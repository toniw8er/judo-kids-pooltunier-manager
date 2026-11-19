"""SQLite-Snapshot und wiederanlauffähige Übernahme der gemeinsamen ODS-Datei."""
import json
import sqlite3
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from hashlib import sha256

from stadtmeisterschaft.domain import RuleError, Tournament
from stadtmeisterschaft.sheets import ods_content, write_bytes_atomic


class Store:
    def __init__(self, folder: Path):
        legacy = folder / "technikversuch.sqlite3"
        current = folder / "wettkampf.sqlite3"
        if legacy.exists() and current.exists():
            raise RuntimeError("Der Arbeitsordner enthält zwei Wettkampfdatenbanken. Bitte einen eindeutigen Arbeitsordner wählen.")
        # Vorhandene Arbeitsordner bleiben ohne Umbenennen und Kopieren nutzbar.
        self.path = legacy if legacy.exists() else current
        self.revision = 0
        self.participant_path = folder / "teilnehmer.ods"
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS current_state "
                        "(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS participant_file "
                        "(id INTEGER PRIMARY KEY CHECK(id=1), digest TEXT NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS participant_transfer "
                        "(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, "
                        "payload TEXT NOT NULL, before BLOB, after BLOB NOT NULL)")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=2)
        try:
            con.execute("PRAGMA synchronous=FULL")
            with con:
                yield con
        finally:
            con.close()

    def load(self) -> Tournament | None:
        with self.connect() as con:
            row = con.execute("SELECT revision, payload FROM current_state WHERE id=1").fetchone()
        if row is None:
            return None
        state = Tournament.from_dict(json.loads(row[1]))
        self.revision = row[0]
        return state

    def save(self, state: Tournament) -> None:
        state.validate()
        # Revision schützt auch vor versehentlichen konkurrierenden Schreibern.
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            self._check_no_transfer(con)
            row = con.execute("SELECT revision, payload FROM current_state WHERE id=1").fetchone()
            actual = row[0] if row else 0
            if actual != self.revision:
                raise RuntimeError("Der Stand wurde anderweitig geändert. Bitte den Arbeitsordner neu öffnen.")
            prepared, payload = self._prepare_print_revisions(state, row)
            con.execute("INSERT INTO current_state VALUES (1, ?, ?) "
                        "ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, payload=excluded.payload",
                        (actual + 1, payload))
        self.revision = actual + 1
        self._accept_print_revisions(state, prepared)

    @staticmethod
    def _prepare_print_revisions(state: Tournament, row) -> tuple[Tournament, str]:
        prepared = deepcopy(state)
        previous = Tournament.from_dict(json.loads(row[1])) if row else None
        old_pools = {pool.id: pool for pool in previous.pools} if previous else {}
        for pool in prepared.pools:
            old = old_pools.get(pool.id)
            pool.print_revision = (old.print_revision + int(
                previous.pool_print_content(pool.id) != prepared.pool_print_content(pool.id))) if old else 1
        return prepared, json.dumps(prepared.to_dict(), ensure_ascii=False)

    @staticmethod
    def _accept_print_revisions(state: Tournament, prepared: Tournament) -> None:
        for pool, saved in zip(state.pools, prepared.pools):
            pool.print_revision = saved.print_revision

    @staticmethod
    def _check_no_transfer(con):
        if con.execute("SELECT 1 FROM participant_transfer").fetchone():
            raise RuleError("Eine Teilnehmerübernahme ist noch offen. Bitte den Arbeitsordner erneut öffnen.")

    def participant_digest(self) -> str | None:
        with self.connect() as con:
            row = con.execute("SELECT digest FROM participant_file WHERE id=1").fetchone()
        return row[0] if row else None

    def _file_content(self) -> bytes | None:
        try:
            return self.participant_path.read_bytes()
        except FileNotFoundError:
            return None

    def _check_file(self, expected: bytes | None) -> None:
        lock = self.participant_path.with_name(f".~lock.{self.participant_path.name}#")
        if lock.exists():
            raise RuleError("teilnehmer.ods ist in Office geöffnet. Bitte dort speichern und schließen.")
        if self._file_content() != expected:
            raise RuleError("teilnehmer.ods wurde zwischenzeitlich geändert. Bitte erneut einlesen.")

    def save_with_participants(self, state: Tournament, expected: bytes | None) -> None:
        """Dauerhafte Absicht vor Dateitausch; Snapshot erst nach erfolgreichem Tausch."""
        state.validate()
        after = ods_content(state.participants)
        self._check_file(expected)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            self._check_no_transfer(con)
            row = con.execute("SELECT revision, payload FROM current_state WHERE id=1").fetchone()
            actual = row[0] if row else 0
            if actual != self.revision:
                raise RuntimeError("Der Stand wurde anderweitig geändert. Bitte den Arbeitsordner neu öffnen.")
            prepared, payload = self._prepare_print_revisions(state, row)
            con.execute("INSERT INTO participant_transfer VALUES (1, ?, ?, ?, ?)",
                        (actual, payload, expected, after))
        try:
            self._check_file(expected)
            write_bytes_atomic(self.participant_path, after)
        except Exception:
            # Kein Dateitausch: die Absicht kann ohne Rückschreiben verworfen werden.
            with self.connect() as con:
                con.execute("DELETE FROM participant_transfer")
            raise
        # Bei einem Fehler bleibt die Absicht erhalten. Weitere Schreibvorgänge
        # sind gesperrt; erneutes Öffnen setzt exakt diesen Stand fort.
        try:
            completed = self.recover_participants()
        except Exception as exc:
            raise RuleError("Übernahme noch nicht abgeschlossen. Bitte teilnehmer.ods unverändert lassen "
                            "und den Arbeitsordner erneut öffnen. " + str(exc)) from exc
        if not completed:
            raise RuleError("teilnehmer.ods wurde nach dem Schreiben zurückgesetzt. Übernahme nicht gespeichert; bitte erneut einlesen.")
        self._accept_print_revisions(state, prepared)

    def recover_participants(self) -> bool:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT revision, payload, before, after FROM participant_transfer WHERE id=1").fetchone()
            if row is None:
                return False
            revision, payload, before, after = row
            current = self._file_content()
            if current != after and current == before:
                con.execute("DELETE FROM participant_transfer")
                return False
            if current != after:
                raise RuleError("Offene Teilnehmerübernahme: teilnehmer.ods wurde geändert oder fehlt. "
                                "Letzter gespeicherter Stand bleibt erhalten; Datei nicht überschrieben.")
            Tournament.from_dict(json.loads(payload))
            stored = con.execute("SELECT revision FROM current_state WHERE id=1").fetchone()
            if (stored[0] if stored else 0) != revision:
                raise RuleError("Offene Teilnehmerübernahme passt nicht mehr zur Datenbankrevision.")
            con.execute("INSERT INTO current_state VALUES (1, ?, ?) "
                        "ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, payload=excluded.payload",
                        (revision + 1, payload))
            con.execute("INSERT INTO participant_file VALUES (1, ?) "
                        "ON CONFLICT(id) DO UPDATE SET digest=excluded.digest", (sha256(after).hexdigest(),))
            con.execute("DELETE FROM participant_transfer")
        self.revision = revision + 1
        return True
