"""Speicherung, Migration und Bedienung interner Lesezeichen."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QPushButton

from devtools.demo_data import demo
from devtools.helpers import demo_window, record_result
from stadtmeisterschaft.domain import AgeClass, RuleError, Tournament
from stadtmeisterschaft.sheets import read_participants, write_ods
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.bookmarks import BookmarkDialog
from stadtmeisterschaft.ui.friendship_search import FriendshipSearch
from stadtmeisterschaft.ui.pool_page import PoolPage


class BookmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'tmp' / 'tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.temp.name)
        self.window = demo_window(self.folder, 10)
        self.pid = self.window.state.pool('Pool 01').members[0]

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def test_note_edit_remove_and_restart(self):
        for kind, entity_id in [('participant', self.pid), ('pool', 'Pool 01')]:
            dialog = BookmarkDialog(self.window, kind, entity_id)
            dialog.note.setPlainText('Gebühr fehlt.\nTrainer <fragen> & Rückmeldung abwarten.')
            dialog.save()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            loaded = Store(self.folder).load()
            entity = loaded.participant(self.pid) if kind == 'participant' else loaded.pool(entity_id)
            self.assertEqual(entity.bookmark, dialog.note.toPlainText())
            dialog = BookmarkDialog(self.window, kind, entity_id)
            dialog.note.setPlainText('')
            dialog.save()
            self.assertEqual(dialog.entity(Store(self.folder).load()).bookmark, '')
            dialog = BookmarkDialog(self.window, kind, entity_id)
            dialog.save(remove=True)
            self.assertIsNone(dialog.entity(Store(self.folder).load()).bookmark)

    def test_cancel_and_failed_save_keep_state_and_input(self):
        before = self.window.state.to_dict()
        dialog = BookmarkDialog(self.window, 'participant', self.pid)
        dialog.note.setPlainText('Nicht bezahlt')
        with patch.object(self.window.store, 'save', side_effect=OSError('Datenträger voll')):
            dialog.save()
        self.assertEqual(self.window.state.to_dict(), before)
        self.assertEqual(dialog.note.toPlainText(), 'Nicht bezahlt')
        self.assertIn('Datenträger voll', dialog.message.text())
        dialog.save()
        self.assertEqual(self.window.state.participant(self.pid).bookmark, 'Nicht bezahlt')
        dialog = BookmarkDialog(self.window, 'participant', self.pid)
        dialog.note.setPlainText('Verwerfen')
        dialog.reject()
        self.assertEqual(Store(self.folder).load().participant(self.pid).bookmark, 'Nicht bezahlt')

    def test_all_older_versions_have_no_bookmarks(self):
        for version in range(6):
            with self.subTest(version=version):
                payload = demo(10).to_dict()
                payload['schema_version'] = version
                for item in payload['participants'] + payload['pools']:
                    item.pop('bookmark')
                state = Tournament.from_dict(payload)
                self.assertTrue(all(p.bookmark is None for p in state.participants + state.pools))
                self.assertEqual(state.to_dict()['schema_version'], 6)

    def test_invalid_notes_are_rejected(self):
        for collection in ['participants', 'pools']:
            for value in [False, 3, [], {}]:
                payload = demo(10).to_dict()
                payload[collection][0]['bookmark'] = value
                with self.subTest(collection=collection, value=value), self.assertRaises(RuleError):
                    Tournament.from_dict(payload)

    def test_ods_reload_keeps_note_and_omits_it_from_sheet(self):
        self.window.change(lambda state: setattr(state.participant(self.pid), 'bookmark', 'INTERN_GEHEIM'), '')
        self.window.session.reload_participants()
        people = read_participants(self.window.store.participant_path, with_ids=True)
        people[0].club = 'Neuer Verein'
        write_ods(self.window.store.participant_path, people)
        state = self.window.session.reload_participants()
        self.assertEqual(state.participant(self.pid).bookmark, 'INTERN_GEHEIM')
        self.assertTrue(all(p.bookmark is None for p in read_participants(self.window.store.participant_path, with_ids=True)))

    def test_notes_have_no_print_effect_even_after_pool_start(self):
        self.window.change(lambda state: record_result(state, 'Pool 01', 'Erstes Kind', 10, 0), '')
        before = deepcopy(self.window.state)
        for kind, entity_id in [('participant', self.pid), ('pool', 'Pool 01')]:
            dialog = BookmarkDialog(self.window, kind, entity_id)
            dialog.note.setPlainText('Interne Absprache')
            dialog.save()
        for pool in before.pools:
            self.assertEqual(before.pool_print_content(pool.id), self.window.state.pool_print_content(pool.id))
            self.assertEqual(pool.print_revision, self.window.state.pool(pool.id).print_revision)
        self.assertTrue(self.window.state.pool('Pool 01').started)

    def test_filter_includes_marked_pools_and_members_and_unassigned(self):
        self.window.change(lambda state: setattr(state.participant(self.pid), 'bookmark', ''), '')
        self.window.bookmarks_only.setChecked(True)
        self.assertFalse(self.window.cards['Pool 01'].isHidden())
        self.assertTrue(self.window.cards['Pool 02'].isHidden())
        self.window.change(lambda state: setattr(state.pool('Pool 02'), 'bookmark', 'Trainer fragen'), '')
        self.assertFalse(self.window.cards['Pool 02'].isHidden())
        self.window.move(self.pid, '', 'Pool 01')
        self.assertFalse(self.window.cards[''].isHidden())
        self.assertTrue(self.window.cards['Pool 01'].isHidden())
        self.assertEqual(self.window.lists[''].count(), 1)
        self.assertFalse(self.window.lists[''].item(0).isHidden())
        self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData('friendship'))
        self.assertTrue(all(card.isHidden() for card in self.window.cards.values()))

    def context_menu(self, widget, point=None, trigger=True):
        point = point or widget.rect().center()
        labels = []
        def choose():
            menu = QApplication.activePopupWidget()
            if isinstance(menu, QMenu):
                labels.extend(action.text() for action in menu.actions())
                if trigger:
                    menu.actions()[0].trigger()
                menu.close()
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, widget.mapToGlobal(point))
        QTimer.singleShot(0, choose)
        QApplication.sendEvent(widget, event)
        self.assertTrue(event.isAccepted())
        return labels

    def test_right_click_anywhere_in_child_targets_clicked_child(self):
        self.window.show()
        items = self.window.lists['Pool 01']
        self.window.scroll.ensureWidgetVisible(items)
        self.app.processEvents()
        items.setCurrentRow(0)
        second = items.item(1)
        pid = second.data(Qt.ItemDataRole.UserRole)
        rect = items.visualItemRect(second)
        with patch.object(self.window, 'edit_bookmark') as edit:
            labels = self.context_menu(items.viewport(), QPoint(rect.right()-10, rect.center().y()))
            self.assertEqual(labels, ['Lesezeichen setzen'])
            edit.assert_called_once_with('participant', pid, self.window)
        self.assertEqual(items.currentItem(), second)
        self.assertIn(pid, self.window.state.pool('Pool 01').members)
        with patch.object(self.window, 'edit_bookmark') as edit:
            QTest.mouseClick(items.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            edit.assert_not_called()

    def test_pool_context_menu_on_card_heading_details_and_empty_list(self):
        friend = self.window.create_pool('friendship')
        self.window.show()
        self.app.processEvents()
        for widget in [self.window.cards[friend], self.window.headers[friend],
                       self.window.pool_details[friend], self.window.lists[friend].viewport()]:
            with self.subTest(widget=widget), patch.object(self.window, 'edit_bookmark') as edit:
                self.assertEqual(self.context_menu(widget), ['Lesezeichen setzen'])
                edit.assert_called_once_with('pool', friend, self.window)
        self.window.change(lambda state: setattr(state.pool(friend), 'bookmark', 'Trainer fragen'), '')
        with patch.object(self.window, 'edit_bookmark') as edit:
            self.assertEqual(self.context_menu(self.window.headers[friend], trigger=False), ['Lesezeichen bearbeiten'])
            edit.assert_not_called()
        self.assertEqual(self.window.state.pool(friend).bookmark, 'Trainer fragen')

    def test_unmarked_objects_have_no_icons_or_bookmark_controls_in_overview(self):
        for items in self.window.lists.values():
            self.assertTrue(all(items.item(i).icon().isNull() for i in range(items.count())))
        self.assertTrue(all(self.window.headers[p.id].icon().isNull() for p in self.window.state.pools))
        self.assertFalse(any('Lesezeichen' in button.text() for button in self.window.findChildren(QPushButton)
                             if not self.window.sidebar.isAncestorOf(button)))
        self.window.change(lambda state: setattr(state.participant(self.pid), 'bookmark', ''), '')
        item = self.window.lists['Pool 01'].item(0)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.background(), self.window.lists['Pool 01'].item(1).background())

    def test_friendship_detail_has_one_pool_action_and_participant_context_menus(self):
        friend = self.window.create_pool('friendship')
        self.window.move(self.pid, friend)
        self.window.move(self.window.state.pool('Pool 01').members[1], friend)
        page = PoolPage(self.window, friend)
        page.show()
        self.app.processEvents()
        buttons = [button for button in page.findChildren(QPushButton) if 'Lesezeichen' in button.text()]
        self.assertEqual(buttons, [page.bookmark_button])
        self.assertTrue(page.bookmark_button.icon().isNull())
        with patch.object(self.window, 'edit_bookmark') as edit:
            self.context_menu(page.heading)
            edit.assert_called_once_with('pool', friend, page)
        for widget, point in [(page.members_context.labels[0], None),
                              (page.name_labels[0][0], None),
                              (page.participant_choice, None),
                              (page.standings.viewport(), page.standings.visualItemRect(page.standings.item(0, 0)).center())]:
            with self.subTest(widget=widget), patch.object(self.window, 'edit_bookmark') as edit:
                self.context_menu(widget, point)
                edit.assert_called_once_with('participant', self.pid, page)
        page.close()

    def test_pool_page_keeps_unsaved_inputs_when_editing_note(self):
        page = PoolPage(self.window, 'Pool 01')
        page.pool_name.setText('Noch nicht gespeichert')
        page.editors[0][0].setCurrentIndex(1)
        signature = page._signature()
        def edit(kind, entity_id, parent):
            dialog = BookmarkDialog(self.window, kind, entity_id, parent)
            dialog.note.setPlainText('Trainer fragen')
            dialog.save()
        with patch.object(self.window, 'edit_bookmark', side_effect=edit):
            page.edit_bookmark('participant', self.pid)
        self.assertEqual(page._signature(), signature)
        self.assertTrue(page.participant_choice.itemIcon(0).isNull())
        self.assertIn('Trainer fragen', page.standings.item(0, 0).toolTip())
        self.assertTrue(page.standings.item(0, 0).icon().isNull())
        page.pool_name.setText(self.window.state.pool('Pool 01').name)
        page._load_results()
        page.close()

    def test_friendship_search_note_edit_preserves_selection(self):
        self.window.change(lambda state: state.configure(state.name, state.event_date,
            [AgeClass('Testklasse', list(range(2000, 2030)), True)]), '')
        friend = self.window.create_pool('friendship')
        self.window.move(self.pid, friend)
        page = FriendshipSearch(self.window, friend)
        partner = page.table.item(0, 0).data(256)
        self.assertTrue(page.table.item(0, 0).icon().isNull())
        with patch.object(self.window, 'edit_bookmark') as edit:
            self.context_menu(page.table.viewport(), page.table.visualItemRect(page.table.item(0, 2)).center())
            edit.assert_called_once_with('participant', partner, page)
        page.add_partner(partner)
        selected = list(page.selected)
        with patch.object(self.window, 'edit_bookmark') as edit:
            page.edit_bookmark(self.pid)
            edit.assert_called_once_with('participant', self.pid, page)
        self.assertEqual(page.selected, selected)
        page.reject()
