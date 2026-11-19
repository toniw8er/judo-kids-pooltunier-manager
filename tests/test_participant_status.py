"""Endgültige Status, automatische Wertungen und gemeinsame Ausgabe."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QMessageBox

from stadtmeisterschaft.application import TournamentSession
from stadtmeisterschaft.domain import FightResult, Participant, Pool, RuleError, Tournament
from stadtmeisterschaft.output import draw_pool
from stadtmeisterschaft.sheets import read_participants, write_ods
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.main_window import Window
from stadtmeisterschaft.ui.pool_page import PoolPage


def tournament(count=3):
    people = [Participant(str(i), "Kind", str(i), "JC", 2017, "M", 20000) for i in range(count)]
    return Tournament(people, [Pool("Pool 01", [p.id for p in people])], event_date="2026-11-19")


class ParticipantStatusTests(unittest.TestCase):
    def test_withdrawal_keeps_played_and_injury_results_and_fills_open_fights(self):
        state = tournament()
        played = FightResult("0:1", 7, 10, "injury")
        state.save_pool("Pool 01", "", {"1": played})
        state.set_participant_status("0", "withdrawn")
        pool = state.pools[0]
        self.assertEqual(pool.results["1"], played)
        self.assertEqual(pool.results["2"], FightResult("0:1", 0, 10, "withdrawal"))
        self.assertNotIn("3", pool.results)
        self.assertTrue(pool.started)
        rows, matrix = state.evaluate_pool(pool.id)
        self.assertEqual((rows[0].points, rows[0].ub_for, matrix["0", "1"]), (0, 7, (0, 7)))
        state.save_pool(pool.id, "", pool.results | {"1": FightResult("0:1", 5, 10, "injury")})
        self.assertEqual(state.evaluate_pool(pool.id)[0][0].ub_for, 5)
        state.validate()

    def test_later_second_withdrawal_preserves_already_awarded_win(self):
        state = tournament(2)
        state.set_participant_status("0", "withdrawn")
        before = deepcopy(state.pools[0].results)
        state.set_participant_status("1", "withdrawn")
        self.assertEqual(state.pools[0].results, before)
        self.assertEqual(set(before), {"1", "2"})
        rows, _ = state.evaluate_pool("Pool 01")
        self.assertEqual([(r.points, r.wins, r.ub_for, r.place) for r in rows], [(0, 0, 0, 2), (4, 2, 20, 1)])

    def test_both_already_withdrawn_before_new_encounter_receive_no_draw_points(self):
        state = tournament(2)
        for person in state.participants:
            person.withdrawn = True
        state.save_pool("Pool 01", "", {})
        rows, matrix = state.evaluate_pool("Pool 01")
        self.assertEqual(set(state.pools[0].results), {"1", "2", "3"})
        self.assertTrue(all(r.points == r.wins == r.ub_for == r.ub_against == 0 for r in rows))
        self.assertEqual([r.place for r in rows], [1, 1])
        self.assertEqual(matrix["0", "1"], (0, 0))

    def test_disqualification_replaces_past_and_future_and_excludes_from_places(self):
        state = tournament()
        state.save_pool("Pool 01", "", {str(i): FightResult("1:0", 10, 7) for i in range(1, 4)})
        state.complete_pool("Pool 01")
        state.set_participant_status("0", "disqualified")
        pool = state.pools[0]
        self.assertTrue(pool.reopened and pool.started)
        self.assertFalse(pool.completed)
        self.assertIn("Disqualifikation", pool.evaluation_note)
        self.assertEqual(pool.results["1"], FightResult("0:1", 0, 10, "disqualification"))
        self.assertEqual(pool.results["3"], FightResult("1:0", 10, 7))
        rows, matrix = state.evaluate_pool(pool.id)
        self.assertEqual([r.place for r in rows], [None, 1, 2])
        self.assertEqual((rows[0].points, rows[0].ub_for, matrix["0", "1"]), (0, 0, (0, 0)))
        with self.assertRaisesRegex(RuleError, "gesperrt"):
            state.save_pool(pool.id, "", pool.results | {"1": FightResult("1:0", 10, 0)})
        state.complete_pool(pool.id)
        state.validate()

    def test_both_disqualified_zero_all_values_and_have_no_places(self):
        state = tournament(2)
        state.set_participant_status("0", "disqualified")
        self.assertNotIn("3", state.pools[0].results)
        state.set_participant_status("1", "disqualified")
        rows, matrix = state.evaluate_pool("Pool 01")
        self.assertEqual(len(state.pools[0].results), 3)
        self.assertTrue(all(r.points == r.wins == r.ub_for == r.ub_against == 0 and r.place is None for r in rows))
        self.assertEqual(matrix["0", "1"], (0, 0))
        state.validate()

    def test_disqualification_overrides_withdrawal_in_both_status_orders(self):
        for order in (("withdrawn", "disqualified"), ("disqualified", "withdrawn")):
            with self.subTest(order=order):
                state = tournament(2)
                for status in order:
                    state.set_participant_status("0" if status == "withdrawn" else "1", status)
                rows, _ = state.evaluate_pool("Pool 01")
                self.assertEqual([(r.points, r.wins, r.ub_for, r.place) for r in rows], [(4, 2, 20, 1), (0, 0, 0, None)])

    def test_no_undo_and_status_applies_to_all_friendship_participations(self):
        state = tournament()
        friend = state.create_pool("friendship")
        for pid in ("0", "1"):
            state.move(pid, friend)
        state.set_participant_status("0", "withdrawn")
        self.assertTrue(all(pool.started for pool in state.pools))
        self.assertEqual(state.pool(friend).results["1"].reason, "withdrawal")
        state.set_participant_status("0", "disqualified")
        self.assertTrue(state.participant("0").withdrawn and state.participant("0").disqualified)
        self.assertTrue(all(pool.results["1"].reason == "disqualification" for pool in state.pools))
        with self.assertRaises(RuleError):
            state.set_participant_status("0", "active")
        with self.assertRaises(RuleError):
            state.move("0", "")

    def test_existing_optional_third_is_preserved_or_overridden_by_status(self):
        for status in ("withdrawn", "disqualified"):
            state = tournament(2)
            results = {"1": FightResult("1:0", 10, 0), "2": FightResult("1:0", 10, 0),
                       "3": FightResult("0:1", 7, 10)}
            state.save_pool("Pool 01", "", results)
            state.set_participant_status("1", status)
            self.assertIn("3", state.pools[0].results)
            self.assertEqual(state.pools[0].results["3"], results["3"] if status == "withdrawn"
                             else FightResult("1:0", 10, 0, "disqualification"))

    def test_required_third_is_filled_and_withdrawal_can_keep_first_place(self):
        state = tournament(2)
        state.save_pool("Pool 01", "", {"1": FightResult("1:0", 10, 0)})
        state.set_participant_status("0", "withdrawn")
        self.assertEqual(set(state.pools[0].results), {"1", "2", "3"})
        # Kein Platzierungsverbot bei Rückzug, auch bei bereits gewonnener Serie.
        state = tournament(2)
        state.save_pool("Pool 01", "", {"1": FightResult("1:0", 10, 0), "2": FightResult("1:0", 10, 0)})
        state.complete_pool("Pool 01")
        state.set_participant_status("0", "withdrawn")
        self.assertTrue(state.pools[0].completed)
        self.assertEqual(state.evaluate_pool("Pool 01")[0][0].place, 1)

    def test_completed_pool_reopens_on_changed_eligibility_even_with_identical_scores(self):
        state = tournament(2)
        state.set_participant_status("0", "withdrawn")
        state.complete_pool("Pool 01")
        state.set_participant_status("0", "disqualified")
        self.assertFalse(state.pools[0].completed)
        self.assertTrue(state.pools[0].reopened)

    def test_automatic_values_cannot_be_removed_and_nonattendance_does_not_set_status(self):
        state = tournament()
        state.save_pool("Pool 01", "", {"1": FightResult("0:1", 0, 10, "nonattendance")})
        self.assertFalse(state.participant("0").withdrawn)
        self.assertNotIn("2", state.pools[0].results)
        state.set_participant_status("0", "withdrawn")
        with self.assertRaises(RuleError):
            state.save_pool("Pool 01", "", {"1": state.pools[0].results["1"]})
        for result in (FightResult("0:0", 0, 0, "nonattendance"), FightResult("1:0", 7, 0, "withdrawal"),
                       FightResult("0:0", 5, 5, "both_disqualified"), FightResult("1:0", 10, 0, "unknown")):
            with self.subTest(result=result), self.assertRaises(RuleError):
                result.validate()

    def test_v0_to_v3_migration_defaults_status_and_reason_and_v4_roundtrip(self):
        state = tournament(2)
        state.save_pool("Pool 01", "", {"1": FightResult("1:0", 10, 7)})
        for version in range(4):
            payload = state.to_dict() | {"schema_version": version}
            for person in payload["participants"]:
                person.pop("withdrawn")
                person.pop("disqualified")
            for pool in payload["pools"]:
                pool.pop("reopen_reason")
                for result in pool["results"].values():
                    result.pop("reason")
            loaded = Tournament.from_dict(payload)
            self.assertTrue(all(not p.withdrawn and not p.disqualified for p in loaded.participants))
            self.assertEqual(loaded.pools[0].results["1"].reason, "played")
        state.set_participant_status("0", "withdrawn")
        state.set_participant_status("1", "disqualified")
        self.assertEqual(Tournament.from_dict(state.to_dict()), state)

    def test_corrupt_status_values_missing_or_inconsistent_awards_are_rejected(self):
        state = tournament(2)
        state.set_participant_status("0", "disqualified")
        for mode in ("missing", "wrong_score", "wrong_status", "invalid_boolean"):
            payload = state.to_dict()
            if mode == "missing":
                payload["pools"][0]["results"].pop("1")
            elif mode == "wrong_score":
                payload["pools"][0]["results"]["1"] = vars(FightResult("1:0", 10, 0))
            elif mode == "wrong_status":
                payload["participants"][0]["disqualified"] = False
            else:
                payload["participants"][0]["withdrawn"] = "false"
            with self.subTest(mode=mode), self.assertRaises(RuleError):
                Tournament.from_dict(payload)


class ParticipantStatusUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        Store(self.folder).save(tournament())
        self.window = Window(self.folder)
        self.addCleanup(self.window.close)

    def test_status_with_entered_injury_is_atomic_and_retry_preserves_inputs(self):
        page = PoolPage(self.window, "Pool 01")
        self.addCleanup(page.close)
        for combo, value in zip(page.editors[0], ("0:1", 7, 10)):
            combo.setCurrentIndex(combo.findData(value))
        page.reason_editors[0].setCurrentIndex(page.reason_editors[0].findData("injury"))
        with patch.object(self.window, "confirm_participant_status", return_value=True):
            with patch.object(self.window.store, "save", side_effect=OSError("voll")):
                self.assertFalse(page.set_status("withdrawn"))
            self.assertFalse(self.window.state.participant("0").withdrawn)
            self.assertEqual(page.editors[0][1].currentData(), 7)
            self.assertTrue(page.set_status("withdrawn"))
        pool = self.window.state.pool("Pool 01")
        self.assertEqual(pool.results["1"], FightResult("0:1", 7, 10, "injury"))
        self.assertTrue(page.editors[0][0].isEnabled())
        self.assertFalse(page.editors[1][0].isEnabled())
        self.assertEqual(page.reason_editors[1].currentData(), "withdrawal")
        self.assertEqual(Store(self.folder).load(), self.window.state)

    def test_overview_confirm_cancel_and_disqualified_page_and_common_file_reload(self):
        self.window.lists["Pool 01"].setCurrentRow(0)
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
            self.assertFalse(self.window.set_selected_status("disqualified"))
        self.assertFalse(self.window.state.participant("0").disqualified)
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(self.window.set_selected_status("disqualified"))
        self.assertIn("Disqualifiziert", self.window.lists["Pool 01"].item(0).text())
        page = PoolPage(self.window, "Pool 01")
        self.addCleanup(page.close)
        self.assertFalse(page.editors[0][0].isEnabled())
        self.assertTrue(page.editors[2][0].isEnabled())
        self.assertEqual(page.standings.item(0, 6).text(), "—")
        self.assertTrue(self.window.reload_participant_file())
        path = self.window.store.participant_path
        people = read_participants(path, with_ids=True)
        people[0].last_name = "Korrektur"
        write_ods(path, people)
        self.assertTrue(self.window.reload_participant_file())
        self.assertTrue(self.window.state.participant("0").disqualified)

    def test_storage_failure_keeps_status_and_all_pools_unchanged(self):
        state = self.window.state
        session = TournamentSession(self.window.store, state)
        before = deepcopy(state)
        with patch.object(self.window.store, "save", side_effect=OSError("voll")):
            with self.assertRaises(OSError):
                session.change(lambda candidate: candidate.set_participant_status("0", "disqualified"))
        self.assertEqual(session.state, before)
        self.assertEqual(self.window.store.load(), before)

    def test_output_uses_same_values_and_explicit_zero_point_reason(self):
        state = tournament(2)
        for p in state.participants:
            p.disqualified = True
        state.save_pool("Pool 01", "", {})
        image = QImage(1100, 740, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        drawn = []

        class RecordingPainter:
            def __getattr__(self, name):
                return getattr(painter, name)

            def drawText(self, rect, flags, text):
                drawn.append((rect.x(), rect.y(), text))
                painter.drawText(rect, flags, text)

        try:
            draw_pool(RecordingPainter(), QRectF(0, 0, 1100, 740), state, state.pools[0])
        finally:
            painter.end()
        content = "\n".join(text for _, _, text in drawn)
        self.assertIn("0 : 0 · 0 Punkte", content)
        self.assertIn("Beide disqualifiziert", content)
        self.assertIn("Disqualifiziert", content)
        # In der gemeinsamen Zeichnung liegt die Platzspalte bei x=1045 (+6 Rand).
        places = [text for x, y, text in drawn if x == 1051 and y > 374]
        self.assertEqual(places, ["", ""])
        self.assertTrue(all(row.place is None for row in state.evaluate_pool("Pool 01")[0]))


if __name__ == "__main__":
    unittest.main()
