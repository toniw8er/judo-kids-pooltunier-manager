"""Eine fachliche Aktion erst nach erfolgreichem Speichern übernehmen."""
from copy import deepcopy
from dataclasses import dataclass
from collections.abc import Callable
from hashlib import sha256

from .domain import Participant, RuleError, Tournament
from .participant_import import ImportComparison, ImportResult, compare_import
from .sheets import read_participants
from .storage import Store


@dataclass(frozen=True)
class PreparedImport:
    people: list[Participant]
    comparison: ImportComparison
    base_state: Tournament
    revision: int
    file_content: bytes | None


class TournamentSession:
    def __init__(self, store: Store, state: Tournament):
        self.store = store
        self.state = state

    def change(self, action: Callable[[Tournament], None]) -> Tournament:
        candidate = deepcopy(self.state)
        action(candidate)
        self.store.save(candidate)
        self.state = candidate
        return candidate

    def prepare_import(self, path) -> PreparedImport:
        people = read_participants(path)
        before = self.store._file_content()
        digest = self.store.participant_digest()
        if (digest is None and before is not None) or (digest is not None and (
                before is None or sha256(before).hexdigest() != digest)):
            raise RuleError("Die gemeinsame Teilnehmerdatei zuerst neu einlesen; Import würde externe Änderungen überschreiben.")
        return PreparedImport(people, compare_import(self.state, people), deepcopy(self.state),
                              self.store.revision, before)

    def commit_import(self, prepared: PreparedImport,
                      weights: dict[str, int] | None = None) -> tuple[Tournament, ImportResult]:
        if self.state != prepared.base_state or self.store.revision != prepared.revision:
            raise RuleError("Der Turnierstand wurde seit der Importvorschau geändert. Bitte den Import erneut starten.")
        candidate = deepcopy(self.state)
        result = candidate.add_participants(prepared.people, weights=weights)
        self.store.save_with_participants(candidate, prepared.file_content)
        self.state = candidate
        return candidate, result

    def import_participants(self, path, *, weights: dict[str, int] | None = None) -> Tournament:
        return self.commit_import(self.prepare_import(path), weights)[0]

    def reload_participants(self) -> Tournament:
        path = self.store.participant_path
        before = self.store._file_content()
        digest = self.store.participant_digest()
        if before is None:
            if digest is not None:
                raise RuleError("teilnehmer.ods fehlt. Letzter gespeicherter Stand bleibt erhalten.")
            candidate = deepcopy(self.state)
        else:
            if digest == sha256(before).hexdigest():
                return self.state
            people = read_participants(path, with_ids=True, content=before,
                                       known_ids={p.id for p in self.state.participants})
            candidate = deepcopy(self.state)
            try:
                candidate.replace_participants(people)
            except RuleError as exc:
                raise RuleError(f"{path.name}: {exc}") from exc
        self.store.save_with_participants(candidate, before)
        self.state = candidate
        return candidate

    def check_participants_at_start(self) -> Tournament:
        if self.store.recover_participants():
            self.state = self.store.load()
        if self.store.participant_digest() is not None:
            return self.reload_participants()
        return self.state
