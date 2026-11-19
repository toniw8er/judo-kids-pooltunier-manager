"""Poolverwaltung, zusätzliche Teilnahmen und explizite Altersklassenkonfiguration."""
from devtools.demo_data import demo
from devtools.helpers import demo_window, record_result
from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QDate, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from stadtmeisterschaft.ui.main_window import MIME
from stadtmeisterschaft.domain import AgeClass, FightResult, RuleError, Tournament, format_years, parse_years
from stadtmeisterschaft.ui.pool_page import PoolPage
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.tournament_config import TournamentConfig


class PoolManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "tmp" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.temp.name)
        self.state = demo(10)
        for i, child in enumerate(self.state.participants[:3]):
            child.birth_year = 2016
            child.weight_grams = 25000 + i * 100
        self.child = self.state.pools[0].members[0]

    def tearDown(self):
        self.temp.cleanup()

    def test_deleted_pool_number_is_reused_after_restart(self):
        self.assertNotIn("Reserve", [pool.id for pool in self.state.pools])
        first = self.state.create_pool(name="Manuell")
        self.state.delete_pool(first)
        Store(self.folder).save(self.state)
        loaded = Store(self.folder).load()
        second = loaded.create_pool("friendship", "Freunde")
        self.assertEqual(first, second)
        self.assertTrue(loaded.pool(second).is_friendship)
        self.assertEqual(loaded.pool(second).name, "Freunde")

    def test_smallest_gap_is_used_across_pool_kinds_despite_old_counter(self):
        self.state.create_pool("friendship", "Freunde")
        self.state.next_pool_number = 900
        self.state.delete_pool("Pool 02")
        self.state.delete_pool("Pool 01")
        before = deepcopy(self.state.pools)
        self.assertEqual(self.state.create_pool(), "Pool 01")
        self.assertEqual(self.state.create_pool("friendship"), "Pool 02")
        self.assertEqual(self.state.create_pool(), "Pool 05")
        self.assertEqual(self.state.pools[:2], before)

    def test_deleting_regular_pool_preserves_children_and_friendships(self):
        friend = self.state.create_pool("friendship")
        self.state.move(self.child, friend)
        self.state.delete_pool("Pool 01")
        self.assertIn(self.child, self.state.pool(friend).members)
        self.assertIn(self.child, [p.id for p in self.state.participants])
        self.assertFalse(any(self.child in p.members for p in self.state.pools if not p.is_friendship))
        self.state.validate()

    def test_friendships_are_additional_and_independently_removable(self):
        first = self.state.create_pool("friendship")
        second = self.state.create_pool("friendship")
        self.state.move(self.child, first, "Pool 01")
        self.state.move(self.child, second, first)
        self.assertIn(self.child, self.state.pool("Pool 01").members)
        self.state.move(self.child, "", first)
        self.assertNotIn(self.child, self.state.pool(first).members)
        self.assertIn(self.child, self.state.pool(second).members)
        self.assertIn(self.child, self.state.pool("Pool 01").members)
        self.state.delete_pool(second)
        self.assertIn(self.child, self.state.pool("Pool 01").members)
        self.state.validate()

    def test_friendship_copy_does_not_change_started_source(self):
        record_result(self.state, "Pool 01", "Erstes Kind", 10, 0)
        before = self.state.pool("Pool 01").__dict__.copy()
        friend = self.state.create_pool("friendship")
        self.state.move(self.child, friend, "Pool 01")
        self.assertEqual(self.state.pool("Pool 01").__dict__, before)

    def test_friendship_results_are_independent_of_regular_results(self):
        record_result(self.state, "Pool 01", "Erstes Kind", 10, 0)
        friend = self.state.create_pool("friendship")
        for child in self.state.pools[0].members[:2]:
            self.state.move(child, friend)
        self.state.save_pool(friend, "Freunde", {"1": FightResult("0:1", 5, 10)})
        Store(self.folder).save(self.state)
        loaded = Store(self.folder).load()
        self.assertEqual(loaded.pool("Pool 01").results["1"], FightResult("1:0", 10, 0))
        self.assertEqual(loaded.pool(friend).results["1"], FightResult("0:1", 5, 10))

    def test_started_friendship_cannot_be_removed_or_deleted(self):
        friend = self.state.create_pool("friendship")
        for child in self.state.pools[0].members[:2]:
            self.state.move(child, friend)
        self.state.save_pool(friend, "Freunde", {"1": FightResult("1:0", 10, 5)})
        before = self.state.to_dict()
        with self.assertRaises(RuleError):
            self.state.move(self.child, "", friend)
        with self.assertRaises(RuleError):
            self.state.delete_pool(friend)
        with self.assertRaises(RuleError):
            self.state.move(self.state.pools[0].members[2], friend)
        self.assertEqual(self.state.to_dict(), before)
        self.state.save_pool(friend, "Freunde", {})
        with self.assertRaises(RuleError):
            self.state.delete_pool(friend)

    def test_friendship_limit_and_duplicate_rejection_are_atomic(self):
        friend = self.state.create_pool("friendship")
        for child in self.state.participants[:5]:
            self.state.move(child.id, friend)
        before = self.state.to_dict()
        for child in [self.child, self.state.participants[5].id]:
            with self.assertRaises(RuleError):
                self.state.move(child, friend)
        self.assertEqual(self.state.to_dict(), before)

    def test_regular_moves_preserve_friendship_and_unique_regular_membership(self):
        friend = self.state.create_pool("friendship")
        regular = self.state.create_pool()
        self.state.move(self.child, friend)
        self.state.move(self.child, regular, friend)
        self.assertIn(self.child, self.state.pool(friend).members)
        self.assertNotIn(self.child, self.state.pool("Pool 01").members)
        self.assertIn(self.child, self.state.pool(regular).members)
        self.state.validate()

    def test_invalid_pool_kind_and_duplicate_members_rejected(self):
        before = self.state.to_dict()
        with self.assertRaises(RuleError):
            self.state.create_pool("unknown")
        self.assertEqual(before, self.state.to_dict())
        self.state.pools[0].members.append(self.child)
        with self.assertRaises(RuleError):
            self.state.validate()

    def test_old_snapshots_load_with_regular_pools_and_no_assumed_rules(self):
        payload = self.state.to_dict()
        del payload["age_classes"]
        del payload["next_pool_number"]
        for pool in payload["pools"]:
            del pool["kind"]
        loaded = Tournament.from_dict(payload)
        self.assertEqual(loaded.age_classes, [])
        self.assertTrue(all(not pool.is_friendship for pool in loaded.pools))
        self.assertEqual(loaded.create_pool(), "Pool 04")

    def test_year_lists_and_ranges_roundtrip_without_silent_reversal(self):
        years = parse_years("2014, 2016–2018; 2016")
        self.assertEqual(years, [2014, 2016, 2017, 2018])
        self.assertEqual(parse_years(format_years(years)), years)
        for text in ["", "2018-2016", "2016.5", "2016,", "1800-2026", "2016 2017"]:
            with self.subTest(text=text), self.assertRaises(RuleError):
                parse_years(text)

    def test_configuration_persists_overlapping_years_and_mixed_flags(self):
        classes = [AgeClass("U11", [2016, 2017, 2018], True), AgeClass("U13", [2014, 2015, 2016])]
        self.state.configure("Wettkampf", "2026-11-18", classes)
        friend = self.state.create_pool("friendship")
        self.state.move(self.child, friend)
        Store(self.folder).save(self.state)
        loaded = Store(self.folder).load()
        self.assertEqual(loaded.age_classes, classes)
        self.assertEqual(loaded.to_dict(), self.state.to_dict())
        self.assertEqual([c.name for c in loaded.common_age_classes("Pool 01")], ["U11", "U13"])
        self.assertEqual(loaded.pool_warnings("Pool 01"), [])

    def test_configuration_changes_recalculate_warnings_without_changing_results(self):
        record_result(self.state, "Pool 01", "Erstes Kind", 10, 0)
        before = self.state.to_dict()["pools"]
        self.state.configure("Wettkampf", "2026-11-18", [AgeClass("U11", [2016], False)])
        self.assertTrue(any("Mädchen/Jungen" in text for text in self.state.pool_warnings("Pool 01")))
        self.state.configure("Wettkampf", "2026-11-18", [AgeClass("U11", [2016], True)])
        self.assertEqual(self.state.pool_warnings("Pool 01"), [])
        self.state.configure("Wettkampf", "2026-11-18", [AgeClass("U8", [2019, 2020], True)])
        self.assertIn("Keine gemeinsame", self.state.pool_warnings("Pool 01")[0])
        self.assertEqual(self.state.to_dict()["pools"], before)

    def test_invalid_age_configuration_leaves_previous_configuration_unchanged(self):
        before = self.state.to_dict()
        for classes in [[AgeClass("U11", [])], [AgeClass("U11", [2016]), AgeClass("u11", [2017])]]:
            with self.assertRaises(RuleError):
                self.state.configure("Nicht übernehmen", "2026-11-18", classes)
            self.assertEqual(self.state.to_dict(), before)

    def test_weight_warning_uses_exact_ten_percent_boundary(self):
        pool = self.state.pools[0]
        pool.members = pool.members[:2]
        self.state.participant(pool.members[0]).weight_grams = 10000
        self.state.participant(pool.members[1]).weight_grams = 11000
        self.assertEqual(self.state.pool_warnings(pool.id), [])
        self.state.participant(pool.members[1]).weight_grams = 11100
        self.assertIn("10-Prozent", self.state.pool_warnings(pool.id)[0])

    def test_failed_configuration_save_preserves_table_for_retry(self):
        window = demo_window(self.folder, 10)
        dialog = TournamentConfig(window)
        dialog.add_class(AgeClass("U11", [2016, 2017], True))
        with patch.object(window.store, "save", side_effect=OSError("Datenträger voll")):
            dialog.save()
        self.assertEqual(window.state.age_classes, [])
        self.assertIn("Nicht übernommen", dialog.message.text())
        self.assertEqual(dialog.classes.item(0, 0).text(), "U11")
        dialog.save()
        self.assertEqual(Store(self.folder).load().age_classes, [AgeClass("U11", [2016, 2017], True)])
        window.close()

    def test_config_dialog_saves_table_and_rejects_invalid_range(self):
        window = demo_window(self.folder, 10)
        dialog = TournamentConfig(window)
        dialog.add_class(AgeClass("U11", [2016, 2017], True))
        dialog.name.setText("Stadtmeisterschaft")
        dialog.event_date.setDate(QDate(2026, 11, 18))
        dialog.classes.item(0, 1).setText("2018-2016")
        dialog.save()
        self.assertIn("aufsteigend", dialog.message.text())
        self.assertEqual(window.state.age_classes, [])
        dialog.classes.item(0, 1).setText("2016-2018")
        dialog.save()
        self.assertEqual(Store(self.folder).load().age_classes, [AgeClass("U11", [2016, 2017, 2018], True)])
        window.close()

    def test_ui_create_delete_and_cancel_preserve_participants(self):
        window = demo_window(self.folder, 10)
        labels = {button.text(): button for button in window.findChildren(QPushButton)}
        labels["Freundschaftspool anlegen"].click()
        friend = window.state.pools[-1]
        self.assertTrue(friend.is_friendship)
        self.assertIn("Freundschaftskampf", window.headers[friend.id].text())
        window.move(window.state.participants[0].id, friend.id)
        before = window.state.to_dict()
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
            self.assertFalse(window.delete_pool(friend.id))
        self.assertEqual(window.state.to_dict(), before)
        page = PoolPage(window, friend.id)
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
            page.delete_pool()
        self.assertNotIn(friend.id, window.headers)
        self.assertEqual(len(window.state.participants), 10)
        self.assertIn(window.state.participants[0].id, window.state.pool("Pool 01").members)
        page.accept()
        window.close()

    def test_ui_failed_creation_does_not_consume_id_or_add_card(self):
        window = demo_window(self.folder, 10)
        before = window.state.to_dict()
        keys = set(window.headers)
        with patch.object(window.store, "save", side_effect=OSError("Datenträger voll")):
            self.assertIsNone(window.create_pool("friendship"))
        self.assertEqual(window.state.to_dict(), before)
        self.assertEqual(set(window.headers), keys)
        window.close()

    def test_drag_to_friendship_then_unassigned_only_removes_extra_membership(self):
        window = demo_window(self.folder, 10)
        friend = window.create_pool("friendship")
        child = window.state.participants[0].id
        window.show()
        self.app.processEvents()

        def drop(target, source):
            mime = QMimeData()
            mime.setData(MIME, json.dumps({"participant_id": child, "source_pool_id": source}).encode())
            viewport = window.lists[target].viewport()
            actions = Qt.DropAction.MoveAction | Qt.DropAction.CopyAction
            enter = QDragEnterEvent(QPoint(20, 20), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(viewport, enter)
            self.assertTrue(enter.isAccepted())
            event = QDropEvent(QPointF(20, 20), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(viewport, event)
            return event

        self.assertEqual(drop(friend, "Pool 01").dropAction(), Qt.DropAction.CopyAction)
        self.assertIn(child, window.state.pool("Pool 01").members)
        self.assertIn(child, window.state.pool(friend).members)
        drop("", friend)
        loaded = Store(self.folder).load()
        self.assertIn(child, loaded.pool("Pool 01").members)
        self.assertNotIn(child, loaded.pool(friend).members)
        window.close()


if __name__ == "__main__":
    unittest.main()
