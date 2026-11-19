"""Automatische Einteilung gegen Fachbeispiele und vollständige Kleinstsuche."""
from copy import deepcopy
from fractions import Fraction
from functools import cache
from itertools import combinations
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from devtools.demo_data import demo
from devtools.helpers import demo_window
from stadtmeisterschaft.age_class_defaults import suggested_classes
from stadtmeisterschaft.domain import AgeClass, FightResult, Participant, RuleError, Tournament
from stadtmeisterschaft.pool_planning import plan_pools
from stadtmeisterschaft.storage import Store


def children(weights, years=None, genders=None):
    return [Participant(str(i), "Kind", str(i), "Verein", (years or [2016] * len(weights))[i],
                        (genders or ["M"] * len(weights))[i], w)
            for i, w in enumerate(weights)]


def score(groups, people):
    lookup = {p.id: p for p in people}
    sizes = [len(g.members) for g in groups]
    spans = []
    for group in groups:
        weights = [lookup[pid].weight_grams for pid in group.members]
        spans.append(Fraction(max(weights) - min(weights), min(weights)))
    return sizes.count(1), len(sizes), sum(n * n for n in sizes), sum(spans, Fraction(0))


def exhaustive_score(people, classes):
    """Unabhängiges Orakel: alle Partitionen, ohne Intervallabkürzung."""
    @cache
    def solve(ids):
        if not ids:
            return 0, 0, 0, Fraction(0)
        best = None
        for size in range(1, min(5, len(ids)) + 1):
            for extra in combinations(ids[1:], size - 1):
                group = (ids[0], *extra)
                ps = [people[i] for i in group]
                if not any(all(p.birth_year in c.years for p in ps)
                           and (c.mixed or len({p.gender for p in ps}) == 1) for c in classes):
                    continue
                weights = [p.weight_grams for p in ps]
                if max(weights) * 10 > min(weights) * 11:
                    continue
                rest = solve(tuple(i for i in ids if i not in group))
                local = (int(size == 1), 1, size * size,
                         Fraction(max(weights) - min(weights), min(weights)))
                candidate = tuple(a + b for a, b in zip(local, rest))
                best = candidate if best is None else min(best, candidate)
        return best
    return solve(tuple(range(len(people))))


