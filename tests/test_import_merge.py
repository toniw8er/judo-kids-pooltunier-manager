"""Meldelistenabgleich, Gewichtsauswahl und gemeinsame atomare Übernahme."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P
from openpyxl import Workbook
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from devtools.helpers import demo_window, record_result
from stadtmeisterschaft.domain import RuleError
from stadtmeisterschaft.sheets import HEADERS, read_participants
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.import_merge import ImportMerge


class ImportMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'tmp' / 'tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.temp.name)
        self.window = demo_window(self.folder, 10)
        self.session = self.window.session
        self.pid = self.session.state.participants[0].id

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def source(self, people, suffix='.ods'):
        path = self.folder / ('meldungen' + suffix)
        rows = [HEADERS] + [[p.first_name, p.last_name, p.club, p.birth_year, p.gender,
                            str(p.weight_grams / 1000)] for p in people]
        if suffix == '.xlsx':
            book = Workbook()
            for values in rows:
                book.active.append(values)
            book.save(path)
            book.close()
        else:
            doc = OpenDocumentSpreadsheet()
            table = Table(name='Meldungen')
            doc.spreadsheet.addElement(table)
            for values in rows:
                row = TableRow()
                for value in values:
                    cell = TableCell(valuetype='string')
                    cell.addElement(P(text=str(value)))
                    row.addElement(cell)
                table.addElement(row)
            doc.save(str(path), addsuffix=False)
        return path

    def changed(self):
        person = deepcopy(self.session.state.participant(self.pid))
        person.weight_grams += 1000
        return person

    def new_person(self):
        person = self.changed()
        person.id = 'new'
        person.first_name = 'Neu'
        return person

    def test_equal_participants_skip_in_both_formats_and_repeat_import(self):
        self.window.change(lambda state: setattr(state.participant(self.pid), 'bookmark', 'Gebühr offen'), '')
        before = deepcopy(self.session.state)
        for suffix in ['.ods', '.xlsx']:
            source = self.source(before.participants, suffix)
            prepared = self.session.prepare_import(source)
            self.assertEqual(prepared.comparison.unchanged, 10)
            self.assertFalse(prepared.comparison.conflicts)
            state, result = self.session.commit_import(prepared)
            self.assertEqual((result.added, result.unchanged, result.updated), (0, 10, 0))
            self.assertEqual(state, before)
            self.assertEqual(Store(self.folder).load(), before)

    def test_new_weight_and_new_children_preserve_identity_assignments_and_notes(self):
        self.window.change(lambda state: setattr(state.participant(self.pid), 'bookmark', 'Trainer fragen'), '')
        before = deepcopy(self.session.state)
        changed = self.changed()
        prepared = self.session.prepare_import(self.source([changed, self.new_person(), before.participants[1]]))
        self.assertEqual(self.session.state, before)
        self.assertFalse(self.session.store.participant_path.exists())
        state, result = self.session.commit_import(prepared, {self.pid: changed.weight_grams})
        self.assertEqual((result.added, result.updated, result.unchanged, result.kept), (1, 1, 1, 0))
        self.assertEqual(state.participant(self.pid).bookmark, 'Trainer fragen')
        self.assertEqual(state.participant(self.pid).weight_grams, changed.weight_grams)
        for old in before.pools:
            self.assertEqual(state.pool(old.id).members, old.members)
            self.assertEqual(state.pool(old.id).results, old.results)
            self.assertEqual(state.pool(old.id).print_revision, old.print_revision + int(self.pid in old.members))
        self.assertEqual(len(state.participants), 11)
        self.assertTrue(state.participants[-1].id)
        self.assertFalse(any(state.participants[-1].id in pool.members for pool in state.pools))
        exported = read_participants(self.session.store.participant_path, with_ids=True)
        self.assertEqual(exported[0].weight_grams, changed.weight_grams)
        self.assertEqual(Store(self.folder).load(), state)

    def test_existing_weight_is_default_and_cancel_changes_nothing(self):
        before = deepcopy(self.session.state)
        prepared = self.session.prepare_import(self.source([self.changed(), self.new_person()]))
        dialog = ImportMerge(self.window, prepared)
        self.assertEqual(dialog.choices[self.pid].currentData(), before.participant(self.pid).weight_grams)
        dialog.reject()
        self.assertEqual(self.session.state, before)
        self.assertFalse(self.session.store.participant_path.exists())
        state, result = self.session.commit_import(prepared, {self.pid: before.participant(self.pid).weight_grams})
        self.assertEqual((result.kept, result.updated, result.added), (1, 0, 1))
        self.assertEqual(state.participant(self.pid), before.participant(self.pid))

    def test_duplicate_incoming_keys_reject_equal_and_conflicting_weights_atomically(self):
        before = deepcopy(self.session.state)
        for difference in [0, 100]:
            first = self.changed()
            second = deepcopy(first)
            second.weight_grams += difference
            with self.subTest(difference=difference), self.assertRaisesRegex(RuleError, 'Mehrdeutige Meldung'):
                self.session.prepare_import(self.source([self.new_person(), first, second]))
            self.assertEqual(self.session.state, before)
            self.assertFalse(self.session.store.participant_path.exists())

    def test_multiple_existing_matches_are_error_even_if_one_weight_matches(self):
        duplicate = deepcopy(self.session.state.participant(self.pid))
        duplicate.id = 'duplicate'
        duplicate.weight_grams += 100
        self.window.change(lambda state: state.participants.append(duplicate), '')
        before = deepcopy(self.session.state)
        with self.assertRaisesRegex(RuleError, 'Mehrdeutiger Treffer'):
            self.session.prepare_import(self.source([before.participant(self.pid), self.new_person()]))
        self.assertEqual(self.session.state, before)
        self.assertFalse(self.session.store.participant_path.exists())

    def test_all_five_fields_are_used_without_matching_only_names(self):
        for field, value in [('first_name', 'Anders'), ('last_name', 'Anders'), ('club', 'Anderer JC'),
                             ('birth_year', 2001), ('gender', 'F')]:
            person = deepcopy(self.session.state.participant(self.pid))
            if getattr(person, field) == value:
                value = 'M'
            setattr(person, field, value)
            with self.subTest(field=field):
                prepared = self.session.prepare_import(self.source([person]))
                self.assertEqual(len(prepared.comparison.new), 1)
                self.assertFalse(prepared.comparison.conflicts)

    def test_started_regular_and_friendship_pools_skip_weight_but_accept_new_children(self):
        for friendship in [False, True]:
            with self.subTest(friendship=friendship):
                if friendship:
                    friend = self.window.create_pool('friendship')
                    for person in self.session.state.participants[:2]:
                        self.window.move(person.id, friend)
                    pool_id = friend
                else:
                    pool_id = 'Pool 01'
                self.window.change(lambda state: record_result(state, pool_id, 'Erstes Kind', 10, 0), '')
                if friendship:
                    self.window.change(lambda state: state.save_pool('Pool 01', '', {}), '')
                before = deepcopy(self.session.state)
                new = self.new_person()
                new.first_name += str(friendship)
                prepared = self.session.prepare_import(self.source([self.changed(), new]))
                self.assertTrue(prepared.comparison.conflicts[0].locked)
                dialog = ImportMerge(self.window, prepared)
                self.assertFalse(dialog.choices)
                self.assertIn('gesperrt', dialog.table.item(0, 4).text())
                dialog.commit()
                self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
                self.assertEqual(self.session.state.participant(self.pid), before.participant(self.pid))
                self.assertEqual(self.session.state.pools, before.pools)
                self.assertIn('1 gesperrte Gewichte übersprungen', self.window.message.text())

    def test_started_friendship_alone_locks_weight_even_after_results_are_cleared(self):
        friend = self.window.create_pool('friendship')
        for person in self.session.state.participants[:2]:
            self.window.move(person.id, friend)
        self.window.change(lambda state: record_result(state, friend, 'Erstes Kind', 10, 0), '')
        self.window.change(lambda state: state.save_pool(friend, '', {}), '')
        prepared = self.session.prepare_import(self.source([self.changed()]))
        self.assertTrue(prepared.comparison.conflicts[0].locked)
        before = deepcopy(self.session.state)
        with self.assertRaises(RuleError):
            self.session.commit_import(prepared, {self.pid: self.changed().weight_grams})
        self.assertEqual(self.session.state, before)
        self.assertEqual(self.session.commit_import(prepared)[0], before)

    def test_missing_or_invalid_weight_decisions_reject_without_saving(self):
        prepared = self.session.prepare_import(self.source([self.changed(), self.new_person()]))
        before = deepcopy(self.session.state)
        for choices in [None, {}, {self.pid: 99999}, {self.pid: True}, {'unknown': 20000}]:
            with self.subTest(choices=choices), self.assertRaises(RuleError):
                self.session.commit_import(prepared, choices)
            self.assertEqual(self.session.state, before)
            self.assertFalse(self.session.store.participant_path.exists())

    def test_stale_preview_is_rejected(self):
        prepared = self.session.prepare_import(self.source([self.changed()]))
        self.window.change(lambda state: setattr(state, 'name', 'Geändert'), '')
        with self.assertRaisesRegex(RuleError, 'Importvorschau geändert'):
            self.session.commit_import(prepared, {self.pid: self.changed().weight_grams})
        self.assertFalse(self.session.store.participant_path.exists())

    def test_external_common_file_change_is_not_overwritten(self):
        self.session.reload_participants()
        prepared = self.session.prepare_import(self.source([self.changed()]))
        self.session.store.participant_path.write_bytes(b'extern geaendert')
        before = deepcopy(self.session.state)
        with self.assertRaisesRegex(RuleError, 'zwischenzeitlich geändert'):
            self.session.commit_import(prepared, {self.pid: self.changed().weight_grams})
        self.assertEqual(self.session.state, before)
        self.assertEqual(self.session.store.participant_path.read_bytes(), b'extern geaendert')
        self.assertEqual(Store(self.folder).load(), before)

    def test_save_failure_keeps_selection_for_retry(self):
        prepared = self.session.prepare_import(self.source([self.changed(), self.new_person()]))
        dialog = ImportMerge(self.window, prepared)
        dialog.choices[self.pid].setCurrentIndex(1)
        before = deepcopy(self.session.state)
        with patch('stadtmeisterschaft.storage.write_bytes_atomic', side_effect=OSError('Datenträger voll')):
            dialog.commit()
        self.assertEqual(self.session.state, before)
        self.assertEqual(Store(self.folder).load(), before)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.choices[self.pid].currentIndex(), 1)
        self.assertIn('Datenträger voll', dialog.message.text())
        dialog.commit()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.session.state.participant(self.pid).weight_grams, prepared.people[0].weight_grams)
        self.assertEqual(len(self.session.state.participants), 11)

    def test_actual_import_action_opens_merge_and_saves_selected_weight(self):
        changed = self.changed()
        source = self.source([changed, self.new_person()], '.xlsx')
        def select_new():
            dialog = QApplication.activeModalWidget()
            if isinstance(dialog, ImportMerge):
                dialog.choices[self.pid].setCurrentIndex(1)
                dialog.commit()
        QTimer.singleShot(0, select_new)
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(source), '')):
            self.window.import_sheet()
        self.assertEqual(self.window.state.participant(self.pid).weight_grams, changed.weight_grams)
        self.assertIn('1 Gewichte aktualisiert', self.window.message.text())
        self.assertEqual(Store(self.folder).load(), self.window.state)
