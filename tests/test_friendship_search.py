"""Freundschaftspartner bewusst auswählen und atomar übernehmen."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from devtools.helpers import demo_window
from stadtmeisterschaft.domain import AgeClass, Participant, Pool, RuleError, Tournament
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.pool_page import PoolPage
from stadtmeisterschaft.friendship import group_warnings, load_age_factor, pair_distance, participant_class, suggestions
from stadtmeisterschaft.ui.friendship_search import FriendshipSearch
from stadtmeisterschaft.ui.planning_details import weight_comparison


class FriendshipRankingTests(unittest.TestCase):
    def test_other_friendships_warn_for_origin_and_partner_without_changing_ranking(self):
        state = search_state()
        order = [s.participant_id for s in suggestions(state, "Pool 01", [])]
        other = state.pool(state.create_pool("friendship", "Schon geplant"))
        other.members = ["0", "1"]
        other.started = True
        ranked = suggestions(state, "Pool 01", [])
        self.assertEqual([s.participant_id for s in ranked], order)
        notes = "\n".join(ranked[0].notes)
        self.assertIn("Alex Test: Bereits in anderem Freundschaftspool: " + other.display_name, notes)
        self.assertIn("Ben Test: Bereits in anderem Freundschaftspool: " + other.display_name, notes)
        # Beim Ergänzen zählt der eigene Pool nicht als weitere Teilnahme.
        self.assertNotIn("Freundschaftspool", "\n".join(group_warnings(state, other.id, [])))
        target = state.add_friendship_partners("Pool 01", ["1"])
        self.assertEqual(state.pool(target).members, ["0", "1"])
        self.assertIn(other.display_name, "\n".join(state.pool_member_warnings(target, "1")))
        state.validate()

    def test_signed_weight_comparison_uses_smaller_weight(self):
        self.assertEqual(weight_comparison(21400, 18900), "2,5 kg schwerer (+13,2 %)")
        self.assertEqual(weight_comparison(18900, 21400), "2,5 kg leichter (−13,2 %)")
        self.assertEqual(weight_comparison(20000, 20000), "gleich schwer (0,0 %)")
        self.assertEqual(weight_comparison(22000, 20000), "2,0 kg schwerer (+10,0 %)")

    def test_confirmed_ranking_and_exact_distances(self):
        state = search_state()
        before = deepcopy(state)
        ranked = suggestions(state, "Pool 01", [])
        self.assertEqual([s.participant_id for s in ranked], ["1", "2", "3", "4", "5"])
        self.assertEqual([f"{s.score:.2f}" for s in ranked], ["9.67", "10.67", "11.67", "24.67", "32.33"])
        self.assertEqual(state, before)
        self.assertEqual(pair_distance(state, "0", "1", 8), (Fraction(29, 3), Fraction(5, 3), 1))

    def test_group_ranking_checks_pairs_between_selected_children(self):
        state = search_state()
        state.participant("1").weight_grams = 28000
        ranked = suggestions(state, "Pool 01", ["1"])
        mia = next(s for s in ranked if s.participant_id == "2")
        self.assertGreater(mia.score, pair_distance(state, "0", "2", 8)[0])
        notes = "\n".join(group_warnings(state, "Pool 01", ["1", "2"]))
        self.assertIn("Ben Test", notes)
        self.assertIn("Mia Test", notes)
        self.assertIn("10 %", notes)
        self.assertNotIn("1", {s.participant_id for s in ranked})

    def test_actual_class_then_youngest_fallback_and_gender_uses_origin(self):
        state = search_state()
        # Mädchen aus getrennter U13 bleibt aus gemischter U11 vorschlagbar.
        state.participant("1").gender = "F"
        self.assertIn("1", {s.participant_id for s in suggestions(state, "Pool 01", [])})
        state.age_classes[0].mixed = False
        self.assertNotIn("1", {s.participant_id for s in suggestions(state, "Pool 01", [])})
        self.assertNotIn("2", {s.participant_id for s in suggestions(state, "Pool 01", [])})
        state.age_classes[0].years.append(2015)
        self.assertEqual(participant_class(state, "1").name, "U13")
        state.pool("Pool 02").age_class = ""
        self.assertEqual(participant_class(state, "1").name, "U11")
        state.pool("Pool 02").age_class = "Entfernt"
        self.assertIsNone(participant_class(state, "1"))

    def test_inactive_unknown_class_ties_and_no_distance_cutoff(self):
        state = search_state()
        state.participant("1").withdrawn = True
        state.participant("2").disqualified = True
        state.participant("3").birth_year = 2022
        state.participant("4").weight_grams = 100000
        self.assertEqual({s.participant_id for s in suggestions(state, "Pool 01", [])}, {"4", "5"})
        state = search_state()
        state.participant("1").weight_grams = state.participant("2").weight_grams = 31000
        state.participant("1").first_name = "Zed"
        ranked = suggestions(state, "Pool 01", [], 0)
        self.assertLess([s.participant_id for s in ranked].index("2"), [s.participant_id for s in ranked].index("1"))
        state.participant("0").birth_year = 2022
        state.pool("Pool 01").age_class = ""
        with self.assertRaises(RuleError):
            suggestions(state, "Pool 01", [])

    def test_factor_config_defaults_and_rejects_bad_files(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "freundschaft.json"
            self.assertEqual(load_age_factor(folder), 8)
            for factor in [0, 8, 100000]:
                path.write_text(json.dumps({"altersfaktor": factor}), encoding="utf-8")
                self.assertEqual(load_age_factor(folder), factor)
            for data in [{}, [], {"altersfaktor": True}, {"altersfaktor": -1}, {"altersfaktor": 1.5}, {"altersfaktor": "8"}]:
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.subTest(data=data), self.assertRaises(RuleError):
                    load_age_factor(folder)
            path.write_bytes(b"\xff")
            with self.assertRaises(RuleError):
                load_age_factor(folder)
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(RuleError):
                load_age_factor(folder)


def search_state():
    names = ["Alex", "Ben", "Mia", "Leon", "Tom", "Finn"]
    weights = [30000, 30500, 33200, 33500, 35000, 30100]
    years = [2017, 2015, 2017, 2017, 2015, 2013]
    people = [Participant(str(i), name, "Test", "JC", year, "F" if name == "Mia" else "M", weight)
              for i, (name, weight, year) in enumerate(zip(names, weights, years))]
    return Tournament(people, [Pool("Pool 01", ["0"], age_class="U11"),
                              Pool("Pool 02", ["1", "4"], age_class="U13")],
                      age_classes=[AgeClass("U11", [2017, 2018], True),
                                   AgeClass("U13", [2015, 2016]), AgeClass("U15", [2013, 2014])],
                      next_pool_number=3)


class FriendshipManagementTests(unittest.TestCase):
    def test_create_from_single_preserves_every_existing_assignment(self):
        state = search_state()
        before = deepcopy(state.pools)
        target = state.add_friendship_partners("Pool 01", ["1", "2"])
        self.assertEqual(state.pools[:2], before)
        self.assertEqual(state.pool(target).members, ["0", "1", "2"])
        self.assertTrue(state.pool(target).is_friendship)
        state.validate()

    def test_extend_one_to_four_member_friendships_and_reject_full_started_empty(self):
        for size in range(1, 5):
            state = search_state()
            pool = state.pool(state.create_pool("friendship", "Zusätzlich"))
            pool.members = [str(i) for i in range(size)]
            self.assertTrue(state.friendship_search_available(pool.id))
            self.assertEqual(state.add_friendship_partners(pool.id, [str(size)]), pool.id)
            self.assertEqual(len(pool.members), size + 1)
            self.assertEqual(pool.name, "Zusätzlich")
        for members, started in [([], False), (["0"] * 5, False), (["0"], True)]:
            state = search_state()
            pool = state.pool(state.create_pool("friendship"))
            pool.members, pool.started = members, started
            before = deepcopy(state)
            self.assertFalse(state.friendship_search_available(pool.id))
            with self.assertRaises(RuleError):
                state.add_friendship_partners(pool.id, ["1"])
            self.assertEqual(state, before)

    def test_invalid_selection_never_creates_partial_pool_or_consumes_id(self):
        for partners in [[], ["1", "1"], ["0"], ["unknown"], ["1", "2", "3", "4", "5"]]:
            state = search_state()
            before = deepcopy(state)
            with self.subTest(partners=partners), self.assertRaises(RuleError):
                state.add_friendship_partners("Pool 01", partners)
            self.assertEqual(state, before)
        state = search_state()
        with self.assertRaises(RuleError):
            state.add_friendship_partners("Pool 02", ["3"])
        for status in ["withdrawn", "disqualified"]:
            setattr(state.participant("3"), status, True)
            before = deepcopy(state)
            with self.assertRaises(RuleError):
                state.add_friendship_partners("Pool 01", ["3"])
            self.assertEqual(state, before)


class FriendshipUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = demo_window(Path(self.temp.name), 10)
        self.window.change(lambda s: s.__dict__.update(search_state().__dict__), "Szenario")

    def tearDown(self):
        self.window.close()
        self.temp.cleanup()

    def test_search_entry_and_unsaved_guard(self):
        page = PoolPage(self.window, "Pool 01")
        self.assertFalse(page.friendship_button.isHidden())
        self.assertTrue(page.friendship_button.isEnabled())
        page.pool_mat.setText("1")
        page.search_friendship()
        self.assertIn("zuerst speichern", page.message.text())
        page.pool_mat.clear()
        page.close()
        other = PoolPage(self.window, "Pool 02")
        self.assertTrue(other.friendship_button.isHidden())
        other.close()

    def test_other_friendship_visible_before_selection_and_does_not_block_commit(self):
        other = []
        self.window.change(lambda s: other.append(s.add_friendship_partners("Pool 01", ["1"])), "Vorhandene Gruppe")
        dialog = FriendshipSearch(self.window, "Pool 01")
        row = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).text().startswith("Ben Test"))
        self.assertIn(other[0], dialog.table.item(row, 0).text())
        self.assertIn("Bereits in anderem Freundschaftspool", dialog.table.item(row, 0).text())
        self.assertIn(other[0], dialog.group.text())
        dialog.add_partner("1")
        self.assertIn("Weitere Freundschaftsteilnahme", dialog.warnings.summary.text())
        self.assertIn("Ben Test: Bereits", dialog.warnings.text())
        self.assertTrue(dialog.confirm.isEnabled())
        dialog.commit()
        self.assertEqual(self.window.store.load().pool(dialog.target_pool_id).members, ["0", "1"])
        extended = FriendshipSearch(self.window, other[0])
        self.assertIn(dialog.target_pool_id, extended.group.text())
        extended.reject()

    def test_failed_atomic_save_keeps_state_and_next_id(self):
        before = deepcopy(self.window.state)
        with patch.object(self.window.store, "save", side_effect=OSError("voll")):
            self.assertFalse(self.window.change(lambda s: s.add_friendship_partners("Pool 01", ["1", "2"]), "Gruppe"))
        self.assertEqual(self.window.state, before)
        self.assertEqual(self.window.store.load(), before)
        target = []
        self.assertTrue(self.window.change(lambda s: target.append(s.add_friendship_partners("Pool 01", ["1", "2"])), "Gruppe"))
        self.assertEqual(Store(Path(self.temp.name)).load().pool(target[0]).members, ["0", "1", "2"])

    def test_entry_for_existing_friendships_and_started_source_is_disabled(self):
        for size in range(0, 6):
            ids = [str(i) for i in range(size)]
            target = []
            def prepare(state):
                target.append(state.create_pool("friendship"))
                state.pool(target[0]).members = ids
            self.window.change(prepare, "Freundschaft")
            page = PoolPage(self.window, target[0])
            self.assertFalse(page.friendship_button.isHidden())
            self.assertEqual(page.friendship_button.isEnabled(), 1 <= size < 5)
            page.close()
        self.window.change(lambda s: setattr(s.pool("Pool 01"), "started", True), "Sperre")
        page = PoolPage(self.window, "Pool 01")
        self.assertFalse(page.friendship_button.isEnabled())
        page.close()

    def test_dialog_select_reorder_undo_cancel_and_confirm(self):
        before = deepcopy(self.window.state)
        dialog = FriendshipSearch(self.window, "Pool 01")
        self.assertEqual(dialog.table.rowCount(), 5)
        dialog.add_partner("1")
        dialog.add_partner("2")
        self.assertEqual(dialog.selected, ["1", "2"])
        self.assertIn("Mia Test", dialog.group.text())
        self.assertIn("Gewicht", dialog.warnings.text())
        dialog.remove_last()
        self.assertEqual(dialog.selected, ["1"])
        dialog.reject()
        self.assertEqual(self.window.state, before)
        dialog = FriendshipSearch(self.window, "Pool 01")
        dialog.add_partner("1")
        with patch.object(self.window.store, "save", side_effect=OSError("voll")):
            dialog.commit()
        self.assertEqual(dialog.selected, ["1"])
        self.assertEqual(self.window.state, before)
        self.assertIn("voll", dialog.message.text())
        dialog.commit()
        target = dialog.target_pool_id
        self.assertIsNotNone(target)
        self.assertEqual(self.window.state.pool(target).members, ["0", "1"])
        extended = FriendshipSearch(self.window, target)
        for pid in ["2", "3", "4"]:
            extended.add_partner(pid)
        self.assertEqual(extended.table.rowCount(), 0)
        self.assertTrue(extended.confirm.isEnabled())
        extended.commit()
        self.assertEqual(extended.target_pool_id, target)
        self.assertEqual(self.window.store.load().pool(target).members, ["0", "1", "2", "3", "4"])

    def test_dialog_invalid_config_and_missing_origin_prevent_confirmation(self):
        path = Path(self.temp.name) / "freundschaft.json"
        path.write_text('{"altersfaktor": -1}', encoding="utf-8")
        dialog = FriendshipSearch(self.window, "Pool 01")
        self.assertFalse(dialog.confirm.isEnabled())
        self.assertIn("ganzen Zahl ab 0", dialog.message.text())
        dialog.reject()
        path.unlink()
        self.window.change(lambda s: s.age_classes.clear(), "Klassen entfernt")
        dialog = FriendshipSearch(self.window, "Pool 01")
        self.assertFalse(dialog.confirm.isEnabled())
        self.assertIn("Altersklassen", dialog.message.text())
        dialog.reject()

    def test_pool_page_reopens_updated_target_after_search(self):
        page = PoolPage(self.window, "Pool 01")
        def accept(dialog):
            dialog.add_partner("1")
            dialog.commit()
            return dialog.result()
        with patch.object(FriendshipSearch, "exec", accept):
            page.search_friendship()
        self.assertEqual(self.window.state.pool(page.next_pool_id).members, ["0", "1"])
        updated = PoolPage(self.window, page.next_pool_id)
        self.assertEqual(updated.participant_choice.count(), 2)
        self.assertEqual(len(updated.editors), 3)
        updated.close()

    def test_mouse_selection_undo_and_cancel_preserve_saved_state(self):
        before = deepcopy(self.window.state)
        dialog = FriendshipSearch(self.window, "Pool 01")
        dialog.show()
        self.app.processEvents()
        QTest.mouseClick(dialog.table.cellWidget(0, 4), Qt.MouseButton.LeftButton)
        self.assertEqual(dialog.selected, ["1"])
        QTest.mouseClick(dialog.remove, Qt.MouseButton.LeftButton)
        self.assertEqual(dialog.selected, [])
        dialog.reject()
        self.assertEqual(self.window.state, before)
        self.assertEqual(self.window.store.load(), before)

    def test_compact_search_shows_weights_comparison_and_info_on_request(self):
        dialog = FriendshipSearch(self.window, "Pool 01")
        self.assertIn("Alex Test · U11 · 30,0 kg", dialog.group.text())
        headers = [dialog.table.horizontalHeaderItem(c).text() for c in range(dialog.table.columnCount())]
        self.assertNotIn("Rangwert", headers)
        self.assertNotIn("Größter Paarabstand", headers)
        self.assertIn("Vergleich zu Alex Test", headers)
        self.assertEqual(dialog.table.item(0, 3).text(), "0,5 kg schwerer (+1,7 %)")
        self.assertFalse(any("Rangwert =" in label.text() for label in dialog.findChildren(QLabel)))
        with patch("stadtmeisterschaft.ui.friendship_search.QMessageBox.information") as info:
            dialog.info.click()
        self.assertIn("Rangwert =", info.call_args.args[2])
        self.assertIn("kleinere", info.call_args.args[2])
        dialog.add_partner("1")
        self.assertIn("Ben Test · U13 · 30,5 kg", dialog.group.text())
        row = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).text() == "Mia Test")
        self.assertEqual(dialog.table.item(row, 3).text(), "zu Alex Test: 3,2 kg schwerer (+10,7 %)")
        self.assertIn("zu Ben Test (30,5 kg)", dialog.table.item(row, 3).toolTip())
        dialog.add_partner("2")
        self.assertTrue(dialog.warnings.scroll.isHidden())
        self.assertIn("Gewichtsspanne über 10 %", dialog.warnings.summary.text())
        dialog.warnings.toggle.click()
        self.assertFalse(dialog.warnings.scroll.isHidden())
        self.assertIn("Mia Test", dialog.warnings.details.text())
        dialog.reject()