class PoolPlanningTests(unittest.TestCase):
    def test_sizes_and_partner_priority(self):
        for n, expected in [(6, [3, 3]), (7, [3, 4]), (8, [4, 4]), (10, [5, 5]), (11, [3, 4, 4])]:
            with self.subTest(n=n):
                groups, missing = plan_pools(children([20000] * n), [AgeClass("U11", [2016])])
                self.assertEqual(sorted(len(g.members) for g in groups), expected)
                self.assertEqual(missing, [])
        # Vier nahe + zwei Randkinder: beide Randkinder brauchen jeweils Partner.
        people = children([19000, 20000, 20000, 20000, 20000, 22000])
        groups, _ = plan_pools(people, [AgeClass("U11", [2016])])
        self.assertEqual(sorted(len(g.members) for g in groups), [3, 3])

    def test_exact_weight_limits_and_no_neighbour_chaining(self):
        for weights, sizes in [([20000, 21000, 22000], [3]),
                               ([20000, 22000, 24200], [1, 2]),
                               ([22500, 25000, 27500], [1, 2]),
                               ([18000, 19000, 19800], [3]),
                               ([18000, 20000], [1, 1]),
                               ([18200, 20000], [2]), ([18100, 20000], [1, 1])]:
            with self.subTest(weights=weights):
                groups, _ = plan_pools(children(weights), [AgeClass("U11", [2016])])
                self.assertEqual(sorted(len(g.members) for g in groups), sizes)

    def test_overlapping_years_are_global_alternatives(self):
        people = children([20000] * 4, [2017, 2016, 2016, 2015])
        classes = [AgeClass("U11", [2016, 2017]), AgeClass("U13", [2015, 2016])]
        groups, _ = plan_pools(people, classes)
        self.assertEqual(sorted(len(g.members) for g in groups), [2, 2])
        self.assertEqual({g.age_class for g in groups}, {"U11", "U13"})

    def test_mixing_is_checked_for_actual_class(self):
        people = children([20000, 20000], [2016, 2016], ["M", "F"])
        groups, _ = plan_pools(people, [AgeClass("U11", [2016]), AgeClass("U13", [2016], True)])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].age_class, "U13")
        groups, _ = plan_pools(people, [AgeClass("U11", [2016])])
        self.assertEqual(len(groups), 2)

    def test_missing_age_class_is_not_assigned_and_singletons_are_marked(self):
        state = Tournament(children([20000, 30000, 40000], [2016, 2016, 2020]), [],
                           age_classes=[AgeClass("U11", [2016])])
        state.recreate_regular_pools()
        self.assertEqual(len(state.pools), 2)
        self.assertIn("Keine passende Altersklasse", state.participant_planning_note("2"))
        self.assertTrue(all("Einzelpool" in state.pool_warnings(p.id)[0] for p in state.pools))
        self.assertEqual({pid for p in state.pools for pid in p.members}, {"0", "1"})

    def test_all_unmatched_with_configured_classes_clears_only_unstarted_regular(self):
        state = demo(10)
        state.age_classes = [AgeClass("Andere", [1900])]
        friend = state.create_pool("friendship")
        state.move(state.participants[0].id, friend)
        before = deepcopy(state.pool(friend))
        state.recreate_regular_pools()
        self.assertEqual(state.pools, [before])

    def test_protected_pools_and_ids_and_reload(self):
        state = demo(10)
        state.age_classes = [AgeClass("Alle", list(range(2000, 2030)), True)]
        state.save_pool("Pool 01", "Gestartet", {"1": FightResult("1:0", 10, 0)})
        state.save_pool("Pool 01", "Gestartet", {})
        friend = state.create_pool("friendship")
        state.move(state.participants[0].id, friend)
        state.move(state.participants[3].id, friend)
        state.save_pool(friend, "Gestartete Freunde", {"1": FightResult("0:1", 0, 10)})
        before = deepcopy([state.pool("Pool 01"), state.pool(friend)])
        state.recreate_regular_pools()
        self.assertEqual(state.pools[:2], before)
        self.assertEqual(state.pools[2].id, "Pool 02")
        assigned = [pid for p in state.pools if not p.is_friendship for pid in p.members]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), {p.id for p in state.participants})
        self.assertEqual(Tournament.from_dict(state.to_dict()), state)

    def test_repeated_replanning_reuses_numbers(self):
        state = demo(10)
        state.age_classes = [AgeClass("Alle", list(range(2000, 2030)), True)]
        state.next_pool_number = 900
        state.recreate_regular_pools()
        expected = [pool.id for pool in state.pools]
        self.assertEqual(expected, [f"Pool {number:02}" for number in range(1, len(expected) + 1)])
        state.recreate_regular_pools()
        self.assertEqual([pool.id for pool in state.pools], expected)

    def test_start_class_warnings_follow_current_configuration(self):
        state = Tournament(children([20000, 20000], genders=["M", "F"]), [],
                           age_classes=[AgeClass("U11", [2016], True), AgeClass("U13", [2016], True)])
        state.recreate_regular_pools()
        pool = state.pools[0]
        self.assertEqual(pool.age_class, "U11")
        state.age_classes[0].mixed = False
        self.assertTrue(any("Mädchen/Jungen" in s for s in state.pool_warnings(pool.id)))
        state.age_classes.pop(0)
        self.assertTrue(any("Startklasse U11" in s for s in state.pool_warnings(pool.id)))
        self.assertEqual(pool.age_class, "U11")

    def test_v1_migration_does_not_guess_class_and_unknown_versions_fail(self):
        state = demo(10)
        payload = state.to_dict()
        payload["schema_version"] = 1
        for pool in payload["pools"]:
            del pool["age_class"]
        migrated = Tournament.from_dict(payload)
        self.assertTrue(all(not p.age_class for p in migrated.pools))
        self.assertEqual(migrated.to_dict()["schema_version"], 6)
        with self.assertRaises(RuleError):
            Tournament.from_dict(payload | {"schema_version": 7})

    def test_deterministic_after_input_reordering(self):
        people = children([20000] * 8, [2017, 2016, 2016, 2015] * 2)
        classes = [AgeClass("U11", [2016, 2017]), AgeClass("U13", [2015, 2016])]
        expected = plan_pools(people, classes)
        self.assertEqual(plan_pools(list(reversed(people)), list(reversed(classes))), expected)

    def test_random_small_cases_match_independent_partition_oracle(self):
        rng = random.Random(2718)
        for case in range(160):
            n = rng.randrange(2, 9)
            people = children([rng.randrange(180, 241) * 100 for _ in range(n)],
                              [rng.choice([2015, 2016, 2017]) for _ in range(n)],
                              [rng.choice(["M", "F"]) for _ in range(n)])
            classes = ([AgeClass("Alle", [2015, 2016, 2017], True)] if case % 2 else
                       [AgeClass("U11", [2016, 2017], bool(case % 3)),
                        AgeClass("U13", [2015, 2016], bool(case % 5))])
            groups, _ = plan_pools(people, classes)
            with self.subTest(case=case):
                self.assertEqual(score(groups, people), exhaustive_score(people, classes))

    def test_solver_limit_and_missing_configuration_do_not_mutate_state(self):
        state = demo(10)
        before = state.to_dict()
        with self.assertRaises(RuleError):
            state.recreate_regular_pools()
        self.assertEqual(state.to_dict(), before)
        state.age_classes = suggested_classes(2026)
        before = state.to_dict()
        with patch("stadtmeisterschaft.pool_planning.plan_pools", side_effect=RuleError("Limit")):
            with self.assertRaises(RuleError):
                state.recreate_regular_pools()
        self.assertEqual(state.to_dict(), before)
        with self.assertRaises(RuleError):
            plan_pools(children([20000, 20000]), [AgeClass("U11", [2016])], time_limit=0)

    def test_development_sizes_and_dense_hundred(self):
        for count in [10, 40, 100]:
            state = demo(count)
            state.age_classes = suggested_classes(2026)
            state.recreate_regular_pools()
            state.validate()
            for pool in state.pools:
                self.assertTrue(pool.age_class)
                self.assertFalse([w for w in state.pool_warnings(pool.id) if "Einzelpool" not in w])
        groups, _ = plan_pools(children([20000 + (i % 10) * 100 for i in range(100)]), [AgeClass("U11", [2016])])
        self.assertEqual(len(groups), 20)
        self.assertTrue(all(len(g.members) == 5 for g in groups))


class PlanningUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_cancel_failure_success_and_restart(self):
        root = Path(__file__).resolve().parents[1] / "tmp" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            window = demo_window(Path(folder), 10)
            self.addCleanup(window.close)
            self.assertFalse(window.recreate_regular_pools())
            window.change(lambda s: s.configure(s.name, s.event_date, suggested_classes(2026)), "Klassen")
            before = window.state.to_dict()
            with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
                self.assertFalse(window.recreate_regular_pools())
            self.assertEqual(window.state.to_dict(), before)
            with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
                with patch.object(window.store, "save", side_effect=OSError("Datenträger voll")):
                    self.assertFalse(window.recreate_regular_pools())
                self.assertEqual(window.state.to_dict(), before)
                self.assertEqual(Store(Path(folder)).load().to_dict(), before)
                window.recreate_button.click()
            self.assertTrue(window.recreate_button.isEnabled())
            self.assertIsNone(QApplication.overrideCursor())
            saved = Store(Path(folder)).load()
            self.assertEqual(saved, window.state)
            self.assertTrue(any("Startklasse:" in label.text() for label in window.pool_details.values()))
            self.assertTrue(any("Keine passende Altersklasse" in window.lists[""].item(i).text()
                                for i in range(window.lists[""].count())))
            window.close()


if __name__ == "__main__":
    unittest.main()
