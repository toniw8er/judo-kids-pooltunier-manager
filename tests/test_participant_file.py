"""Gemeinsame Teilnehmerdatei einschließlich Fehlern und Wiederanlauf."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from odf.opendocument import load
from odf.table import TableCell, TableRow
from odf.text import P

from PySide6.QtWidgets import QApplication, QFileDialog

from devtools.demo_data import demo
from stadtmeisterschaft.application import TournamentSession
from stadtmeisterschaft.domain import FightResult, Participant, RuleError
from stadtmeisterschaft.sheets import HEADERS, read_participants, write_ods
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.main_window import Window


class ParticipantFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = Store(self.folder)
        self.state = demo(10)
        self.store.save(self.state)
        self.session = TournamentSession(self.store, self.state)
        self.path = self.store.participant_path

    def initialize(self):
        self.session.reload_participants()

    def incoming(self):
        return read_participants(self.path, with_ids=True)

    def new_person(self):
        return Participant("", "Neu", "Angemeldet", "JC", 2017, "F", 23100)

    def reject_updates(self):
        with self.store.connect() as con:
            con.execute("CREATE TRIGGER reject_update BEFORE UPDATE ON current_state "
                        "BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END")

    def date_file(self, *, both=False, changed_year=None):
        doc = load(str(self.path))
        rows = doc.spreadsheet.getElementsByType(TableRow)
        for index, row in enumerate(rows):
            cells = row.getElementsByType(TableCell)
            cell = cells[3]
            if both:
                extra = TableCell(valuetype="string")
                extra.addElement(P(text="Geburtsdatum" if index == 0 else "15.03.2016"))
                row.addElement(extra)
            else:
                for child in list(cell.childNodes):
                    cell.removeChild(child)
                cell.addElement(P(text="Geburtsdatum" if index == 0 else
                    f"15.03.{changed_year if changed_year is not None and index == 1 else self.session.state.participants[index-1].birth_year}"))
        doc.save(str(self.path))

    def test_date_column_reload_preserves_started_data_and_converts_export_to_year(self):
        pool = self.state.pools[0]
        self.state.save_pool(pool.id, "Gestartet", {"1": FightResult("1:0", 10, 0)})
        self.state.participants[0].bookmark = "Startgebühr offen"
        self.store.save(self.state)
        self.initialize()
        before = deepcopy(self.session.state)
        self.date_file()
        result = self.session.reload_participants()
        self.assertEqual(result, before)
        self.assertEqual([(p.id, p.birth_year) for p in self.incoming()],
                         [(p.id, p.birth_year) for p in result.participants])
        self.assertIsNone(self.incoming()[0].bookmark)
        doc = load(str(self.path))
        from odf import teletype
        headers = [teletype.extractText(c) for c in doc.spreadsheet.getElementsByType(TableRow)[0].getElementsByType(TableCell)]
        self.assertEqual(headers, HEADERS + ["Teilnehmer-ID"])
        restarted = Store(self.folder)
        self.assertEqual(TournamentSession(restarted, restarted.load()).check_participants_at_start(), before)

    def test_date_column_cannot_bypass_started_year_protection(self):
        pool = self.state.pools[0]
        self.state.save_pool(pool.id, "", {"1": FightResult("1:0", 10, 0)})
        self.store.save(self.state)
        self.initialize()
        self.date_file(changed_year=self.state.participants[0].birth_year + 1)
        content = self.path.read_bytes()
        with self.assertRaisesRegex(RuleError, "Jahrgang.*gesperrt"):
            self.session.reload_participants()
        self.assertEqual(self.path.read_bytes(), content)
        self.assertEqual(self.session.state, self.state)
        self.assertEqual(Store(self.folder).load(), self.state)

    def test_both_birth_columns_reject_reload_without_overwriting_file_or_state(self):
        self.initialize()
        self.date_file(both=True)
        content = self.path.read_bytes()
        with self.assertRaisesRegex(RuleError, "niemals beide"):
            self.session.reload_participants()
        self.assertEqual(self.path.read_bytes(), content)
        self.assertEqual(self.session.state, self.state)
        self.assertEqual(Store(self.folder).load(), self.state)

    def test_ids_changes_removal_and_new_rows_preserve_pools_and_survive_restart(self):
        self.initialize()
        people = self.incoming()
        changed, removed = people[0].id, people[-1].id
        people[0].last_name = "Korrigiert"
        people[0].weight_grams += 100
        people = people[:-1] + [self.new_person()]
        write_ods(self.path, people)
        result = self.session.reload_participants()
        self.assertEqual(result.participant(changed).last_name, "Korrigiert")
        self.assertEqual(result.pools[0].members, self.state.pools[0].members)
        self.assertFalse(any(removed in pool.members for pool in result.pools))
        self.assertEqual(result.participants[-1].name, "Neu Angemeldet")
        self.assertTrue(result.participants[-1].id)
        self.assertNotIn(result.participants[-1].id, {pid for pool in result.pools for pid in pool.members})
        self.assertEqual(self.incoming(), result.participants)
        restarted = Store(self.folder)
        session = TournamentSession(restarted, restarted.load())
        before_revision = restarted.revision
        self.assertEqual(session.check_participants_at_start().to_dict(), result.to_dict())
        self.assertEqual(restarted.revision, before_revision)

    def test_paper_stand_for_external_name_change_is_recovered_exactly_once(self):
        self.initialize()
        people = self.incoming()
        people[0].last_name = "Neuer Name"
        write_ods(self.path, people)
        before = deepcopy(self.session.state)
        self.reject_updates()
        with self.assertRaises(RuleError):
            self.session.reload_participants()
        self.assertEqual(self.session.state, before)
        self.assertEqual(self.store.load(), before)
        with self.store.connect() as con:
            con.execute("DROP TRIGGER reject_update")
        restarted = Store(self.folder)
        session = TournamentSession(restarted, restarted.load())
        recovered = session.check_participants_at_start()
        for pool in recovered.pools:
            expected = before.pool(pool.id).print_revision + int(people[0].id in pool.members)
            self.assertEqual(pool.print_revision, expected)
        self.assertEqual(session.check_participants_at_start(), recovered)
        self.assertEqual(restarted.load(), recovered)

    def test_unknown_duplicate_and_erased_ids_reject_whole_file(self):
        self.initialize()
        for mode in ("unknown", "duplicate", "erased", "duplicate_values"):
            with self.subTest(mode=mode):
                people = deepcopy(self.state.participants)
                if mode == "unknown":
                    people[0].id = "unknown"
                elif mode == "duplicate":
                    people[1].id = people[0].id
                elif mode == "erased":
                    people[0].id = ""
                else:
                    people[1] = deepcopy(people[0])
                    people[1].id = self.state.participants[1].id
                write_ods(self.path, people)
                before = self.path.read_bytes()
                with self.assertRaises(RuleError):
                    self.session.reload_participants()
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual(self.session.state.to_dict(), self.state.to_dict())
                self.assertEqual(Store(self.folder).load().to_dict(), self.state.to_dict())

    def test_started_friendship_protects_data_and_deletion_even_with_results_cleared(self):
        friend = self.state.create_pool("friendship")
        for p in self.state.participants[:2]:
            self.state.move(p.id, friend)
        self.state.save_pool(friend, "", {"1": FightResult("1:0", 10, 0)})
        self.state.save_pool(friend, "", {})
        self.store.save(self.state)
        self.initialize()
        for field, value in (("weight_grams", 30000), ("birth_year", 2020), ("gender", "F"), ("delete", None)):
            people = deepcopy(self.state.participants)
            if field == "delete":
                people.pop(0)
            else:
                if getattr(people[0], field) == value:
                    value = "M"
                setattr(people[0], field, value)
            write_ods(self.path, people)
            with self.subTest(field=field), self.assertRaises(RuleError):
                self.session.reload_participants()
            self.assertEqual(self.session.state.to_dict(), self.state.to_dict())
        people = deepcopy(self.state.participants)
        people[0].last_name, people[0].club = "Korrigiert", "Neuer Verein"
        write_ods(self.path, people)
        expected = deepcopy(self.state.pools)
        for pool in expected:
            pool.print_revision += int(people[0].id in pool.members)
        self.assertEqual(self.session.reload_participants().pools, expected)

    def test_empty_valid_file_deletes_only_unstarted_participants(self):
        self.initialize()
        write_ods(self.path, [])
        result = self.session.reload_participants()
        self.assertEqual(result.participants, [])
        self.assertTrue(all(not pool.members for pool in result.pools))

    def test_started_regular_pool_keeps_results_and_members_on_name_correction(self):
        pool = self.state.pools[0]
        self.state.save_pool(pool.id, "Gestartet", {"1": FightResult("1:0", 10, 7)})
        self.store.save(self.state)
        self.initialize()
        people = self.incoming()
        people.reverse()
        next(p for p in people if p.id == pool.members[0]).first_name = "Korrektur"
        write_ods(self.path, people)
        expected = deepcopy(self.state.pools)
        for item in expected:
            item.print_revision += int(pool.members[0] in item.members)
        self.assertEqual(self.session.reload_participants().pools, expected)
        people = [p for p in people if p.id != pool.members[0]]
        write_ods(self.path, people)
        with self.assertRaisesRegex(RuleError, "Löschen nach Start"):
            self.session.reload_participants()

    def test_file_changed_between_parse_and_replace_is_preserved(self):
        self.initialize()
        write_ods(self.path, self.incoming() + [self.new_person()])
        actual = self.store._check_file
        calls = 0

        def changed(expected):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.path.write_bytes(b"saved again externally")
            actual(expected)

        with patch.object(self.store, "_check_file", side_effect=changed):
            with self.assertRaisesRegex(RuleError, "zwischenzeitlich"):
                self.session.reload_participants()
        self.assertEqual(self.path.read_bytes(), b"saved again externally")
        self.assertEqual(self.store.load().to_dict(), self.state.to_dict())

    def test_duplicate_id_error_reports_actual_line_after_blank_row(self):
        from odf.opendocument import load
        from odf.table import TableRow
        self.initialize()
        people = deepcopy(self.state.participants)
        people[1].id = people[0].id
        write_ods(self.path, people)
        doc = load(str(self.path))
        first = doc.getElementsByType(TableRow)[1]
        first.parentNode.insertBefore(TableRow(), first)
        doc.save(str(self.path), addsuffix=False)
        with self.assertRaisesRegex(RuleError, "teilnehmer.ods, Zeile 4: Doppelte Teilnehmer-ID"):
            self.session.reload_participants()

    def test_file_reverted_after_replace_is_never_reported_as_saved(self):
        self.initialize()
        write_ods(self.path, self.incoming() + [self.new_person()])
        before = self.path.read_bytes()

        def reverted(path, content):
            path.write_bytes(content)
            path.write_bytes(before)

        with patch("stadtmeisterschaft.storage.write_bytes_atomic", side_effect=reverted):
            with self.assertRaisesRegex(RuleError, "zurückgesetzt"):
                self.session.reload_participants()
        self.assertEqual(self.session.state.to_dict(), self.state.to_dict())
        self.assertEqual(self.store.load().to_dict(), self.state.to_dict())

    def test_missing_or_unreadable_file_never_means_delete_all(self):
        self.initialize()
        for content in (None, b"broken"):
            if content is None:
                self.path.unlink()
            else:
                self.path.write_bytes(content)
            with self.assertRaises(Exception):
                self.session.reload_participants()
            self.assertEqual(self.session.state.to_dict(), self.state.to_dict())

    def test_new_ids_and_entire_import_are_not_applied_when_ods_replace_fails(self):
        self.initialize()
        people = self.incoming() + [self.new_person()]
        write_ods(self.path, people)
        before = self.path.read_bytes()
        with patch("stadtmeisterschaft.storage.write_bytes_atomic", side_effect=PermissionError("gesperrt")):
            with self.assertRaises(PermissionError):
                self.session.reload_participants()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(Store(self.folder).load().to_dict(), self.state.to_dict())
        self.assertEqual(self.session.state.to_dict(), self.state.to_dict())
        result = self.session.reload_participants()
        self.assertEqual(len(result.participants), 11)

    def test_sqlite_failure_after_file_replace_recovers_exact_ids_and_blocks_other_saves(self):
        self.initialize()
        write_ods(self.path, self.incoming() + [self.new_person()])
        self.reject_updates()
        with self.assertRaisesRegex(RuleError, "noch nicht abgeschlossen"):
            self.session.reload_participants()
        assigned_id = self.incoming()[-1].id
        self.assertTrue(assigned_id)
        self.assertEqual(self.session.state.to_dict(), self.state.to_dict())
        with self.assertRaisesRegex(RuleError, "noch offen"):
            self.session.change(lambda state: state.create_pool())
        with self.store.connect() as con:
            con.execute("DROP TRIGGER reject_update")
        restarted = Store(self.folder)
        session = TournamentSession(restarted, restarted.load())
        result = session.check_participants_at_start()
        self.assertEqual(result.participants[-1].id, assigned_id)
        self.assertEqual(restarted.load().to_dict(), result.to_dict())

    def test_sqlite_intent_write_failure_does_not_touch_ods(self):
        self.initialize()
        write_ods(self.path, self.incoming() + [self.new_person()])
        before = self.path.read_bytes()
        with self.store.connect() as con:
            con.execute("CREATE TRIGGER reject_intent BEFORE INSERT ON participant_transfer "
                        "BEGIN SELECT RAISE(ABORT, 'full'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.session.reload_participants()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(Store(self.folder).load().to_dict(), self.state.to_dict())

    def test_process_exit_before_and_after_file_replace(self):
        self.initialize()
        for phase in ("before", "after"):
            with self.subTest(phase=phase):
                people = deepcopy(self.state.participants) + [self.new_person()]
                write_ods(self.path, people)
                original = self.path.read_bytes()
                code = """
