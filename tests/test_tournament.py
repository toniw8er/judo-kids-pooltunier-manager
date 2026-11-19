"""Gezielte Regel-, Datei- und Fehlertests: uv run python -m unittest discover -s tests -v"""
from devtools.demo_data import demo
from devtools.helpers import demo_window, record_result
import copy
from datetime import date, datetime
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P
from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from stadtmeisterschaft.application import TournamentSession
from stadtmeisterschaft.domain import FightResult, RuleError, Tournament, parse_weight
from stadtmeisterschaft.output import FIGHT_ORDER, write_pdf
from stadtmeisterschaft.sheets import HEADERS, read_participants, write_ods
from stadtmeisterschaft.storage import Store


class TournamentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "tmp" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.temp.name)
        self.state = demo(10)
        self.state.create_pool()

    def tearDown(self):
        self.temp.cleanup()

    def sheet(self, suffix=".ods", rows=None):
        rows = rows if rows is not None else [HEADERS, ["Jörg", "Müller", "JC Äöü", 2016, "M", "25,3"]]
        path = self.folder / ("meldungen" + suffix)
        if suffix == ".xlsx":
            book = Workbook()
            for row in rows:
                book.active.append(row)
            book.save(path)
            book.close()
        else:
            doc = OpenDocumentSpreadsheet()
            table = Table(name="Meldungen")
            doc.spreadsheet.addElement(table)
            for values in rows:
                row = TableRow()
                for value in values:
                    cell = (TableCell(valuetype="date", datevalue=value.isoformat())
                            if isinstance(value, date) else TableCell(valuetype="string"))
                    cell.addElement(P(text=str(value)))
                    row.addElement(cell)
                table.addElement(row)
            doc.save(str(path))
        return path

    def test_move_removes_source_and_keeps_one_assignment(self):
        person = self.state.pools[0].members[0]
        self.state.move(person, "Pool 04")
        self.assertNotIn(person, self.state.pools[0].members)
        self.assertEqual(self.state.pool("Pool 04").members, [person])
        self.state.validate()

    def test_full_target_is_rejected_without_changes(self):
        before = self.state.to_dict()
        with self.assertRaises(RuleError):
            self.state.move(self.state.pools[0].members[0], "Pool 02")
        self.assertEqual(before, self.state.to_dict())

    def test_child_can_return_to_unassigned(self):
        person = self.state.pools[0].members[0]
        self.state.move(person, "")
        self.assertFalse(any(person in pool.members for pool in self.state.pools))
        self.assertIn(person, [p.id for p in self.state.participants])
        self.state.move(person, "Pool 04")
        self.assertIn(person, self.state.pool("Pool 04").members)

    def test_results_and_optional_name_survive_restart(self):
        results = {"1": FightResult("1:0", 7, 7), "3": FightResult("0:0", 5, 5)}
        self.state.save_pool("Pool 01", " U11 · Gruppe A ", results)
        Store(self.folder).save(self.state)
        loaded = Store(self.folder).load()
        pool = loaded.pool("Pool 01")
        self.assertEqual(pool.id, "Pool 01")
        self.assertEqual(pool.name, "U11 · Gruppe A")
        self.assertEqual(pool.results, results)
        self.assertNotIn("2", pool.results)  # Eine leere Begegnung ist kein Unentschieden.
        with self.assertRaises(RuleError):
            loaded.move(pool.members[0], "")
        loaded.save_pool(pool.id, pool.name, {})
        self.assertTrue(pool.started)
        with self.assertRaises(RuleError):
            loaded.move(pool.members[0], "")

    def test_invalid_result_does_not_partly_rename_or_replace(self):
        before = self.state.to_dict()
        with self.assertRaises(RuleError):
            self.state.save_pool("Pool 01", "Neuer Name", {"1": FightResult("1:0", 10, 3)})
        self.assertEqual(self.state.to_dict(), before)

    def test_old_first_fight_is_preserved_when_loading(self):
        payload = self.state.to_dict()
        pool = payload["pools"][0]
        del pool["results"]
        del pool["name"]
        pool["started"] = True
        pool["test_result"] = {"participants": pool["members"][:2], "winner": "Zweites Kind", "first": 5, "second": 10}
        loaded = Tournament.from_dict(payload)
        self.assertEqual(loaded.pools[0].results, {"1": FightResult("0:1", 5, 10)})
        self.assertTrue(loaded.pools[0].started)
        self.assertNotIn("test_result", loaded.to_dict()["pools"][0])

    def test_started_source_and_target_stay_frozen_after_reload(self):
        record_result(self.state, "Pool 01", "Erstes Kind", 10, 0)
        store = Store(self.folder)
        store.save(self.state)
        loaded = Store(self.folder).load()
        with self.assertRaises(RuleError):
            loaded.move(loaded.pools[0].members[0], "Pool 04")
        with self.assertRaises(RuleError):
            loaded.move(loaded.pools[2].members[0], "Pool 01")
        self.assertEqual(loaded.pools[0].results["1"].first, 10)

    def test_ods_and_xlsx_produce_equivalent_values(self):
        ods = read_participants(self.sheet())
        xlsx = read_participants(self.sheet(".xlsx"))
        self.assertEqual(ods[0].name, "Jörg Müller")
        self.assertEqual(ods[0].weight_grams, 25300)
        self.assertEqual(ods[0].__dict__ | {"id": "ignored"}, xlsx[0].__dict__ | {"id": "ignored"})

    def test_birth_dates_from_text_and_native_cells_in_both_formats(self):
        headers = HEADERS.copy()
        headers[3] = "Geburtsdatum"
        cases = ["15.03.2016", "1.2.2016", "2016-03-15", "29.02.2016",
                 date(2016, 3, 15), datetime(2016, 3, 15)]
        for suffix in [".ods", ".xlsx"]:
            for value in cases:
                with self.subTest(suffix=suffix, value=value):
                    path = self.sheet(suffix, [headers, ["Jörg", "Müller", "JC", value, "M", "25,3"]])
                    person = read_participants(path)[0]
                    self.assertEqual(person.birth_year, 2016)
                    self.assertEqual(person.weight_grams, 25300)
                    self.assertFalse(hasattr(person, 'birth_date'))

    def test_birth_columns_are_mutually_exclusive_even_with_equal_or_empty_values(self):
        for suffix in [".ods", ".xlsx"]:
            for year, birthday in [(2016, "15.03.2016"), (2016, "15.03.2017"), (2016, ""), ("", "")]:
                with self.subTest(suffix=suffix, year=year, birthday=birthday):
                    headers = HEADERS[:4] + ["Geburtsdatum"] + HEADERS[4:]
                    path = self.sheet(suffix, [headers, ["Jörg", "Müller", "JC", year, birthday, "M", "25,3"]])
                    with self.assertRaisesRegex(RuleError, "Geburtsjahr oder Geburtsdatum, niemals beide"):
                        read_participants(path)
            path = self.sheet(suffix, [HEADERS[:3] + HEADERS[4:], ["Jörg", "Müller", "JC", "M", "25,3"]])
            with self.assertRaisesRegex(RuleError, "genau eine Spalte"):
                read_participants(path)

    def test_invalid_birth_dates_reject_entire_import_with_row_number(self):
        headers = HEADERS.copy()
        headers[3] = "Geburtsdatum"
        store = Store(self.folder)
        store.save(self.state)
        session = TournamentSession(store, self.state)
        before = self.state.to_dict()
        invalid = ["29.02.2015", "31.04.2016", "15.13.2016", "03/04/2016", "2016", 2016,
                   42444, "15.03.1899", "15.03.2101", "unbekannt", ""]
        for suffix in [".ods", ".xlsx"]:
            for value in invalid:
                with self.subTest(suffix=suffix, value=value):
                    path = self.sheet(suffix, [headers,
                        ["Neu", "Gültig", "JC", "15.03.2016", "M", "25,3"],
                        ["Neu", "Ungültig", "JC", value, "W", "24,1"]])
                    with self.assertRaisesRegex(RuleError, "Zeile 3"):
                        session.import_participants(path)
                    self.assertEqual(session.state.to_dict(), before)
                    self.assertEqual(Store(self.folder).load().to_dict(), before)
                    self.assertFalse(store.participant_path.exists())

    def test_date_in_year_column_and_formula_in_date_column_are_rejected(self):
        for suffix in [".ods", ".xlsx"]:
            path = self.sheet(suffix, [HEADERS, ["Jörg", "Müller", "JC", date(2016, 3, 15), "M", "25,3"]])
            with self.assertRaisesRegex(RuleError, "Geburtsjahr"):
                read_participants(path)
        headers = HEADERS.copy()
        headers[3] = "Geburtsdatum"
        path = self.sheet(".xlsx", [headers, ["Jörg", "Müller", "JC", "=DATE(2016,3,15)", "M", "25,3"]])
        with self.assertRaisesRegex(RuleError, "Formel"):
            read_participants(path)

    def test_german_gender_and_weight_inputs_in_both_formats(self):
        cases = [("W", "15,2", "F"), ("w", "15.2", "F"), ("F", 15.2, "F"),
                 ("J", "15,2", "M"), ("j", "15.2", "M"), ("M", "15,2 kg", "M"),
                 ("F", "15.2 kilo", "F")]
        for suffix in [".ods", ".xlsx"]:
            for gender, weight, expected in cases:
                with self.subTest(suffix=suffix, gender=gender, weight=weight):
                    path = self.sheet(suffix, [HEADERS, ["Jörg", "Müller", "JC", 2016, gender, weight]])
                    person = read_participants(path)[0]
                    self.assertEqual(person.gender, expected)
                    self.assertEqual(person.weight_grams, 15200)

    def test_calc_numeric_weight_with_comma_display(self):
        from odf.opendocument import load
        path = self.sheet(rows=[HEADERS, ["Mia", "Müller", "JC", 2016, "W", "15,2"]])
        document = load(str(path))
        cell = document.getElementsByType(TableCell)[11]
        cell.setAttribute("valuetype", "float")
        cell.setAttribute("value", 15.2)
        document.save(str(path), addsuffix=False)
        self.assertEqual(read_participants(path)[0].weight_grams, 15200)

    def test_numeric_weight_storage_noise_in_ods_and_xlsx(self):
        from odf.opendocument import load
        from math import nextafter
        cases = [("20.399999999999999", 20400), ("20.400000000000002", 20400),
                 ("15.200000000000001", 15200), ("25.299999999999997", 25300)]
        for raw, expected in cases:
            path = self.sheet(rows=[HEADERS, ["Mia", "Müller", "JC", 2016, "W", raw]])
            document = load(str(path))
            cell = document.getElementsByType(TableCell)[11]
            cell.setAttribute("valuetype", "float")
            cell.setAttribute("value", raw)
            document.save(str(path), addsuffix=False)
            with self.subTest(format="ods", raw=raw):
                self.assertEqual(read_participants(path)[0].weight_grams, expected)
        for value in [20.4, nextafter(20.4, 0), nextafter(20.4, 100)]:
            path = self.sheet(".xlsx", [HEADERS, ["Mia", "Müller", "JC", 2016, "W", value]])
            with self.subTest(format="xlsx", value=value):
                self.assertEqual(read_participants(path)[0].weight_grams, 20400)

    def test_real_weight_precision_is_not_rounded_in_numeric_or_text_cells(self):
        from odf.opendocument import load
        for raw in ["20.41", "20.3999", "20.40000001", "NaN", "Infinity", "0", "-1"]:
            for suffix in [".ods", ".xlsx"]:
                path = self.sheet(suffix, [HEADERS, ["Mia", "Müller", "JC", 2016, "W", float(raw)]])
                if suffix == ".ods":
                    document = load(str(path))
                    cell = document.getElementsByType(TableCell)[11]
                    cell.setAttribute("valuetype", "float")
                    cell.setAttribute("value", raw)
                    document.save(str(path), addsuffix=False)
                with self.subTest(suffix=suffix, raw=raw), self.assertRaisesRegex(RuleError, "Zeile 2"):
                    read_participants(path)
        for suffix in [".ods", ".xlsx"]:
            path = self.sheet(suffix, [HEADERS, ["Mia", "Müller", "JC", 2016, "W", "20.399999999999999"]])
            with self.subTest(suffix=suffix, text=True), self.assertRaisesRegex(RuleError, "100-Gramm"):
                read_participants(path)

    def test_invalid_second_row_rejects_complete_import(self):
        path = self.sheet(rows=[HEADERS, ["Jörg", "Müller", "JC", 2016, "M", "25,3"],
                               ["Lea", "Weiß", "", 2016, "F", "26,0"]])
        before = self.state.to_dict()
        with self.assertRaisesRegex(RuleError, "Zeile 3"):
            self.state.add_participants(read_participants(path))
        self.assertEqual(before, self.state.to_dict())

    def test_duplicate_batch_rejected_before_appending(self):
        people = read_participants(self.sheet())
        duplicate = copy.deepcopy(people[0])
        duplicate.id = "another-id"
        before = self.state.to_dict()
        with self.assertRaises(RuleError):
            self.state.add_participants(people + [duplicate])
        self.assertEqual(before, self.state.to_dict())

    def test_ods_template_and_id_export(self):
        from odf.opendocument import load
        from odf import teletype
        path = self.folder / "vorlage.ods"
        write_ods(path)
        doc = load(str(path))
        headers = [teletype.extractText(cell) for cell in doc.getElementsByType(TableCell)]
        self.assertEqual(headers, HEADERS)
        write_ods(path, self.state.participants)
        self.assertIn(self.state.participants[0].id, teletype.extractText(load(str(path)).spreadsheet))

    def test_invalid_weights_not_rounded(self):
        for value in ["25,31", "NaN", "Infinity", "0", "-1", "abc"]:
            with self.subTest(value=value), self.assertRaises(RuleError):
                parse_weight(value)

    def test_formula_rejected_in_xlsx(self):
        path = self.sheet(".xlsx", [HEADERS, ["Jörg", "Müller", "JC", 2016, "M", "=25+1"]])
        with self.assertRaisesRegex(RuleError, "Formel"):
            read_participants(path)

    def test_stale_writer_cannot_overwrite_newer_state(self):
        first = Store(self.folder)
        first.save(self.state)
        second = Store(self.folder)
        old = second.load()
        self.state.move(self.state.pools[0].members[0], "Pool 04")
        first.save(self.state)
        with self.assertRaises(RuntimeError):
            second.save(old)
        self.assertEqual(Store(self.folder).load().to_dict(), self.state.to_dict())

    def test_failed_commit_leaves_previous_state(self):
        store = Store(self.folder)
        store.save(self.state)
        before = self.state.to_dict()
        with store.connect() as con:
            con.execute("CREATE TRIGGER reject_update BEFORE UPDATE ON current_state "
                        "BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END")
        self.state.move(self.state.pools[0].members[0], "Pool 04")
        with self.assertRaises(sqlite3.DatabaseError):
            store.save(self.state)
        self.assertEqual(Store(self.folder).load().to_dict(), before)
        self.assertEqual(store.revision, 1)

    def test_process_exit_during_transaction_restores_last_commit(self):
        import subprocess
        import sys
        store = Store(self.folder)
        store.save(self.state)
        before = self.state.to_dict()
        code = ("import os,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
                "c.execute('BEGIN IMMEDIATE'); "
                "c.execute(\"UPDATE current_state SET payload='broken' WHERE id=1\"); os._exit(17)")
        result = subprocess.run([sys.executable, "-c", code, str(store.path)], timeout=10)
        self.assertEqual(result.returncode, 17)
        self.assertEqual(Store(self.folder).load().to_dict(), before)

    @unittest.skipUnless(os.name == "nt", "Windows-Dateisperre")
    def test_locked_ods_keeps_existing_file_unchanged(self):
        import ctypes
        from ctypes import wintypes
        path = self.folder / "locked.ods"
        write_ods(path)
        before = path.read_bytes()
        create = ctypes.windll.kernel32.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        handle = create(str(path), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            with self.assertRaises(PermissionError):
                write_ods(path, self.state.participants)
        finally:
            close = ctypes.windll.kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close(handle)
        self.assertEqual(path.read_bytes(), before)

    def test_ui_does_not_show_failed_save_as_applied(self):
        from unittest.mock import patch
        window = demo_window(self.folder, 10)
        window.create_pool()
        before = window.state.to_dict()
        person = window.state.pools[0].members[0]
        with patch.object(window.store, "save", side_effect=OSError("Datenträger voll")):
            window.move(person, "Pool 04")
        self.assertEqual(window.state.to_dict(), before)
        self.assertIn("Nicht übernommen", window.message.text())
        window.close()

    def test_drag_drop_routes_through_rules_and_save(self):
        from stadtmeisterschaft.ui.main_window import MIME
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        window = demo_window(self.folder, 10)
        window.create_pool()
        window.show()
        self.app.processEvents()
        person = window.state.pools[0].members[0]
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"participant_id": person, "source_pool_id": "Pool 01"}).encode())
        viewport = window.lists["Pool 04"].viewport()
        enter = QDragEnterEvent(QPoint(20, 20), Qt.DropAction.MoveAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, enter)
        drop = QDropEvent(QPointF(20, 20), Qt.DropAction.MoveAction, mime,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, drop)
        self.assertIn(person, window.state.pool("Pool 04").members)
        self.assertIn(person, Store(self.folder).load().pool("Pool 04").members)
        # Derselbe echte Drop-Weg muss auch zurück nach „Noch ohne Pool“ funktionieren.
        mime.setData(MIME, json.dumps({"participant_id": person, "source_pool_id": "Pool 04"}).encode())
        viewport = window.lists[""].viewport()
        self.assertTrue(window.lists[""].acceptDrops())
        enter = QDragEnterEvent(QPoint(20, 20), Qt.DropAction.MoveAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(20, 20), Qt.DropAction.MoveAction, mime,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, drop)
        self.assertFalse(any(person in pool.members for pool in Store(self.folder).load().pools))
        window.close()

    def test_pool_header_opens_page_and_saves_real_encounters(self):
        from stadtmeisterschaft.ui.pool_page import PoolPage
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QPushButton
        window = demo_window(self.folder, 10)
        window.show()
        self.app.processEvents()
        button_labels = [button.text() for button in window.findChildren(QPushButton)]
        self.assertIn("PDF exportieren", button_labels)
        self.assertFalse(any("100 Testkinder" in label or "verschieben" in label for label in button_labels))
        self.assertFalse(hasattr(window, "target"))
        page_seen = []

        def enter_results():
            page = self.app.activeModalWidget()
            page_seen.append(isinstance(page, PoolPage))
            try:
                page.pool_name.setText("U11 · Gruppe A")
                for combo, value in zip(page.editors[0], ("1:0", 10, 5)):
                    combo.setCurrentIndex(combo.findData(value))
                for combo, value in zip(page.editors[2], ("0:1", 0, 7)):
                    combo.setCurrentIndex(combo.findData(value))
                self.assertTrue(page.save())
            finally:
                page.accept()

        QTimer.singleShot(0, enter_results)
        window.headers["Pool 01"].click()
        self.assertEqual(page_seen, [True])
        pool = Store(self.folder).load().pool("Pool 01")
        self.assertEqual(pool.name, "U11 · Gruppe A")
        self.assertEqual(pool.results, {"1": FightResult("1:0", 10, 5), "3": FightResult("0:1", 0, 7)})
        self.assertIn("U11 · Gruppe A", window.headers["Pool 01"].text())
        window.close()

    def test_partial_pool_row_is_not_saved_as_draw_or_zero(self):
        from stadtmeisterschaft.ui.pool_page import PoolPage
        window = demo_window(self.folder, 10)
        page = PoolPage(window, "Pool 01")
        before = window.state.to_dict()
        page.pool_name.setText("Noch nicht speichern")
        page.editors[0][0].setCurrentIndex(page.editors[0][0].findData("1:0"))
        self.assertFalse(page.save())
        self.assertIn("Kampf 1", page.message.text())
        self.assertEqual(Store(self.folder).load().to_dict(), before)
        page.accept()
        window.close()

    def test_failed_pool_save_preserves_entered_values_for_retry(self):
        from stadtmeisterschaft.ui.pool_page import PoolPage
        from unittest.mock import patch
        window = demo_window(self.folder, 10)
        page = PoolPage(window, "Pool 01")
        before = window.state.to_dict()
        for combo, value in zip(page.editors[1], ("1:0", 7, 7)):
            combo.setCurrentIndex(combo.findData(value))
        with patch.object(window.store, "save", side_effect=OSError("Datenträger voll")):
            self.assertFalse(page.save())
        self.assertEqual(window.state.to_dict(), before)
        self.assertEqual(tuple(combo.currentData() for combo in page.editors[1]), ("1:0", 7, 7))
        self.assertIn("Nicht übernommen", page.message.text())
        self.assertTrue(page.save())
        self.assertEqual(Store(self.folder).load().pool("Pool 01").results["2"], FightResult("1:0", 7, 7))
        page.accept()
        window.close()

    def test_tournament_configuration_survives_restart(self):
        # Zentrale Metadaten bleiben unabhängig von der Ergebniseingabe erhalten.
        self.state.configure("Stadtmeisterschaft München", "2027-02-20")
        store = Store(self.folder)
        store.save(self.state)
        restored = Store(self.folder).load()
        self.assertEqual(restored.name, "Stadtmeisterschaft München")
        self.assertEqual(restored.event_date, "2027-02-20")

    def test_closing_pool_page_does_not_silently_discard_drafts(self):
        from stadtmeisterschaft.ui.pool_page import PoolPage
        from PySide6.QtWidgets import QMessageBox
        from unittest.mock import patch
        window = demo_window(self.folder, 10)
        page = PoolPage(window, "Pool 01")
        page.show()
        self.app.processEvents()
        page.editors[0][0].setCurrentIndex(page.editors[0][0].findData("1:0"))
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Cancel):
            page.close()
        self.assertTrue(page.isVisible())
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Save):
            page.close()
        self.assertTrue(page.isVisible())
        self.assertIn("Kampf 1", page.message.text())
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Discard):
            page.close()
        self.assertFalse(page.isVisible())
        self.assertEqual(Store(self.folder).load().pool("Pool 01").results, {})
        window.close()

    def test_invalid_configuration_leaves_previous_values_unchanged(self):
        before = self.state.to_dict()
        for name, value in [("", "2027-02-20"), ("Turnier", "2027-02-30"), ("Turnier", "")]:
            with self.assertRaises(RuleError):
                self.state.configure(name, value)
            self.assertEqual(self.state.to_dict(), before)

    def test_legacy_state_needs_date_before_printing(self):
        payload = self.state.to_dict()
        del payload["name"]
        del payload["event_date"]
        legacy = Tournament.from_dict(payload)
        self.assertEqual(legacy.event_date, "")
        path = self.folder / "existing.pdf"
        path.write_bytes(b"existing output")
        with self.assertRaises(RuleError):
            write_pdf(path, legacy, legacy.pools[:1])
        self.assertEqual(path.read_bytes(), b"existing output")

    def test_pdf_and_confirmed_fight_order(self):
        self.assertEqual(FIGHT_ORDER[3], [(1, 2), (1, 3), (2, 3)])
        self.assertEqual(FIGHT_ORDER[5], [(1, 2), (3, 4), (1, 5), (2, 3), (4, 5),
                                         (1, 3), (2, 5), (1, 4), (3, 5), (2, 4)])
        path = self.folder / "pools.pdf"
        write_pdf(path, self.state, self.state.pools[:3])
        self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
        self.assertGreater(path.stat().st_size, 5000)


if __name__ == "__main__":
    unittest.main()
