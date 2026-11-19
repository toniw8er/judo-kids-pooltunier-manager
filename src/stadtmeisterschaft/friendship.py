"""Erklärbare Vorschläge für zusätzliche Freundschaftsteilnahmen."""
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path
import json

from .domain import AgeClass, RuleError, Tournament


def load_age_factor(folder: Path) -> int:
    path = folder / "freundschaft.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 8
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuleError(f"{path.name}: Konfiguration nicht lesbar: {exc}") from exc
    if (not isinstance(data, dict) or set(data) != {"altersfaktor"}
            or type(data["altersfaktor"]) is not int or data["altersfaktor"] < 0):
        raise RuleError(f'{path.name}: Erwartet wird {{"altersfaktor": 8}} mit einer ganzen Zahl ab 0.')
    return data["altersfaktor"]


def ordered_classes(state: Tournament) -> list[AgeClass]:
    return sorted(state.age_classes, key=lambda c: (-max(c.years), -min(c.years), c.name.casefold()))


def participant_class(state: Tournament, pid: str) -> AgeClass | None:
    classes = ordered_classes(state)
    actual = next((p.age_class for p in state.pools if not p.is_friendship and pid in p.members and p.age_class), "")
    if actual:
        return next((c for c in classes if c.name == actual), None)
    year = state.participant(pid).birth_year
    return next((c for c in classes if year in c.years), None)


@dataclass(frozen=True)
class Suggestion:
    participant_id: str
    score: Fraction
    weight_distance: Fraction
    class_steps: int
    age_class: str
    notes: tuple[str, ...]


def pair_distance(state: Tournament, first: str, second: str, factor: int) -> tuple[Fraction, Fraction, int]:
    a, b = state.participant(first), state.participant(second)
    classes = ordered_classes(state)
    ca, cb = participant_class(state, first), participant_class(state, second)
    if ca is None or cb is None:
        raise RuleError("Für die Rangfolge bitte passende Altersklassen konfigurieren bzw. die gespeicherte Startklasse wiederherstellen.")
    steps = abs(classes.index(ca) - classes.index(cb))
    weight = Fraction(100 * abs(a.weight_grams - b.weight_grams), min(a.weight_grams, b.weight_grams))
    return weight + factor * steps ** 2, weight, steps


def group_warnings(state: Tournament, source_id: str, selected: list[str]) -> list[str]:
    preview = deepcopy(state)
    source = preview.pool(source_id)
    source.members += list(selected)
    if not source.is_friendship:
        source.kind, source.age_class = "friendship", ""
    notes = preview.pool_warnings(source_id)
    for pid in source.members:
        person = preview.participant(pid)
        notes.extend(f"{person.name}: {note}" for note in preview.pool_member_warnings(source_id, pid))
    # Auch bei verschiedenen Altersklassen alle Geschlechterpaare prüfen.
    origin = participant_class(state, state.pool(source_id).members[0])
    for a, b in combinations(source.members, 2):
        if (preview.participant(a).gender != preview.participant(b).gender
                and origin and not origin.mixed):
            notes.append(f"{preview.participant(a).name} / {preview.participant(b).name}: "
                         "Geschlechtermischung in der Ausgangsklasse nicht freigegeben.")
    return list(dict.fromkeys(notes))


def suggestions(state: Tournament, source_id: str, selected: list[str], factor: int = 8) -> list[Suggestion]:
    if type(factor) is not int or factor < 0:
        raise RuleError("Der Altersfaktor muss eine ganze Zahl ab 0 sein.")
    if not state.friendship_search_available(source_id):
        raise RuleError("Dieser Pool kann nicht um Freundschaftspartner ergänzt werden.")
    source = state.pool(source_id)
    group = source.members + list(selected)
    if len(group) > 5 or len(set(group)) != len(group):
        raise RuleError("Höchstens fünf verschiedene Kinder je Freundschaftspool.")
    if any(state.participant(pid).withdrawn or state.participant(pid).disqualified for pid in group):
        raise RuleError("Zurückgezogene oder disqualifizierte Kinder können nicht für neue Freundschaftskämpfe gewählt werden.")
    # Die Ausgangsgruppe bleibt für den Geschlechterfilter maßgeblich.
    for pid in group:
        if participant_class(state, pid) is None:
            raise RuleError("Für die Rangfolge bitte passende Altersklassen konfigurieren bzw. die gespeicherte Startklasse wiederherstellen.")
    if len(group) == 5:
        return []
    result = []
    for person in state.participants:
        age_class = participant_class(state, person.id)
        if person.id in group or person.withdrawn or person.disqualified or age_class is None:
            continue
        origin = state.participant(source.members[0])
        if person.gender != origin.gender and not participant_class(state, origin.id).mixed:
            continue
        pairs = [pair_distance(state, a, b, factor) for a, b in combinations(group + [person.id], 2)]
        score, weight, steps = max(pairs)
        result.append(Suggestion(person.id, score, weight, steps, age_class.name,
                                 tuple(group_warnings(state, source_id, selected + [person.id]))))
    return sorted(result, key=lambda s: (s.score, state.participant(s.participant_id).name.casefold(), s.participant_id))