import os, sys
from pathlib import Path
from stadtmeisterschaft.application import TournamentSession
from stadtmeisterschaft.storage import Store
import stadtmeisterschaft.storage as storage
store = Store(Path(sys.argv[1]))
session = TournamentSession(store, store.load())
real_write = storage.write_bytes_atomic
def interrupted(path, content):
    if sys.argv[2] == 'after':
        real_write(path, content)
    os._exit(17)
storage.write_bytes_atomic = interrupted
session.reload_participants()
"""
                result = subprocess.run([sys.executable, "-c", code, str(self.folder), phase], timeout=15)
                self.assertEqual(result.returncode, 17)
                restarted = Store(self.folder)
                self.assertEqual(restarted.load().to_dict(), self.state.to_dict())
                assigned = self.incoming()[-1].id
                if phase == "before":
                    self.assertEqual(self.path.read_bytes(), original)
                    self.assertFalse(restarted.recover_participants())
                else:
                    self.assertTrue(restarted.recover_participants())
                    self.assertEqual(restarted.load().participants[-1].id, assigned)

    def test_external_change_after_interrupted_transfer_is_preserved(self):
        self.initialize()
        self.reject_updates()
        write_ods(self.path, self.incoming() + [self.new_person()])
        with self.assertRaises(RuleError):
            self.session.reload_participants()
        self.path.write_bytes(b"externally changed")
        with self.assertRaisesRegex(RuleError, "Offene Teilnehmerübernahme"):
            self.store.recover_participants()
        self.assertEqual(self.path.read_bytes(), b"externally changed")
        self.assertEqual(self.store.load().to_dict(), self.state.to_dict())

    def test_stale_revision_and_office_lock_preserve_both_states(self):
        self.initialize()
        before = self.path.read_bytes()
        lock = self.path.with_name(".~lock.teilnehmer.ods#")
        lock.touch()
        with self.assertRaisesRegex(RuleError, "Office"):
            self.store.save_with_participants(self.state, before)
        lock.unlink()
        other = Store(self.folder)
        newer = other.load()
        newer.name = "Neuer Stand"
        other.save(newer)
        with self.assertRaisesRegex(RuntimeError, "anderweitig"):
            self.store.save_with_participants(self.state, before)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(Store(self.folder).load().name, "Neuer Stand")

    def test_additional_import_keeps_children_and_refuses_unread_external_changes(self):
        from odf.opendocument import OpenDocumentSpreadsheet
        from odf.table import Table, TableRow, TableCell
        from odf.text import P
        source = self.folder / "meldungen.ods"
        doc = OpenDocumentSpreadsheet()
        table = Table(name="Meldungen")
        doc.spreadsheet.addElement(table)
        for values in (HEADERS, ["Neu", "Angemeldet", "JC", 2017, "W", "23,1"]):
            row = TableRow()
            for value in values:
                cell = TableCell(valuetype="string")
                cell.addElement(P(text=str(value)))
                row.addElement(cell)
            table.addElement(row)
        doc.save(str(source), addsuffix=False)
        result = self.session.import_participants(source)
        self.assertEqual(result.participants[:10], self.state.participants)
        self.assertEqual(result.pools, self.state.pools)
        self.assertEqual(self.incoming(), result.participants)
        changed = self.incoming()
        changed[0].last_name = "Extern"
        write_ods(self.path, changed)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(RuleError, "zuerst neu einlesen"):
            self.session.import_participants(source)
        self.assertEqual(self.path.read_bytes(), before)

    def test_startup_applies_external_changes_and_falls_back_on_errors(self):
        self.initialize()
        people = self.incoming()
        people[0].last_name = "Neuer Name"
        write_ods(self.path, people)
        window = Window(self.folder)
        self.addCleanup(window.close)
        self.assertEqual(window.state.participants[0].last_name, "Neuer Name")
        self.path.unlink()
        window.open_folder(self.folder)
        self.assertEqual(len(window.state.participants), 10)
        self.assertIn("Letzter gespeicherter Stand", window.message.text())
        self.assertFalse(window.reload_participant_file())

    def test_ui_import_reload_and_export_cannot_overwrite_common_file(self):
        window = Window(self.folder)
        self.addCleanup(window.close)
        self.assertTrue(window.reload_participant_file())
        self.assertEqual(window.state.participants, self.incoming())
        before = self.path.read_bytes()
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(self.path), "")):
            window.export_ods(False)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn("bitte über", window.message.text())
        self.assertEqual(self.store.participant_digest(), sha256(before).hexdigest())
        source = Path(__file__).parent / "fixtures" / "testmeldungen.ods"
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(source), "")):
            window.import_sheet()
        self.assertEqual(len(window.state.participants), 11)
        self.assertEqual(window.state.participants, self.incoming())
        self.assertIn("Meldungen übernommen", window.message.text())
        changed = self.incoming()
        changed[-1].last_name = "Per Schaltfläche korrigiert"
        write_ods(self.path, changed)
        self.assertTrue(window.reload_participant_file())
        self.assertEqual(window.state.participants[-1].last_name, "Per Schaltfläche korrigiert")


if __name__ == "__main__":
    unittest.main()
