"""Echter Start, reproduzierbare Demos und sichere Übernahme vorhandener Stände."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from devtools.demo_data import demo
from devtools.run import prepare_demo
from stadtmeisterschaft.domain import RuleError, Tournament
from stadtmeisterschaft.sheets import read_participants
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.main_window import Window


class AppLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_new_tournament_is_empty_and_stays_empty_after_restart(self):
        window = Window(self.folder)
        try:
            self.assertEqual(window.state.participants, [])
            self.assertEqual(window.state.pools, [])
            self.assertFalse(window.state.is_demo)
            self.assertNotIn("TESTDATEN", window.windowTitle())
        finally:
            window.close()
        window = Window(self.folder)
        try:
            self.assertEqual(window.state.participants, [])
        finally:
            window.close()

    def test_demo_scenarios_are_repeatable_and_explicitly_marked(self):
        for count in (10, 40, 100):
            with self.subTest(count=count):
                state = demo(count)
                self.assertEqual(state.to_dict(), demo(count).to_dict())
                self.assertEqual(len(state.participants), count)
                self.assertTrue(state.is_demo)
                self.assertEqual(state.event_date, "2026-11-18")
                state.validate()

    def test_development_start_resumes_and_fresh_start_keeps_previous_data(self):
        folder = prepare_demo(base=self.folder)
        store = Store(folder)
        state = store.load()
        state.configure("Mein bearbeiteter Test", "2026-12-01")
        store.save(state)
        self.assertEqual(prepare_demo(base=self.folder), folder)
        fresh = prepare_demo(base=self.folder, fresh=True)
        self.assertNotEqual(folder, fresh)
        self.assertEqual(Store(folder).load().name, "Mein bearbeiteter Test")
        self.assertEqual(prepare_demo(base=self.folder), fresh)

    def test_development_start_rejects_real_tournament(self):
        folder = self.folder / "kinder-40-2026"
        folder.mkdir()
        Store(folder).save(Tournament([], []))
        before = (folder / "wettkampf.sqlite3").read_bytes()
        with self.assertRaisesRegex(ValueError, "Demo-Wettkampf"):
            prepare_demo(base=self.folder)
        self.assertEqual(before, (folder / "wettkampf.sqlite3").read_bytes())

    def test_legacy_database_loads_without_renaming_and_upgrades_on_save(self):
        data = demo(10).to_dict()
        data.pop("schema_version")
        data.pop("is_demo")
        path = self.folder / "technikversuch.sqlite3"
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("CREATE TABLE current_state (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)")
                connection.execute("INSERT INTO current_state VALUES (1, 3, ?)", (json.dumps(data),))
        store = Store(self.folder)
        self.assertEqual(store.path, path)
        state = store.load()
        self.assertEqual(len(state.participants), 10)
        self.assertFalse(state.is_demo)  # Alte Daten werden nicht anhand ihrer Namen umklassifiziert.
        store.save(state)
        self.assertFalse((self.folder / "wettkampf.sqlite3").exists())
        self.assertEqual(Store(self.folder).load().to_dict()["schema_version"], 6)

    def test_future_data_format_is_rejected_without_overwriting(self):
        store = Store(self.folder)
        store.save(demo(10))
        with store.connect() as connection:
            data = demo(10).to_dict() | {"schema_version": 99}
            connection.execute("UPDATE current_state SET payload=?", (json.dumps(data),))
        before = store.path.read_bytes()
        with self.assertRaisesRegex(RuleError, "Programmversion"):
            store.load()
        self.assertEqual(before, store.path.read_bytes())

    def test_ambiguous_database_names_are_rejected(self):
        Store(self.folder).save(demo(10))
        (self.folder / "technikversuch.sqlite3").write_bytes((self.folder / "wettkampf.sqlite3").read_bytes())
        with self.assertRaisesRegex(RuntimeError, "zwei Wettkampfdatenbanken"):
            Store(self.folder)

    def test_checked_in_import_fixtures_still_agree(self):
        fixtures = Path(__file__).parent / "fixtures"
        for name, count in [("testmeldungen", 1), ("testmeldungen-40-kinder", 40)]:
            ods = read_participants(fixtures / f"{name}.ods")
            xlsx = read_participants(fixtures / f"{name}.xlsx")
            self.assertEqual(len(ods), count)
            self.assertEqual([vars(person) | {"id": ""} for person in ods],
                             [vars(person) | {"id": ""} for person in xlsx])
