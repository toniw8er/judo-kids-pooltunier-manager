"""Teilnehmerbezogene Regelhinweise und gemeinsame Poolreihenfolge."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QHelpEvent, QImage, QMouseEvent, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QToolTip

from devtools.helpers import demo_window
from stadtmeisterschaft.domain import AgeClass, FightResult, Participant, Pool, RuleError, Tournament
from stadtmeisterschaft.output import draw_pool, write_pdf
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.pool_page import PoolPage
from stadtmeisterschaft.ui.main_window import MIME
from stadtmeisterschaft.ui.planning_details import class_text, participant_planning_text, pool_planning_notes


def display_state():
    return Tournament([
        Participant("a", "Anna", "Jung", "JC", 2019, "F", 20000),
        Participant("b", "Bea", "Jung", "JC", 2019, "F", 21000),
        Participant("c", "Clara", "Alt", "JC", 2015, "F", 18000),
        Participant("d", "Dora", "Leicht", "JC", 2019, "F", 19000),
        Participant("e", "Eva", "Klärfall", "JC", 2022, "F", 20000),
    ], [Pool("Pool 01", ["c"], age_class="A älter"),
        Pool("Pool 02", ["a", "b"], age_class="Z jünger"),
        Pool("Pool 03", ["d"], kind="friendship")],
        age_classes=[AgeClass("A älter", [2014, 2015]), AgeClass("Z jünger", [2018, 2019])],
        next_pool_number=4)


def visual_order(window):
    return [window.section_grids[key].itemAt(i).widget()
            for key in ("regular", "friendship") for i in range(window.section_grids[key].count())]


class PoolDisplayRulesTests(unittest.TestCase):
    def test_multiple_friendships_warn_and_refresh_after_removal(self):
        state = display_state()
        first = state.pool("Pool 03")
        second = state.pool(state.create_pool("friendship", "Weitere Gruppe"))
        second.members = ["d", "a"]
        self.assertIn(second.display_name, "\n".join(pool_planning_notes(state, first.id)))
        self.assertIn(first.display_name, "\n".join(pool_planning_notes(state, second.id)))
        self.assertFalse(any("Freundschaftspool" in note for note in state.pool_member_warnings(second.id, "a")))
        state.move("d", "", second.id)
        self.assertEqual(state.other_friendship_note("d", first.id), "")
        self.assertFalse(any("Freundschaftspool" in note for note in pool_planning_notes(state, first.id)))
        state.move("d", second.id)
        state.delete_pool(second.id)
        self.assertEqual(state.other_friendship_note("d", first.id), "")

    def test_unknown_year_marks_only_affected_child_even_without_fixed_class(self):
        state = display_state()
        state.move("e", "Pool 02")
        for actual_class in ["Z jünger", ""]:
            state.pool("Pool 02").age_class = actual_class
            self.assertIn("Keine passende Altersklasse", " ".join(state.pool_member_warnings("Pool 02", "e")))
            self.assertEqual(state.pool_member_warnings("Pool 02", "a"), [])
            self.assertEqual(state.pool_member_warnings("Pool 02", "b"), [])

    def test_year_outside_actual_class_and_pairwise_weight_and_gender_conflicts(self):
        state = display_state()
        state.move("c", "Pool 02")
        self.assertIn("Startklasse Z jünger", " ".join(state.pool_member_warnings("Pool 02", "c")))
        state.move("c", "Pool 01")
        state.participant("b").weight_grams = 22000
        self.assertEqual(state.pool_member_warnings("Pool 02", "a"), [])
        state.participant("b").weight_grams = 22100
        for pid in ["a", "b"]:
            self.assertIn("10 %", " ".join(state.pool_member_warnings("Pool 02", pid)))
        state.participant("b").weight_grams = 21000
        state.participant("b").gender = "M"
        self.assertTrue(all("Geschlechtermischung" in " ".join(state.pool_member_warnings("Pool 02", pid))
                            for pid in ["a", "b"]))
        state.age_classes[1].mixed = True
        self.assertEqual(state.pool_member_warnings("Pool 02", "a"), [])

    def test_sort_by_actual_years_then_both_weight_bounds_without_changing_ids_or_fights(self):
        state = display_state()
        state.pools.extend([Pool("Pool 04", ["e"]), Pool("Pool 05"),
                            Pool("Pool 06", ["b"], kind="friendship"),
                            Pool("Pool 07", ["a"], kind="friendship")])
        before = deepcopy(state.to_dict())
        self.assertEqual([p.id for p in state.sorted_pools()],
                         ["Pool 03", "Pool 07", "Pool 02", "Pool 06", "Pool 01", "Pool 04", "Pool 05"])
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(state.pool_weight_note("Pool 02"), "20,0–21,0 kg")
        self.assertEqual(state.pool_weight_note("Pool 05"), "")


class PlanningOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.window = demo_window(self.folder, 10)
        self.addCleanup(self.window.close)
        self.window.change(lambda state: state.__dict__.update(display_state().__dict__), "Szenario")

    def visible_ids(self):
        return {pid for pid, card in self.window.cards.items() if not card.isHidden()}

    def test_filters_are_view_only_keep_sort_order_and_clear_hidden_selection(self):
        before = deepcopy(self.window.state)
        self.window.lists["Pool 02"].item(0).setSelected(True)
        for key, expected in [("friendship", {"Pool 03"}), ("single", {"Pool 01"}),
                              ("regular", {"Pool 01", "Pool 02"}),
                              ("all", {"", "Pool 01", "Pool 02", "Pool 03"})]:
            self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData(key))
            self.assertEqual(self.visible_ids(), expected)
            displayed = visual_order(self.window)
            self.assertEqual(displayed, [self.window.cards[p.id] for kind in (False, True)
                                        for p in self.window.state.sorted_pools()
                                        if p.id in expected and p.is_friendship == kind])
        self.assertFalse(self.window.lists["Pool 02"].selectedItems())
        self.assertEqual(self.window.state, before)
        self.assertEqual(self.window.store.load(), before)
        self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData("single"))
        self.window.move("b", "")
        self.assertEqual(self.visible_ids(), {"Pool 01", "Pool 02"})
        self.window.pool_filter.setCurrentIndex(self.window.pool_filter.findData("friendship"))
        with patch("stadtmeisterschaft.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(self.folder / "p.pdf"), "")), \
             patch("stadtmeisterschaft.ui.main_window.write_pdf") as write:
            self.window.export_pdf()
            self.assertEqual([p.id for p in write.call_args.args[2]], [p.id for p in self.window.state.sorted_pools()])
        self.window.change(lambda state: state.delete_pool("Pool 03"), "Entfernt")
        self.assertEqual(self.visible_ids(), set())
        self.assertIn("Keine passenden Pools", self.window.filter_count.text())

    def test_sections_reflow_without_mixing_pool_types_or_changing_state(self):
        for _ in range(5):
            self.window.create_pool()
        self.window.show()
        self.window.resize(1050, 850)
        for _ in range(3):
            self.app.processEvents()
        before = deepcopy(self.window.state)
        narrow_columns = self.window.board_columns
        self.window.resize(1900, 1000)
        for _ in range(3):
            self.app.processEvents()
        self.assertGreater(self.window.board_columns, narrow_columns)
        for key, friend in [("regular", False), ("friendship", True)]:
            grid = self.window.section_grids[key]
            self.assertFalse(self.window.section_widgets[key].isHidden())
            actual = [grid.itemAt(i).widget() for i in range(grid.count())]
            self.assertEqual(actual, [self.window.cards[p.id] for p in before.sorted_pools()
                                      if p.is_friendship == friend])
            for i in range(grid.count()):
                self.assertEqual(grid.getItemPosition(i)[:2], divmod(i, self.window.board_columns))
        self.assertLess(self.window.cards[""].geometry().bottom(),
                        self.window.section_widgets["regular"].geometry().top())
        self.assertLess(self.window.section_widgets["regular"].geometry().bottom(),
                        self.window.section_widgets["friendship"].geometry().top())
        self.assertEqual(self.window.state, before)
        self.assertEqual(self.window.store.load(), before)

    def test_compact_rows_wrap_long_names_and_hints_without_internal_scrolling(self):
        self.window.change(lambda s: setattr(s.participant("a"), "last_name", "Sehr langer Name " * 7), "Name")
        self.window.move("e", "Pool 02")
        self.window.show()
        for _ in range(3):
            self.app.processEvents()
        items = self.window.lists["Pool 02"]
        normal = items.visualItemRect(items.item(1))
        long = items.visualItemRect(items.item(0))
        self.assertGreater(long.height(), normal.height())
        self.assertLess(normal.height(), 50)
        for i in range(items.count()):
            self.assertTrue(items.viewport().rect().contains(items.visualItemRect(items.item(i))))
        self.assertEqual(items.verticalScrollBar().maximum(), 0)
        self.assertEqual(items.horizontalScrollBar().maximum(), 0)
        self.assertIn("Hinweis: Altersklasse", items.item(2).text())
        self.assertIn("Sehr langer Name " * 7, items.item(0).text())

    def test_resize_keeps_all_rows_inside_cards_and_bookmark_visible(self):
        def prepare(state):
            state.participant("a").last_name = "von Bergmann-Langenfeld"
            state.participant("a").bookmark = "Am Eingang melden"
            state.move("a", "Pool 03")
        self.window.change(prepare, "Langer Name und Freundschaftsteilnahme")
        self.window.show()
        for width in (1900, 1050, 1500, 1050):
            with self.subTest(width=width):
                self.window.resize(width, 950)
                for _ in range(15):
                    self.app.processEvents()
                self.assertEqual(self.window.scroll.horizontalScrollBar().maximum(), 0)
                for pid, items in self.window.lists.items():
                    if items.isHidden():
                        continue
                    self.assertTrue(self.window.cards[pid].rect().contains(items.geometry()), pid)
                    self.assertEqual(items.verticalScrollBar().maximum(), 0, pid)
                    for i in range(items.count()):
                        self.assertTrue(items.viewport().rect().contains(items.visualItemRect(items.item(i))), pid)
        items = self.window.lists["Pool 02"]
        self.window.scroll.ensureWidgetVisible(items)
        self.app.processEvents()
        image = items.viewport().grab().toImage()
        scale = image.devicePixelRatio()
        self.assertEqual(image.pixelColor(round(12 * scale), round(12 * scale)).name(), "#7135ab")

    def test_collapsed_unassigned_strip_accepts_drop_and_expands_with_child(self):
        self.window.move("d", "Pool 02")
        self.window.move("e", "Pool 02")
        self.window.show()
        self.app.processEvents()
        self.assertFalse(self.window.headers[""].isChecked())
        self.assertTrue(self.window.lists[""].isHidden())
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"participant_id": "a", "source_pool_id": "Pool 02"}).encode())
        card = self.window.cards[""]
        enter = QDragEnterEvent(QPoint(4, 4), Qt.DropAction.MoveAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(card, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(4, 4), Qt.DropAction.MoveAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(card, drop)
        self.assertTrue(drop.isAccepted())
        self.assertNotIn("a", self.window.store.load().pool("Pool 02").members)
        self.assertTrue(self.window.headers[""].isChecked())
        self.assertEqual(self.window.lists[""].count(), 1)
        self.window.headers[""].click()
        self.window.refresh()
        self.assertTrue(self.window.lists[""].isHidden())
        self.assertIn("1", self.window.headers[""].text())

    def test_focused_participant_uses_full_row_selection_without_extra_frame(self):
        self.window.change(lambda state: setattr(state.participant('a'), 'bookmark', 'Trainer'), 'Notiz')
        items = self.window.lists['Pool 02']
        index = items.model().index(0, 0)
        images = []
        for selected, focused in ((True, False), (True, True), (False, False)):
            option = QStyleOptionViewItem()
            option.widget = items
            option.rect = QRect(0, 0, 600, 40)
            option.font = items.font()
            option.palette = items.palette()
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            if selected:
                option.state |= QStyle.StateFlag.State_Selected
            if focused:
                option.state |= QStyle.StateFlag.State_HasFocus
            image = QImage(600, 40, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            try:
                items.itemDelegate().paint(painter, option, index)
            finally:
                painter.end()
            images.append(image)
        self.assertEqual(images[0], images[1])
        self.assertNotEqual(images[0], images[2])

    def test_hover_and_tooltip_use_fixed_header_context_with_full_information(self):
        self.window.change(lambda state: setattr(state.participant("a"), "bookmark", "Am Eingang melden"), "Notiz")
        self.window.move("e", "Pool 02")
        self.window.show()
        items = self.window.lists["Pool 02"]
        self.window.scroll.ensureWidgetVisible(items)
        for _ in range(15):
            self.app.processEvents()
        height = self.window.context_info.height()
        point = items.visualItemRect(items.item(0)).center()
        move = QMouseEvent(QEvent.Type.MouseMove, QPointF(point), QPointF(items.viewport().mapToGlobal(point)),
                           Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(items.viewport(), move)
        self.app.processEvents()
        self.assertEqual(self.window.context_timer.interval(), 2000)
        QTest.qWait(200)
        self.assertEqual(self.window.context_info.toPlainText(), self.window.context_hint)
        # Weitere Bewegung im selben Element darf den Timer nicht neu starten.
        remaining = self.window.context_timer.remainingTime()
        self.app.sendEvent(items.viewport(), move)
        self.assertLessEqual(self.window.context_timer.remainingTime(), remaining)
        QTest.qWait(1900)
        context = self.window.context_info.toPlainText()
        self.assertIn("Anna Jung", context)
        self.assertIn("Jg. 2019", context)
        self.assertIn("20,0 kg", context)
        self.assertIn("JC", context)
        self.assertIn("Am Eingang melden", context)
        self.assertTrue(context.startswith("Anna Jung"))
        QToolTip.hideText()
        help_event = QHelpEvent(QEvent.Type.ToolTip, point, items.viewport().mapToGlobal(point))
        self.assertTrue(self.app.sendEvent(items.viewport(), help_event))
        self.assertFalse(QToolTip.isVisible())
        point = items.visualItemRect(items.item(2)).center()
        move = QMouseEvent(QEvent.Type.MouseMove, QPointF(point), QPointF(items.viewport().mapToGlobal(point)),
                           Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(items.viewport(), move)
        self.app.processEvents()
        self.assertEqual(self.window.context_info.toPlainText(), context)
        QTest.qWait(2100)
        self.assertIn("Eva Klärfall", self.window.context_info.toPlainText())
        self.assertIn("Keine passende Altersklasse", self.window.context_info.toPlainText())
        self.assertEqual(self.window.context_info.height(), height)
        self.window.refresh()
        self.assertEqual(self.window.context_info.toPlainText(), self.window.context_hint)

    def test_leaving_switching_and_refresh_cancel_pending_hover(self):
        self.window.show()
        self.app.processEvents()
        label = self.window.event_label
        point = QPoint(2, 2)
        help_event = QHelpEvent(QEvent.Type.ToolTip, point, label.mapToGlobal(point))
        self.app.sendEvent(label, help_event)
        self.assertTrue(self.window.context_timer.isActive())
        QTest.qWait(50)
        header = self.window.headers["Pool 02"]
        self.app.sendEvent(header, QHelpEvent(QEvent.Type.ToolTip, point, header.mapToGlobal(point)))
        self.assertIs(self.window.context_target[0], header)
        self.assertGreater(self.window.context_timer.remainingTime(), 1950)
        self.app.sendEvent(label, help_event)
        self.app.sendEvent(label, QEvent(QEvent.Type.Leave))
        self.assertFalse(self.window.context_timer.isActive())
        self.assertIsNone(self.window.context_target)
        self.app.sendEvent(label, help_event)
        self.window.lists["Pool 02"].setCurrentRow(0)
        self.assertFalse(self.window.context_timer.isActive())
        self.assertIn("Anna Jung", self.window.context_info.toPlainText())
        self.app.sendEvent(label, help_event)
        self.window.refresh()
        self.assertFalse(self.window.context_timer.isActive())
        self.assertEqual(self.window.context_info.toPlainText(), self.window.context_hint)

    def test_selection_and_general_help_are_available_in_header_without_popup(self):
        self.window.lists["Pool 02"].setCurrentRow(0)
        self.assertIn("Anna Jung", self.window.context_info.toPlainText())
        self.assertFalse(self.window.status_actions_widget.isHidden())
        label = self.window.event_label
        point = QPoint(2, 2)
        help_event = QHelpEvent(QEvent.Type.ToolTip, point, label.mapToGlobal(point))
        self.assertTrue(self.app.sendEvent(label, help_event))
        self.assertIn("Anna Jung", self.window.context_info.toPlainText())
        QTest.qWait(2100)
        self.assertIn(str(self.folder).casefold(), self.window.context_info.toPlainText().casefold())

    def test_age_details_prefer_actual_class_mark_fallback_and_use_event_year(self):
        state = self.window.state
        self.assertEqual(class_text(state, "c"), "A älter")
        self.assertEqual(class_text(state, "d"), "Z jünger (Jahrgang)")
        state.event_date = "2030-01-01"
        self.assertIn("15 Jahre im Wettkampfjahr", participant_planning_text(state, "c"))
        self.assertIn("Jg. 2015", participant_planning_text(state, "c"))
        state.age_classes.pop(0)
        self.assertIn("nicht mehr konfiguriert", class_text(state, "c"))
        self.assertEqual(class_text(state, "e"), "Klasse offen")
        state.event_date = ""
        self.assertNotIn("Jahre", participant_planning_text(state, "c"))

    def test_mixed_age_pool_names_children_classes_and_ages_without_repeated_generic_warning(self):
        self.window.move("c", "Pool 03")
        page = PoolPage(self.window, "Pool 03")
        try:
            self.assertIn("Clara Alt · A älter · Jg. 2015", page.members_context.text())
            self.assertIn("11 Jahre im Wettkampfjahr", page.members_context.text())
            self.assertIn("Dora Leicht · Z jünger (Jahrgang) · Jg. 2019", page.members_context.text())
            self.assertIn("Unterschiedliche Altersklassen:", page.warnings.summary.text())
            self.assertIn("A älter", page.warnings.summary.text())
            self.assertIn("Z jünger", page.warnings.summary.text())
            self.assertNotIn("keine gemeinsame", page.warnings.text().casefold())
            self.assertIn("Clara Alt", page.warnings.text())
        finally:
            page.close()

    def test_friendship_references_refresh_navigate_and_survive_restart(self):
        paper_revision = self.window.state.pool("Pool 01").print_revision
        self.assertIn("Einzelpool:", "\n".join(pool_planning_notes(self.window.state, "Pool 01")))
        self.window.move("c", "Pool 03")
        self.assertTrue(self.window.friendship_links["Pool 01"].labels)
        self.assertIn("Freundschaftskampf organisiert", self.window.friendship_links["Pool 01"].labels[0].text())
        self.assertNotIn("Einzelpool:", "\n".join(pool_planning_notes(self.window.state, "Pool 01")))
        page = PoolPage(self.window, "Pool 01")
        self.assertNotIn("Noch kein Partner", page.evaluation_label.text())
        self.assertEqual(self.window.state.pool("Pool 01").print_revision, paper_revision)
        page.pool_mat.setText("1")
        page.friendship_links.labels[0].linkActivated.emit("Pool 03")
        self.assertIsNone(page.next_pool_id)
        page.pool_mat.clear()
        page.friendship_links.labels[0].linkActivated.emit("Pool 03")
        self.assertEqual(page.next_pool_id, "Pool 03")
        self.window.remove_from_pool("d", "Pool 03")
        self.assertIn("angelegt · noch ohne Partner", self.window.friendship_links["Pool 01"].labels[0].text())
        self.assertIn("Einzelpool:", "\n".join(pool_planning_notes(self.window.state, "Pool 01")))
        self.window.open_folder(self.folder)
        self.assertTrue(self.window.friendship_links["Pool 01"].labels)
        self.window.change(lambda state: state.delete_pool("Pool 03"), "Entfernt")
        self.assertFalse(self.window.friendship_links["Pool 01"].labels)

    def test_all_friendship_references_follow_membership_changes(self):
        targets = []
        for partner in ["a", "b"]:
            self.window.change(lambda state: targets.append(state.add_friendship_partners("Pool 01", [partner])), "Zusätzliche Kämpfe")
        links = self.window.friendship_links["Pool 01"]
        self.assertEqual(len(links.labels), 2)
        for target in targets:
            self.assertTrue(any(target in label.text() for label in links.labels))
        self.window.remove_from_pool("c", targets[0])
        labels = self.window.friendship_links["Pool 01"].labels
        self.assertEqual(len(labels), 1)
        self.assertIn(targets[1], labels[0].text())
        self.window.change(lambda state: state.delete_pool(targets[1]), "Entfernt")
        self.assertFalse(self.window.friendship_links["Pool 01"].labels)


class PaperStandTests(unittest.TestCase):
    def test_print_changes_only_increment_affected_pool_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            state = display_state()
            store.save(state)
            for value, expected in [("2", 2), ("2", 2), ("", 3)]:
                state.save_pool("Pool 02", "", {}, mat=value)
                store.save(state)
                self.assertEqual([p.print_revision for p in state.pools], [1, expected, 1])
            state.participant("a").last_name = "Korrigiert"
            store.save(state)
            self.assertEqual([p.print_revision for p in state.pools], [1, 4, 1])
            state.participant("a").birth_year = 2018  # Kein gedruckter Inhalt.
            store.save(state)
            self.assertEqual(state.pool("Pool 02").print_revision, 4)
            state.event_date = "2026-12-01"
            store.save(state)
            self.assertEqual([p.print_revision for p in state.pools], [2, 5, 2])
            self.assertEqual(Store(Path(directory)).load(), state)
            state.save_pool("Pool 02", "", {"1": FightResult("1:0", 10, 7)})
            store.save(state)
            self.assertEqual(state.pool("Pool 02").print_revision, 6)
            # Ein fehlgeschlagener Commit darf die sichtbare Standnummer nicht ändern.
            state.pool("Pool 02").mat = "3"
            with store.connect() as con:
                con.execute("CREATE TRIGGER reject_update BEFORE UPDATE ON current_state "
                            "BEGIN SELECT RAISE(ABORT, 'voll'); END")
            with self.assertRaises(Exception):
                store.save(state)
            self.assertEqual(state.pool("Pool 02").print_revision, 6)
            self.assertEqual(Store(Path(directory)).load().pool("Pool 02").print_revision, 6)

    def test_print_content_contract_covers_visible_changes(self):
        base = display_state()
        for action in [
            lambda s: setattr(s, "name", "Neuer Wettkampf"),
            lambda s: setattr(s, "is_demo", True),
            lambda s: setattr(s.pool("Pool 02"), "name", "Gruppe A"),
            lambda s: setattr(s.pool("Pool 02"), "age_class", "Andere Klasse"),
            lambda s: setattr(s.pool("Pool 02"), "kind", "friendship"),
            lambda s: setattr(s.pool("Pool 02"), "completed", True),
            lambda s: s.pool("Pool 02").members.reverse(),
            lambda s: setattr(s.participant("a"), "club", "Neuer Verein"),
            lambda s: setattr(s.participant("a"), "withdrawn", True),
            lambda s: setattr(s.participant("a"), "disqualified", True),
            lambda s: setattr(s.participant("a"), "weight_grams", 19000),
        ]:
            state = deepcopy(base)
            action(state)
            self.assertNotEqual(base.pool_print_content("Pool 02"), state.pool_print_content("Pool 02"))

    def test_v0_to_v4_migrate_empty_mat_and_revision_one_and_validate_new_fields(self):
        for version in range(5):
            payload = display_state().to_dict() | {"schema_version": version}
            for pool in payload["pools"]:
                pool.pop("mat")
                pool.pop("print_revision")
            loaded = Tournament.from_dict(payload)
            self.assertTrue(all(p.mat == "" and p.print_revision == 1 for p in loaded.pools))
        for field, values in [("mat", [None, 2]), ("print_revision", [0, -1, True, "2"])]:
            for value in values:
                state = display_state()
                setattr(state.pools[0], field, value)
                with self.subTest(field=field, value=value), self.assertRaises(RuleError):
                    state.validate()


class PoolDisplayUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fight_labels_show_weights_and_only_current_pair_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            window = demo_window(Path(directory), 10)
            try:
                def prepare(state):
                    state.__dict__.update(display_state().__dict__)
                    state.move("c", "Pool 02")
                    state.participant("c").birth_year = 2019
                    state.participant("c").weight_grams = 23100
                window.change(prepare, "Paarweise Hinweise")
                page = PoolPage(window, "Pool 02")
                first, second = page.name_labels[:2]
                for label, _, _ in [first, second]:
                    self.assertIn("kg", label.text())
                    self.assertNotIn("Hinweis", label.text())
                    self.assertNotIn("Clara Alt", label.toolTip())
                label, pid, opponent = page.name_labels[2]
                self.assertEqual((pid, opponent), ("a", "c"))
                self.assertIn("Hinweis", label.text())
                self.assertIn("3,1 kg leichter (−15,5 %)", label.toolTip())
                self.assertNotIn("Bea Jung", label.toolTip())
                page.close()
            finally:
                window.close()

    def test_mat_edit_export_guard_failure_clear_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            window = demo_window(Path(directory), 10)
            self.addCleanup(window.close)
            window.change(lambda s: s.save_pool("Pool 03", "", {
                "1": FightResult("1:0", 10, 0), "2": FightResult("1:0", 10, 0)}), "Ergebnisse")
            window.change(lambda s: s.complete_pool("Pool 03"), "Abschluss")
            page = PoolPage(window, "Pool 03")
            before = deepcopy(window.state.pool("Pool 03"))
            page.pool_mat.setText(" Halle A ")
            self.assertFalse(page._can_export())
            with patch.object(window.store, "save", side_effect=OSError("voll")):
                self.assertFalse(page.save())
            self.assertEqual(window.state.pool("Pool 03"), before)
            self.assertEqual(page.pool_mat.text(), " Halle A ")
            self.assertTrue(page.save())
            saved = window.state.pool("Pool 03")
            self.assertEqual(saved.mat, "Halle A")
            self.assertTrue(saved.completed)
            self.assertEqual(saved.results, before.results)
            self.assertEqual(saved.members, before.members)
            self.assertEqual(saved.print_revision, before.print_revision + 1)
            self.assertIn("Matte: Halle A", window.pool_details[saved.id].text())
            self.assertIn(f"Papierstand {saved.print_revision}", page.pool_note.text())
            self.assertEqual(Store(Path(directory)).load().pool(saved.id), saved)
            page.pool_mat.clear()
            self.assertTrue(page.save())
            self.assertNotIn("Matte:", window.pool_details[saved.id].text())
            self.assertEqual(Store(Path(directory)).load().pool(saved.id).mat, "")
            page.close()
            window.close()

    def test_mat_and_small_footer_in_shared_drawing_and_export_is_read_only(self):
        state = display_state()
        state.pool("Pool 02").mat = "2"
        state.pool("Pool 02").print_revision = 3
        image = QImage(1100, 740, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        drawn = []

        class RecordingPainter:
            def __getattr__(self, name):
                return getattr(painter, name)

            def drawText(self, rect, flags, text):
                drawn.append((rect, text, painter.font().pixelSize(), painter.pen().color().name()))
                painter.drawText(rect, flags, text)

        try:
            draw_pool(RecordingPainter(), QRectF(0, 0, 1100, 740), state, state.pool("Pool 02"),
                      created_at=datetime(2026, 11, 19, 10, 42, 3))
        finally:
            painter.end()
        self.assertTrue(any(text == "Matte: 2" for _, text, _, _ in drawn))
        self.assertEqual([text for _, text, _, _ in drawn if "kg" in text], ["20,0 - 21,0 kg"])
        self.assertFalse(any("⚠" in text or "Regelhinweis" in text for _, text, _, _ in drawn))
        self.assertFalse(any("Jg." in text or "Jahre im Wettkampfjahr" in text
                             or "organisiert" in text for _, text, _, _ in drawn))
        footer = next(item for item in drawn if item[1].startswith("Stand 3"))
        self.assertEqual(footer[1], "Stand 3 · erstellt am 19.11.2026, 10:42:03")
        self.assertGreaterEqual(footer[0].y(), 690)
        self.assertLessEqual(footer[2], 11)
        self.assertEqual(footer[3], "#555555")
        before = deepcopy(state)
        with tempfile.TemporaryDirectory() as directory:
            write_pdf(Path(directory) / "a.pdf", state, state.sorted_pools())
            write_pdf(Path(directory) / "b.pdf", state, state.sorted_pools())
        self.assertEqual(state, before)

    def test_markers_refresh_sorting_export_and_reload(self):
        root = Path(__file__).resolve().parents[1] / "tmp" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            window = demo_window(Path(directory), 10)
            self.addCleanup(window.close)
            window.change(lambda state: state.__dict__.update(display_state().__dict__), "Szenario")

            def ordered_ids():
                return [pid for card in visual_order(window) for pid, candidate in window.cards.items()
                        if candidate is card]

            self.assertEqual(ordered_ids(), ["Pool 02", "Pool 01", "Pool 03"])
            window.move("e", "Pool 02")
            marked = next(window.lists["Pool 02"].item(i) for i in range(3)
                          if window.lists["Pool 02"].item(i).data(Qt.ItemDataRole.UserRole) == "e")
            self.assertIn("Hinweis: Altersklasse", marked.text())
            self.assertEqual(marked.background().color().name(), "#edf4f8")
            self.assertIn("Keine passende Altersklasse", marked.toolTip())
            page = PoolPage(window, "Pool 02")
            eva = next(label for label, pid, opponent in page.name_labels if pid == "e")
            self.assertIn("20,0 kg", eva.text())
            self.assertIn("Hinweis", eva.text())
            self.assertNotIn("Regelhinweis:", eva.text())
            self.assertIn("Keine passende Altersklasse", eva.toolTip())
            self.assertTrue(page.warnings.scroll.isHidden())
            page.warnings.toggle.click()
            self.assertFalse(page.warnings.scroll.isHidden())
            self.assertIn("Eva Klärfall", page.warnings.details.text())
            page.close()
            window.move("e", "")
            self.assertTrue(all("Hinweis:" not in window.lists["Pool 02"].item(i).text() for i in range(2)))
            window.move("a", "Pool 03")
            self.assertEqual(ordered_ids(), ["Pool 02", "Pool 01", "Pool 03"])
            # Entfernen aus Freundschaftspool verändert dessen untere Gewichtsgrenze.
            window.remove_from_pool("d", "Pool 03")
            window.change(lambda state: setattr(state.participant("a"), "weight_grams", 23000), "Gewicht")
            self.assertEqual(ordered_ids(), ["Pool 02", "Pool 01", "Pool 03"])
            with patch("stadtmeisterschaft.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(Path(directory) / "p.pdf"), "")), \
                 patch("stadtmeisterschaft.ui.main_window.write_pdf") as write:
                window.export_pdf()
                self.assertEqual([p.id for p in write.call_args.args[2]],
                                 [p.id for p in window.state.sorted_pools()])
            window.open_folder(Path(directory))
            self.assertEqual(ordered_ids(), [p.id for friend in (False, True)
                                            for p in Store(Path(directory)).load().sorted_pools()
                                            if p.is_friendship == friend])
            window.close()


if __name__ == "__main__":
    unittest.main()
