"""Bedienabläufe für Poolentfernung, Jahrgangsvorschläge und Testdaten."""
from devtools.demo_data import demo
from devtools.helpers import demo_window, record_result
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from stadtmeisterschaft.age_class_defaults import suggested_classes
from stadtmeisterschaft.ui.main_window import Window
from stadtmeisterschaft.domain import AgeClass
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.tournament_config import TournamentConfig


class UsabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'tmp' / 'tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.temp.name)
        self.window = demo_window(self.folder, 10)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def double_click_child(self, pool_id):
        self.window.show()
        items = self.window.lists[pool_id]
        self.window.scroll.ensureWidgetVisible(items)
        self.app.processEvents()
        point = items.visualItemRect(items.item(0)).center()
        QTest.mouseClick(items.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseDClick(items.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()

    def test_double_click_removes_regular_membership_and_persists(self):
        child = self.window.state.pool('Pool 01').members[0]
        with patch.object(self.window, 'open_pool', side_effect=AssertionError('Poolseite darf nicht öffnen')):
            self.double_click_child('Pool 01')
        self.assertNotIn(child, Store(self.folder).load().pool('Pool 01').members)
        self.assertIn(child, [self.window.lists[''].item(i).data(Qt.ItemDataRole.UserRole)
                              for i in range(self.window.lists[''].count())])

    def test_double_click_friendship_preserves_regular_and_other_friendship(self):
        child = self.window.state.pool('Pool 01').members[0]
        first = self.window.create_pool('friendship')
        second = self.window.create_pool('friendship')
        self.window.move(child, first)
        self.window.move(child, second)
        self.double_click_child(first)
        loaded = Store(self.folder).load()
        self.assertNotIn(child, loaded.pool(first).members)
        self.assertIn(child, loaded.pool(second).members)
        self.assertIn(child, loaded.pool('Pool 01').members)

    def test_double_click_started_pool_and_failed_write_preserve_memberships(self):
        before = self.window.state.to_dict()
        with patch.object(self.window.store, 'save', side_effect=OSError('Datenträger voll')):
            self.double_click_child('Pool 01')
        self.assertEqual(self.window.state.to_dict(), before)
        self.window.change(lambda state: record_result(state, 'Pool 01', 'Erstes Kind', 10, 0), 'Test')
        before = self.window.state.to_dict()
        self.double_click_child('Pool 01')
        self.assertEqual(self.window.state.to_dict(), before)
        self.assertIn('gesperrt', self.window.message.text())

    def test_proposals_follow_event_year_and_preserve_overlap(self):
        expected = [[2018, 2019], [2016, 2017, 2018], [2014, 2015, 2016],
                    [2012, 2013, 2014], [2009, 2010, 2011]]
        self.assertEqual([c.name for c in suggested_classes(2026)], ['U9', 'U11', 'U13', 'U15', 'U18'])
        self.assertEqual([c.years for c in suggested_classes(2026)], expected)
        self.assertEqual([c.years for c in suggested_classes(2027)], [[y+1 for y in row] for row in expected])

    def test_proposals_preserve_custom_values_and_mixed_flags(self):
        dialog = TournamentConfig(self.window)
        dialog.event_date.setDate(QDate(2026, 5, 1))
        dialog.add_class(AgeClass('U11', [2015, 2016], True))
        dialog.suggest_classes()
        dialog.suggest_classes()
        self.assertEqual(dialog.classes.rowCount(), 5)
        self.assertEqual(dialog.classes.item(0, 1).text(), '2015–2016')
        self.assertTrue(dialog.classes.cellWidget(0, 2).isChecked())
        dialog.event_date.setDate(QDate(2027, 5, 1))
        self.assertEqual(dialog.classes.item(0, 1).text(), '2015–2016')
        dialog.save()
        loaded = Store(self.folder).load()
        self.assertEqual(loaded.age_classes[0], AgeClass('U11', [2015, 2016], True))
        self.assertEqual(next(c.years for c in loaded.age_classes if c.name=='U13'), [2015, 2016, 2017])

    def test_known_class_name_prefills_empty_years_and_manual_edit_survives_date_change(self):
        dialog = TournamentConfig(self.window)
        dialog.event_date.setDate(QDate(2026, 5, 1))
        dialog.add_class()
        dialog.classes.item(0, 0).setText('u 13')
        self.assertEqual(dialog.classes.item(0, 1).text(), '2014–2016')
        dialog.event_date.setDate(QDate(2027, 5, 1))
        self.assertEqual(dialog.classes.item(0, 1).text(), '2015–2017')
        dialog.classes.item(0, 1).setText('2014, 2016')
        dialog.event_date.setDate(QDate(2028, 5, 1))
        self.assertEqual(dialog.classes.item(0, 1).text(), '2014, 2016')
        dialog.reject()
        self.assertEqual(self.window.state.age_classes, [])

    def test_default_demo_has_variety_and_existing_folder_is_preserved(self):
        state = demo()
        self.assertEqual(len(state.participants), 40)
        self.assertGreaterEqual(len({p.birth_year for p in state.participants}), 10)
        self.assertEqual(min(p.birth_year for p in state.participants), 2026-17)
        self.assertEqual(max(p.birth_year for p in state.participants), 2026-5)
        weights = [p.weight_grams for p in state.participants]
        self.assertEqual((min(weights), max(weights)), (17500, 67200))
        self.assertEqual(sum(len(p.members) for p in state.pools), 35)
        state.validate()
        self.window.close()
        self.window = Window(self.folder)
        self.assertEqual(len(self.window.state.participants), 10)


if __name__ == '__main__':
    unittest.main()
