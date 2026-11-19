"""Tippfehlertolerante Namenssuche und Navigation zu allen Teilnahmen."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from stadtmeisterschaft.domain import Participant, Pool, RuleError, Tournament
from stadtmeisterschaft.participant_search import search_participants
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.main_window import Window


def search_state():
    return Tournament([
        Participant("a", "Paul", "Pfeifer", "TV Erlangen", 2018, "M", 23100),
        Participant("b", "Paula", "Müller", "JC München", 2017, "F", 23800),
        Participant("c", "Paul", "Pfeifer", "Anderer Verein", 2016, "M", 24000),
        Participant("d", "Anna-Maria", "Groß", "JC", 2017, "F", 24000),
    ], [Pool("Pool 01", ["a", "b"]), Pool("Pool 02", ["a", "c"], kind="friendship"),
        Pool("Pool 03", ["a", "d"], kind="friendship")], next_pool_number=4)


class ParticipantSearchTests(unittest.TestCase):
    def setUp(self):
        self.people = search_state().participants

    def ids(self, query):
        return [p.id for p in search_participants(self.people, query)]

    def test_first_last_partial_and_reverse_names(self):
        for query in ["Paul Pfeifer", "PFEIFER paul", "pfeif", "  Pfeifer   "]:
            with self.subTest(query=query):
                self.assertEqual(set(self.ids(query)), {"a", "c"})
        self.assertEqual(self.ids("Paul")[:2], ["a", "c"])
        self.assertIn("b", self.ids("Paul"))

    def test_small_typos_and_transpositions(self):
        for query in ["Pfeiffer", "Pfiefer", "Pfeier", "Pual Pfeifer"]:
            with self.subTest(query=query):
                self.assertEqual(set(self.ids(query)), {"a", "c"})

    def test_umlauts_sharp_s_and_compound_names(self):
        self.assertEqual(self.ids("MUELLER"), ["b"])
        self.assertEqual(self.ids("müller"), ["b"])
        self.assertEqual(self.ids("gross maria"), ["d"])

    def test_empty_unrelated_and_repeated_words_do_not_match(self):
        for query in ["", "  ", "---", "Xyzzy", "Paul Paul"]:
            self.assertEqual(self.ids(query), [])

    def test_exact_names_rank_before_fuzzy_names(self):
        exact = Participant("e", "Paul", "Pfeiffer", "JC", 2018, "M", 23100)
        self.assertEqual(search_participants(self.people + [exact], "Paul Pfeiffer")[0].id, "e")


class SearchSidebarUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        Store(self.folder).save(search_state())
        self.window = Window(self.folder)
        self.addCleanup(self.window.close)
        self.sidebar = self.window.sidebar
        self.addCleanup(self.sidebar.drafts.clear)
        self.window.show()
        self.window.open_sidebar(False)
        self.app.processEvents()

    def search(self, text):
        self.sidebar.query.setFocus()
        self.sidebar.query.setText(text)
        self.app.processEvents()

    def test_single_entry_toggles_sidebar_and_keeps_tab_query_and_count(self):
        button = self.window.sidebar_button
        self.assertTrue(button.isChecked())
        self.assertEqual([b for b in self.window.centralWidget().findChildren(QPushButton)
                          if not self.sidebar.isAncestorOf(b) and 'Orga-Notizen' in b.text()], [button])
        self.assertFalse(hasattr(self.window, 'search_button'))
        self.assertFalse(hasattr(self.window, 'notes_button'))
        self.mark('participant', 'a', 'Trainer fragen')
        self.assertEqual(button.text(), 'Suche && Orga-Notizen · 1')
        self.sidebar.tabs.setCurrentIndex(1)
        self.search('Trainer')
        button.click()
        self.assertTrue(self.sidebar.isHidden())
        self.assertFalse(button.isChecked())
        button.click()
        self.assertTrue(self.sidebar.isVisible())
        self.assertTrue(button.isChecked())
        self.assertEqual(self.sidebar.tabs.currentIndex(), 1)
        self.assertEqual(self.sidebar.query.text(), 'Trainer')
        self.sidebar.close_button.click()
        self.assertFalse(button.isChecked())
        button.click()
        self.assertTrue(self.sidebar.isVisible())

    def card(self, kind, entity_id):
        return self.sidebar.cards[(kind, entity_id)]

    def mark(self, kind, entity_id, note):
        self.window.change(lambda state: setattr(
            state.participant(entity_id) if kind == 'participant' else state.pool(entity_id), 'bookmark', note), 'Notiz')

    def test_search_disambiguates_names_and_lists_every_destination(self):
        self.search('pfeifer')
        self.assertEqual(list(self.sidebar.cards), [('participant', 'a'), ('participant', 'c')])
        first = self.card('participant', 'a')
        second = self.card('participant', 'c')
        self.assertEqual(set(first.pool_links), {'Pool 01', 'Pool 02', 'Pool 03'})
        self.assertEqual(set(second.pool_links), {'Pool 02'})
        self.assertIn('TV Erlangen', ' '.join(label.text() for label in first.findChildren(QLabel)))
        self.assertIn('Anderer Verein', ' '.join(label.text() for label in second.findChildren(QLabel)))

    def test_click_reveals_filtered_friendship_and_preserves_data_and_sidebar(self):
        before = deepcopy(self.window.state.to_dict())
        self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData('regular'))
        self.window.bookmarks_only.setChecked(True)
        self.search('pfeifer')
        self.card('participant', 'a').pool_links['Pool 03'].click()
        self.app.processEvents()
        self.assertFalse(self.window.cards['Pool 03'].isHidden())
        self.assertEqual(self.window.pool_filter.currentData(), 'all')
        self.assertFalse(self.window.bookmarks_only.isChecked())
        item = self.window.lists['Pool 03'].currentItem()
        self.assertEqual(item.data(Qt.ItemDataRole.UserRole), 'a')
        self.assertTrue(item.isSelected())
        self.assertTrue(self.sidebar.isVisible())
        self.assertEqual(self.sidebar.query.text(), 'pfeifer')
        self.assertEqual(self.window.state.to_dict(), before)
        self.assertEqual(self.window.store.load().to_dict(), before)

    def test_unassigned_and_pool_navigation(self):
        self.window.headers[''].setChecked(False)
        self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData('friendship'))
        self.search('gross')
        self.card('participant', 'd').jump.click()
        self.app.processEvents()
        self.assertTrue(self.window.headers[''].isChecked())
        self.assertEqual(self.window.lists[''].currentItem().data(Qt.ItemDataRole.UserRole), 'd')
        self.window.bookmarks_only.setChecked(True)
        self.search('Pool 02')
        QTest.keyClick(self.sidebar.query, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertFalse(self.window.cards['Pool 02'].isHidden())
        self.assertFalse(self.window.bookmarks_only.isChecked())
        self.assertTrue(self.window.headers['Pool 02'].hasFocus())

    def test_enter_clear_and_search_empty_states(self):
        QTest.keyClicks(self.sidebar.query, 'mueller')
        QTest.keyClick(self.sidebar.query, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(self.window.lists['Pool 01'].currentItem().data(Qt.ItemDataRole.UserRole), 'b')
        self.search('nichtsgefunden')
        self.assertFalse(self.sidebar.cards)
        self.assertIn('Keine passenden Treffer.', [w.text() for w in self.sidebar.findChildren(QLabel)])
        self.sidebar.query.clear()
        self.assertFalse(self.sidebar.cards)

    def test_results_follow_moves_renames_and_pool_deletion(self):
        self.search('pfeifer')
        self.window.move('a', '')
        self.assertNotIn('Pool 01', self.card('participant', 'a').pool_links)
        self.window.change(lambda state: state.delete_pool('Pool 03'), 'Entfernt')
        self.assertNotIn('Pool 03', self.card('participant', 'a').pool_links)
        self.window.change(lambda state: setattr(state.participant('a'), 'last_name', 'Neu'), 'Name')
        self.assertNotIn(('participant', 'a'), self.sidebar.cards)

    def test_scrolls_to_selected_child_in_large_board(self):
        from devtools.demo_data import demo
        self.window.change(lambda state: state.__dict__.update(demo(100).__dict__), '100 Kinder')
        self.app.processEvents()
        pool = self.window.state.sorted_pools()[-1]
        person = self.window.state.participant(pool.members[-1])
        self.search(person.name)
        self.card('participant', person.id).pool_links[pool.id].click()
        self.app.processEvents()
        items = self.window.lists[pool.id]
        point = items.mapTo(self.window.scroll.viewport(), items.visualItemRect(items.currentItem()).center())
        self.assertTrue(self.window.scroll.viewport().rect().contains(point))
        self.assertGreater(self.window.scroll.verticalScrollBar().value(), 0)

    def test_notes_are_unique_complete_filter_independent_and_searchable(self):
        text = 'Trainer <fragen> & Rückmeldung\nNoch eine Zeile'
        self.mark('participant', 'a', text)
        self.mark('participant', 'd', '')
        self.mark('pool', 'Pool 02', 'Neue Liste bringen')
        self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData('single'))
        self.window.open_sidebar(True)
        self.assertEqual(len(self.sidebar.cards), 3)
        self.assertEqual(self.card('participant', 'a').note.text(), text)
        self.assertEqual(self.card('participant', 'd').note.text(), 'Notiz ergänzen …')
        self.assertEqual(self.window.sidebar_button.text(), 'Suche && Orga-Notizen · 3')
        self.search('rueckmeldung')
        self.assertEqual(list(self.sidebar.cards), [('participant', 'a')])
        self.search('Pool 02')
        self.assertEqual(set(self.sidebar.cards), {('participant', 'a'), ('pool', 'Pool 02')})
        self.sidebar.query.clear()
        self.sidebar.types.setCurrentIndex(2)
        self.assertEqual(list(self.sidebar.cards), [('pool', 'Pool 02')])
        self.sidebar.tabs.setCurrentIndex(0)
        self.search('mueller')
        self.assertIn(('participant', 'b'), self.sidebar.cards)

    def test_create_edit_cancel_empty_note_and_restart_without_print_changes(self):
        before = deepcopy(self.window.state)
        self.search('mueller')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Trainer sprechen\nMitbringen: <Liste>')
        card.save.click()
        self.assertEqual(Store(self.folder).load().participant('b').bookmark, 'Trainer sprechen\nMitbringen: <Liste>')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Verwerfen')
        card.cancel.click()
        self.assertNotIn('Verwerfen', self.card('participant', 'b').note.text())
        card = self.card('participant', 'b')
        QTest.mouseClick(card.note, Qt.MouseButton.LeftButton)
        card.editor.clear()
        card.save.click()
        self.assertEqual(Store(self.folder).load().participant('b').bookmark, '')
        self.assertEqual(self.window.state.pool('Pool 01').print_revision, before.pool('Pool 01').print_revision)
        self.assertEqual(self.window.state.pool_print_content('Pool 01'), before.pool_print_content('Pool 01'))

    def test_failed_save_keeps_editor_and_draft_and_can_retry(self):
        self.search('mueller')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Gebühr fehlt')
        with patch.object(self.window.store, 'save', side_effect=OSError('Datenträger voll')):
            card.save.click()
        self.assertIsNone(self.window.state.participant('b').bookmark)
        self.assertEqual(card.editor.toPlainText(), 'Gebühr fehlt')
        self.assertIn('Datenträger voll', self.sidebar.message.text())
        card.save.click()
        self.assertEqual(Store(self.folder).load().participant('b').bookmark, 'Gebühr fehlt')

    def test_drafts_survive_tabs_search_hide_and_external_refresh(self):
        self.search('mueller')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Entwurf')
        self.sidebar.close_button.click()
        self.window.open_sidebar(True)
        self.sidebar.query.clear()
        self.mark('pool', 'Pool 01', 'Andere Notiz')
        self.window.open_sidebar(False)
        self.search('mueller')
        self.assertEqual(self.card('participant', 'b').editor.toPlainText(), 'Entwurf')
        self.assertFalse(self.card('participant', 'b').editor.isHidden())

    def test_complete_and_undo_participant_and_pool_including_empty_note(self):
        for kind, entity_id, note in [('participant', 'a', ''), ('pool', 'Pool 02', 'Liste bringen')]:
            with self.subTest(kind=kind):
                self.mark(kind, entity_id, note)
                self.sidebar.query.clear()
                self.window.open_sidebar(True)
                before = deepcopy(self.window.state)
                self.card(kind, entity_id).done.click()
                entity = self.window.state.participant(entity_id) if kind == 'participant' else self.window.state.pool(entity_id)
                self.assertIsNone(entity.bookmark)
                self.assertNotIn((kind, entity_id), self.sidebar.cards)
                self.assertTrue(self.sidebar.undo_bar.isVisible())
                self.sidebar.undo_button.click()
                self.assertEqual(self.window.store.load(), before)
                self.assertIn((kind, entity_id), self.sidebar.cards)
                self.sidebar.clear_undo()
                self.assertIsNone(self.sidebar.undo_entry)

    def test_failed_complete_and_undo_do_not_lose_note(self):
        self.mark('participant', 'a', 'Trainer')
        self.window.open_sidebar(True)
        with patch.object(self.window.store, 'save', side_effect=OSError('Datenträger voll')):
            self.card('participant', 'a').done.click()
        self.assertEqual(self.window.state.participant('a').bookmark, 'Trainer')
        self.assertIn(('participant', 'a'), self.sidebar.cards)
        self.card('participant', 'a').done.click()
        with patch.object(self.window.store, 'save', side_effect=OSError('Datenträger voll')):
            self.sidebar.undo_button.click()
        self.assertIsNotNone(self.sidebar.undo_entry)
        self.sidebar.undo_button.click()
        self.assertEqual(self.window.state.participant('a').bookmark, 'Trainer')

    def test_stale_edits_and_undo_never_overwrite_new_notes(self):
        self.mark('participant', 'a', 'Alt')
        self.search('pfeifer')
        card = self.card('participant', 'a')
        card.edit.click()
        card.editor.setPlainText('Entwurf')
        self.mark('participant', 'a', 'Extern geändert')
        self.card('participant', 'a').save.click()
        self.assertEqual(self.window.state.participant('a').bookmark, 'Extern geändert')
        self.assertIn('inzwischen geändert', self.sidebar.message.text())
        self.card('participant', 'a').cancel.click()
        self.card('participant', 'a').done.click()
        self.mark('participant', 'a', 'Neu gesetzt')
        self.sidebar.undo_button.click()
        self.assertEqual(self.window.state.participant('a').bookmark, 'Neu gesetzt')
        self.assertIn('nicht überschrieben', self.sidebar.message.text())

    def test_add_entry_and_close_reopen(self):
        self.window.open_sidebar(True)
        self.sidebar.add.click()
        self.assertEqual(self.sidebar.tabs.currentIndex(), 0)
        self.assertTrue(self.sidebar.query.hasFocus())
        self.search('Pool 02')
        card = self.card('pool', 'Pool 02')
        card.edit.click()
        card.editor.setPlainText('Neue Liste')
        card.save.click()
        self.sidebar.close_button.click()
        self.assertTrue(self.sidebar.isHidden())
        self.window.open_sidebar(True)
        self.assertEqual(self.sidebar.tabs.currentIndex(), 1)
        self.assertEqual(self.card('pool', 'Pool 02').note.text(), 'Neue Liste')

    def test_close_and_folder_switch_resolve_drafts_and_clear_undo(self):
        self.search('mueller')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Entwurf')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(self.window.close())
        self.assertTrue(self.window.isVisible())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Save):
            self.assertTrue(self.sidebar.resolve_drafts())
        self.assertEqual(Store(self.folder).load().participant('b').bookmark, 'Entwurf')
        self.sidebar.complete(('participant', 'b'))
        with tempfile.TemporaryDirectory() as other:
            self.window.open_folder(Path(other))
            self.assertFalse(self.sidebar.drafts)
            self.assertIsNone(self.sidebar.undo_entry)
            self.assertEqual(self.window.sidebar_button.text(), 'Suche && Orga-Notizen · 0')
            self.window.open_folder(self.folder)

    def test_sidebar_resize_keeps_board_and_notes_accessible(self):
        self.mark('participant', 'a', 'Lange Notiz ' * 40)
        self.window.change(lambda state: setattr(state.pool('Pool 02'), 'name', 'Sehr langer Poolname ' * 2), 'Name')
        self.sidebar.query.clear()
        self.window.open_sidebar(True)
        for width in (1500, 1050):
            self.window.resize(width, 900)
            for _ in range(15):
                self.app.processEvents()
            self.assertEqual(self.window.scroll.horizontalScrollBar().maximum(), 0)
            self.assertEqual(self.sidebar.scroll.horizontalScrollBar().maximum(), 0)
            self.assertTrue(self.sidebar.rect().contains(self.sidebar.scroll.geometry()))
            self.assertTrue(self.card('participant', 'a').note.wordWrap())

    def test_navigation_preserves_note_scroll_and_expiry_disables_undo(self):
        self.window.change(lambda state: [setattr(p, 'bookmark', 'Lange Notiz ' * 20)
                                         for p in state.participants + state.pools], 'Notizen')
        self.window.open_sidebar(True)
        self.app.processEvents()
        bar = self.sidebar.scroll.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        position = bar.value()
        self.assertGreater(position, 0)
        self.card('participant', 'a').jump.click()
        self.app.processEvents()
        self.assertEqual(bar.value(), position)
        self.card('participant', 'a').done.click()
        expired = QSignalSpy(self.sidebar.undo_timer.timeout)
        self.sidebar.undo_timer.start(30)
        self.assertTrue(expired.wait(1000))
        self.assertIsNone(self.sidebar.undo_entry)
        self.assertTrue(self.sidebar.undo_bar.isHidden())

    def test_deleted_object_cannot_be_restored_by_undo(self):
        self.mark('pool', 'Pool 02', 'Trainer')
        self.sidebar.complete(('pool', 'Pool 02'))
        self.window.change(lambda state: state.delete_pool('Pool 02'), 'Entfernt')
        self.sidebar.undo_button.click()
        self.assertNotIn('Pool 02', [p.id for p in self.window.state.pools])
        self.assertIn('Nicht übernommen', self.sidebar.message.text())

    def test_failed_draft_save_blocks_folder_switch_and_discard_allows_it(self):
        self.search('mueller')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Entwurf')
        with tempfile.TemporaryDirectory() as other:
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Save), \
                 patch.object(self.window.store, 'save', side_effect=OSError('Datenträger voll')):
                self.window.open_folder(Path(other))
            self.assertEqual(self.window.folder, self.folder.resolve())
            self.assertEqual(self.card('participant', 'b').editor.toPlainText(), 'Entwurf')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Discard):
                self.window.open_folder(Path(other))
            self.assertEqual(self.window.folder, Path(other).resolve())
            self.assertFalse(self.sidebar.drafts)
            self.window.open_folder(self.folder)
        self.assertIsNone(self.window.state.participant('b').bookmark)

    def test_failed_folder_open_after_saving_leaves_working_editor(self):
        self.search('mueller')
        card = self.card('participant', 'b')
        card.edit.click()
        card.editor.setPlainText('Gespeichert vor Wechsel')
        with tempfile.TemporaryDirectory() as other:
            locked = Window(Path(other))
            try:
                with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Save):
                    with self.assertRaises(RuleError):
                        self.window.open_folder(Path(other))
            finally:
                locked.close()
        self.assertTrue(self.card('participant', 'b').editor.isHidden())
        self.card('participant', 'b').edit.click()
        self.card('participant', 'b').editor.setPlainText('Weiterarbeiten')
        self.card('participant', 'b').save.click()
        self.assertEqual(Store(self.folder).load().participant('b').bookmark, 'Weiterarbeiten')
