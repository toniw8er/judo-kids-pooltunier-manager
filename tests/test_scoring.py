"""Wertung, vollständige Gleichstände, Abschluss und Korrekturen."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from devtools.helpers import demo_window
from stadtmeisterschaft.domain import FightResult, Pool, RuleError, Tournament
from stadtmeisterschaft.scoring import Standing, assign_places, evaluate_pool
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.pool_page import PoolPage


def pair():
    return Pool("Pool 01", ["a", "b"], started=True,
                results={"1": FightResult("1:0", 10, 7), "2": FightResult("1:0", 5, 5)})


class ScoringTests(unittest.TestCase):
    def test_round_robin_sizes_and_friendship_share_the_same_non_mutating_calculation(self):
        for n, points, ub, places in [
            (3, [4, 2, 0], [20, 17, 14], [1, 2, 3]),
            (4, [6, 4, 2, 0], [30, 27, 24, 21], [1, 2, 3, 3]),
            (5, [8, 6, 4, 2, 0], [40, 37, 34, 31, 28], [1, 2, 3, 3, 5]),
        ]:
            pool = Pool("Test", [str(i) for i in range(n)], started=True)
            pool.results = {str(i): FightResult("1:0", 10, 7) for i in range(1, len(pool.fight_order) + 1)}
            before = deepcopy(pool)
            rows, matrix = evaluate_pool(pool)
            self.assertEqual([r.points for r in rows], points)
            self.assertEqual([r.ub_for for r in rows], ub)
            self.assertEqual([r.place for r in rows], places)
            self.assertEqual(pool, before)
            pool.kind = "friendship"
            self.assertEqual(evaluate_pool(pool), (rows, matrix))

    def test_confirmed_placements_including_all_tie_partitions_up_to_five(self):
        examples = [([3, 2, 1], [1, 2, 3]), ([4, 3, 2, 1], [1, 2, 3, 3]),
                    ([5, 4, 3, 2, 1], [1, 2, 3, 3, 5]), ([3, 3, 2, 1], [1, 1, 3, 3]),
                    ([3, 2, 2, 1], [1, 2, 2, 3]), ([3, 2, 1, 1, 1], [1, 2, 3, 3, 3]),
                    ([2, 2, 2, 1], [1, 1, 1, 3]), ([3, 3, 3, 2, 1], [1, 1, 1, 3, 5]),
                    ([2, 2, 2, 1, 1], [1, 1, 1, 3, 3]), ([2, 2, 2, 2, 1], [1, 1, 1, 1, 5]),
                    ([2, 2, 1, 1, 1], [1, 1, 3, 3, 3]), ([1] * 5, [1] * 5)]
        for keys, places in examples:
            rows = [Standing(str(i), points=p) for i, p in enumerate(keys)]
            assign_places(rows)
            self.assertEqual([r.place for r in rows], places)
        # Jede mögliche Anordnung von Gleichstandsgruppen; keine Gruppe teilen.
        for n in range(2, 6):
            for keys in product(range(n), repeat=n):
                rows = [Standing(str(i), points=p) for i, p in enumerate(keys)]
                assign_places(rows)
                for i in range(n):
                    for j in range(i):
                        if keys[i] == keys[j]:
                            self.assertEqual(rows[i].place, rows[j].place)

    def test_each_criterion_breaks_ties_in_the_confirmed_order(self):
        for stronger, weaker in [((4, 1, 5, 5), (3, 3, 30, 0)),
                                 ((4, 2, 5, 5), (4, 1, 30, 0)),
                                 ((4, 2, 10, 10), (4, 2, 7, 0)),
                                 ((4, 2, 10, 0), (4, 2, 10, 5))]:
            rows = [Standing("a", *stronger), Standing("b", *weaker)]
            assign_places(rows)
            self.assertEqual([r.place for r in rows], [1, 2])

    def test_actual_results_include_losers_ub_and_optional_third(self):
        pool = pair()
        rows, matrix = evaluate_pool(pool)
        self.assertEqual([(r.points, r.wins, r.ub_for, r.ub_against, r.place) for r in rows],
                         [(4, 2, 15, 12, 1), (0, 0, 12, 15, 2)])
        self.assertEqual(matrix["a", "b"], (4, 15))
        pool.results["3"] = FightResult("0:1", 7, 10)
        rows, matrix = evaluate_pool(pool)
        self.assertEqual([(r.points, r.ub_for, r.place) for r in rows], [(4, 22, 1), (2, 22, 2)])
        self.assertEqual(matrix["b", "a"], (2, 22))

    def test_pair_completeness_for_every_first_two_outcomes(self):
        for first, second in product(["1:0", "0:1", "0:0"], repeat=2):
            pool = pair()
            pool.results = {"1": FightResult(first, 5, 5), "2": FightResult(second, 5, 5)}
            optional = first == second and first != "0:0"
            self.assertEqual(pool.third_fight_optional, optional)
            self.assertEqual(pool.ready_to_complete, optional)
            self.assertEqual(pool.missing_required_fights, [] if optional else [3])
            if not optional:
                self.assertTrue(all(r.place is None for r in evaluate_pool(pool)[0]))
            pool.results["3"] = FightResult("0:0", 5, 5)
            self.assertTrue(pool.ready_to_complete)

    def test_pair_draw_examples_and_incomplete_or_single_pool(self):
        pool = pair()
        pool.results = {str(i): FightResult("0:0", 5, 5) for i in range(1, 4)}
        rows, _ = evaluate_pool(pool)
        self.assertEqual([(r.points, r.place) for r in rows], [(3, 1), (3, 1)])
        pool.results["3"] = FightResult("1:0", 10, 5)
        self.assertEqual([r.points for r in evaluate_pool(pool)[0]], [4, 2])
        pool.results["2"] = FightResult("0:1", 7, 10)
        self.assertEqual([r.points for r in evaluate_pool(pool)[0]], [3, 3])
        self.assertEqual([r.place for r in evaluate_pool(pool)[0]], [1, 2])
        for pool in [Pool("Leer"), Pool("Einzel", ["a"]), Pool("Offen", ["a", "b", "c"])]:
            self.assertFalse(pool.ready_to_complete)
            self.assertTrue(all(r.place is None for r in evaluate_pool(pool)[0]))

    def test_completion_reopen_reclose_and_existing_third_result(self):
        pool = pair()
        state = Tournament([], [pool])
        state.complete_pool(pool.id)
        self.assertTrue(pool.completed)
        revised = dict(pool.results) | {"2": FightResult("0:1", 5, 10)}
        state.save_pool(pool.id, "Korrigiert", revised)
        self.assertFalse(pool.completed)
        self.assertTrue(pool.started and pool.reopened)
        self.assertIn("Kampf 3 wieder verpflichtend", pool.evaluation_note)
        with self.assertRaises(RuleError):
            state.complete_pool(pool.id)
        revised["3"] = FightResult("0:0", 5, 5)
        state.save_pool(pool.id, "Korrigiert", revised)
        self.assertFalse(pool.completed)
        self.assertIn("erneut abschließen", pool.evaluation_note)
        state.complete_pool(pool.id)
        state.save_pool(pool.id, "Weiter korrigiert", revised | {"1": FightResult("0:0", 7, 7)})
        self.assertTrue(pool.completed)
        self.assertEqual(pool.results["3"], revised["3"])
        self.assertFalse(pool.reopened)
        state.save_pool(pool.id, "", {})
        self.assertFalse(pool.completed)
        self.assertTrue(pool.started)

    def test_v2_migration_does_not_infer_completion(self):
        from devtools.demo_data import demo
        state = demo(10)
        state.save_pool("Pool 03", "", {"1": FightResult("1:0", 10, 0), "2": FightResult("1:0", 10, 0)})
        payload = state.to_dict() | {"schema_version": 2}
        for pool in payload["pools"]:
            pool.pop("completed")
            pool.pop("reopened")
        migrated = Tournament.from_dict(payload)
        self.assertTrue(migrated.pool("Pool 03").ready_to_complete)
        self.assertFalse(migrated.pool("Pool 03").completed)
        migrated.complete_pool("Pool 03")
        self.assertEqual(Tournament.from_dict(migrated.to_dict()), migrated)
        broken = deepcopy(migrated.to_dict())
        broken["pools"][2]["results"] = {}
        with self.assertRaises(RuleError):
            Tournament.from_dict(broken)


class ScoringUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_atomic_finish_failure_reopen_and_reload(self):
        root = Path(__file__).resolve().parents[1] / "tmp" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            window = demo_window(Path(directory), 10)
            self.addCleanup(window.close)
            page = PoolPage(window, "Pool 03")
            self.addCleanup(page.close)
            for row in page.editors[:2]:
                for combo, value in zip(row, ["1:0", 10, 5]):
                    combo.setCurrentIndex(combo.findData(value))
            before = deepcopy(window.state.to_dict())
            with patch.object(window.store, "save", side_effect=OSError("Datenträger voll")):
                self.assertFalse(page.save(complete=True))
            self.assertEqual(window.state.to_dict(), before)
            self.assertEqual(page.editors[0][0].currentData(), "1:0")
            page.complete_button.click()
            self.assertTrue(window.state.pool("Pool 03").completed)
            self.assertIn("Abgeschlossen", page.evaluation_label.text())
            self.assertEqual(page.standings.item(0, 6).text(), "1")
            page.editors[1][0].setCurrentIndex(page.editors[1][0].findData("0:1"))
            self.assertTrue(page.save())
            self.assertFalse(window.state.pool("Pool 03").completed)
            self.assertIn("Kampf 3 wieder verpflichtend", page.evaluation_label.text())
            self.assertEqual(page.standings.item(0, 6).text(), "—")
            self.assertTrue(page.complete_button.isEnabled())
            self.assertFalse(page.save(complete=True))
            self.assertIn("Pflichtkämpfe", page.message.text())
            pool = Store(Path(directory)).load().pool("Pool 03")
            self.assertTrue(pool.reopened and pool.started)
            for combo, value in zip(page.editors[2], ["0:0", 5, 5]):
                combo.setCurrentIndex(combo.findData(value))
            self.assertTrue(page.save())
            self.assertFalse(window.state.pool("Pool 03").completed)
            page.complete_button.click()
            self.assertTrue(Store(Path(directory)).load().pool("Pool 03").completed)
            self.assertFalse(page.delete_button.isEnabled())
            self.assertIn("Abgeschlossen", window.pool_details["Pool 03"].text())
            page.close()
            window.close()


if __name__ == "__main__":
    unittest.main()
