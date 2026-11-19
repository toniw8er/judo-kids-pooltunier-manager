"""Eindeutiger Meldelistenabgleich und bewusste Auswahl geänderter Gewichte."""
from copy import deepcopy
from dataclasses import dataclass

from .domain import Participant, RuleError, Tournament, signature


@dataclass(frozen=True)
class WeightConflict:
    participant_id: str
    name: str
    club: str
    birth_year: int
    gender: str
    old_weight: int
    new_weight: int
    locked: bool


@dataclass(frozen=True)
class ImportComparison:
    new: tuple[Participant, ...]
    unchanged: int
    conflicts: tuple[WeightConflict, ...]


@dataclass(frozen=True)
class ImportResult:
    added: int
    unchanged: int
    updated: int
    kept: int
    locked: int

    @property
    def message(self):
        return (f"Meldungen übernommen · {self.added} neue Kinder · {self.updated} Gewichte aktualisiert · "
                f"{self.unchanged} unverändert übersprungen · {self.kept} bestehende Gewichte beibehalten · "
                f"{self.locked} gesperrte Gewichte übersprungen.")


def compare_import(state: Tournament, incoming: list[Participant]) -> ImportComparison:
    known = {}
    known_ids = {p.id: p for p in state.participants}
    for person in state.participants:
        known.setdefault(signature(person)[:5], []).append(person)
    frozen = {pid for pool in state.pools if pool.started for pid in pool.members}
    seen, ids, new, conflicts = set(), set(), [], []
    unchanged = 0
    for person in incoming:
        key = signature(person)[:5]
        if key in seen or person.id in ids:
            raise RuleError(f"Mehrdeutige Meldung: {person.name} steht mehrfach in der Meldeliste. "
                            "Bitte die Datei bereinigen. Gesamter Import abgelehnt.")
        seen.add(key)
        ids.add(person.id)
        matches = known.get(key, [])
        if len(matches) > 1:
            raise RuleError(f"Mehrdeutiger Treffer: {person.name} ist mehrfach vorhanden. "
                            "Bitte die Teilnehmerdaten bereinigen. Gesamter Import abgelehnt.")
        if person.id in known_ids and (not matches or matches[0].id != person.id):
            raise RuleError(f"Widersprüchliche Teilnehmer-ID: {person.name}. Gesamter Import abgelehnt.")
        if not matches:
            new.append(deepcopy(person))
        elif matches[0].weight_grams == person.weight_grams:
            unchanged += 1
        else:
            old = matches[0]
            conflicts.append(WeightConflict(old.id, old.name, old.club, old.birth_year, old.gender,
                                            old.weight_grams, person.weight_grams, old.id in frozen))
    return ImportComparison(tuple(new), unchanged, tuple(conflicts))


def merge_participants(state: Tournament, incoming: list[Participant],
                       weights: dict[str, int] | None = None) -> ImportResult:
    comparison = compare_import(state, incoming)
    weights = {} if weights is None else weights
    editable = {c.participant_id: c for c in comparison.conflicts if not c.locked}
    if set(weights) != set(editable):
        raise RuleError("Bitte für jeden ungesperrten Gewichtsunterschied das bestehende oder neue Gewicht auswählen.")
    for pid, weight in weights.items():
        conflict = editable[pid]
        if type(weight) is not int or weight not in (conflict.old_weight, conflict.new_weight):
            raise RuleError("Nur das bestehende oder neue Gewicht kann übernommen werden.")
    updated = sum(weights[c.participant_id] == c.new_weight for c in editable.values())
    for pid, weight in weights.items():
        state.participant(pid).weight_grams = weight
    state.participants.extend(comparison.new)
    state.validate()
    return ImportResult(len(comparison.new), comparison.unchanged, updated, len(editable) - updated,
                        sum(c.locked for c in comparison.conflicts))
