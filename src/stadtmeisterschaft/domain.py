"""Turnierdaten und Fachregeln, unabhängig von Qt."""
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from uuid import uuid4


FIGHT_ORDER = {2: [(1, 2)] * 3, 3: [(1, 2), (1, 3), (2, 3)],
               4: [(1, 2), (3, 4), (1, 3), (2, 4), (1, 4), (2, 3)],
               5: [(1, 2), (3, 4), (1, 5), (2, 3), (4, 5),
                   (1, 3), (2, 5), (1, 4), (3, 5), (2, 4)]}


class RuleError(ValueError):
    """Eine Eingabe oder Aktion ist fachlich nicht zulässig."""


@dataclass
class Participant:
    id: str
    first_name: str
    last_name: str
    club: str
    birth_year: int
    gender: str
    weight_grams: int
    withdrawn: bool = False
    disqualified: bool = False
    bookmark: str | None = None

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def status_label(self) -> str:
        return "Disqualifiziert" if self.disqualified else "Zurückgezogen" if self.withdrawn else "Aktiv"


RESULT_REASONS = {
    "played": "Ausgetragen", "injury": "Aufgabe / Verletzung",
    "nonattendance": "Nichtantritt", "withdrawal": "Rückzug",
    "both_withdrawn": "Beide zurückgezogen · ohne Punkte",
    "disqualification": "Disqualifikation",
    "both_disqualified": "Beide disqualifiziert · ohne Punkte",
}
AUTOMATIC_REASONS = {"withdrawal", "both_withdrawn", "disqualification", "both_disqualified"}


@dataclass
class FightResult:
    outcome: str
    first: int
    second: int
    reason: str = "played"

    @property
    def automatic(self) -> bool:
        return self.reason in AUTOMATIC_REASONS

    @property
    def zero_points(self) -> bool:
        return self.reason in {"both_withdrawn", "both_disqualified"}

    def validate(self) -> None:
        if self.reason not in RESULT_REASONS:
            raise RuleError("Unbekannter Ergebnisgrund.")
        if self.outcome not in {"1:0", "0:1", "0:0"}:
            raise RuleError("Als Ausgang bitte 1:0, 0:1 oder 0:0 auswählen.")
        if any(type(value) is not int or value not in {0, 5, 7, 10}
               for value in (self.first, self.second)):
            raise RuleError("Unterbewertungen müssen 0, 5, 7 oder 10 sein.")
        if self.zero_points:
            if (self.outcome, self.first, self.second) != ("0:0", 0, 0):
                raise RuleError("Bei beidseitigem Rückzug oder Disqualifikation müssen sämtliche Werte null sein.")
        elif self.reason != "played":
            winner, loser = ((self.first, self.second) if self.outcome == "1:0" else (self.second, self.first))
            if self.outcome == "0:0" or winner != 10 or (self.reason != "injury" and loser != 0):
                raise RuleError("Kampflose Siege benötigen UB 10:0; bei Aufgabe bleibt die UB des Verlierers erhalten.")


@dataclass
class AgeClass:
    name: str
    years: list[int]
    mixed: bool = False

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise RuleError("Jede Altersklasse benötigt einen Namen.")
        if not self.years or any(type(year) is not int or not 1900 <= year <= 2100 for year in self.years):
            raise RuleError(f"{self.name}: Bitte gültige Jahrgänge zwischen 1900 und 2100 festlegen.")
        if type(self.mixed) is not bool:
            raise RuleError("Die Freigabe gemischter Gruppen muss ein Ja/Nein-Wert sein.")


def parse_years(value: str) -> list[int]:
    """Explizite Jahrgänge, z. B. 2016-2018 oder 2014, 2016; keine Regelableitung."""
    years = set()
    for token in re.split(r"[,;]", value.replace("–", "-").replace("—", "-")):
        match = re.fullmatch(r"\s*(\d{4})(?:\s*-\s*(\d{4}))?\s*", token)
        if not match:
            raise RuleError("Jahrgänge z. B. als 2016-2018 oder 2014, 2016 eingeben.")
        first, last = int(match[1]), int(match[2] or match[1])
        if not 1900 <= first <= last <= 2100:
            raise RuleError("Jahrgangsbereiche müssen aufsteigend zwischen 1900 und 2100 liegen.")
        years.update(range(first, last + 1))
    return sorted(years)


def format_years(years: list[int]) -> str:
    groups = []
    for year in sorted(set(years)):
        if groups and year == groups[-1][-1] + 1:
            groups[-1].append(year)
        else:
            groups.append([year])
    return ", ".join(str(group[0]) if len(group) == 1 else f"{group[0]}–{group[-1]}" for group in groups)


@dataclass
class Pool:
    id: str
    members: list[str] = field(default_factory=list)
    started: bool = False
    name: str = ""
    results: dict[str, FightResult] = field(default_factory=dict)
    kind: str = "regular"
    age_class: str = ""
    completed: bool = False
    reopened: bool = False
    reopen_reason: str = ""
    mat: str = ""
    print_revision: int = 1
    bookmark: str | None = None

    @property
    def is_friendship(self) -> bool:
        return self.kind == "friendship"

    @property
    def display_name(self) -> str:
        return f"{self.id} · {self.name}" if self.name else self.id

    @property
    def fight_order(self) -> list[tuple[int, int]]:
        return FIGHT_ORDER.get(len(self.members), [])

    @property
    def third_fight_optional(self) -> bool:
        first, second = self.results.get("1"), self.results.get("2")
        return bool(len(self.members) == 2 and first and second
                    and first.outcome == second.outcome and first.outcome != "0:0")

    @property
    def missing_required_fights(self) -> list[int]:
        return [n for n in range(1, len(self.fight_order) + 1)
                if str(n) not in self.results and not (n == 3 and self.third_fight_optional)]

    @property
    def ready_to_complete(self) -> bool:
        return bool(self.fight_order) and not self.missing_required_fights

    @property
    def evaluation_note(self) -> str:
        if self.completed:
            return "Abgeschlossen"
        if self.reopened:
            if self.reopen_reason:
                return self.reopen_reason + " Bitte den Pool erneut abschließen."
            if len(self.members) == 2 and self.missing_required_fights == [3]:
                return "Durch Ergebniskorrektur ist Kampf 3 wieder verpflichtend. Pool wieder offen."
            if self.ready_to_complete:
                return "Ergebnisse wieder vollständig. Bitte den Pool erneut abschließen."
            return "Durch Ergebniskorrektur fehlen Pflichtkämpfe. Pool wieder offen."
        if not self.fight_order:
            return "Noch kein Partner – keine Platzierung"
        if self.ready_to_complete:
            return "Vorläufige Platzierungen · Pool noch nicht abgeschlossen"
        return "Zwischenstand · Pflichtkämpfe fehlen · noch keine Platzierungen"

@dataclass
class Tournament:
    participants: list[Participant]
    pools: list[Pool]
    name: str = "Stadtmeisterschaft"
    event_date: str = field(default_factory=lambda: date.today().isoformat())
    age_classes: list[AgeClass] = field(default_factory=list)
    next_pool_number: int = 1
    is_demo: bool = False

    def to_dict(self) -> dict:
        return {"schema_version": 6, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "Tournament":
        version = data.get("schema_version", 0)
        if type(version) is not int or version not in (0, 1, 2, 3, 4, 5, 6):
            raise RuleError("Dieser Wettkampfstand benötigt eine andere Programmversion.")
        pools = []
        for entry in data["pools"]:
            values = dict(entry)
            # Version 0/1 hatte keine tatsächliche Startklasse. Keine erraten.
            if version < 2:
                values["age_class"] = ""
            if version < 3:
                values.update(completed=False, reopened=False)
            if version < 4:
                values["reopen_reason"] = ""
            if version < 5:
                values.update(mat="", print_revision=1)
            if version < 6:
                values["bookmark"] = None
            legacy = values.pop("test_result", None)
            values["results"] = {number: FightResult(**(result if version >= 4 else dict(result, reason="played")))
                                 for number, result in values.get("results", {}).items()}
            if legacy and not values["results"]:
                if legacy["participants"] != values["members"][:2]:
                    raise RuleError("Das alte Testergebnis passt nicht zur Poolbesetzung.")
                outcome = {"Erstes Kind": "1:0", "Zweites Kind": "0:1", "Unentschieden": "0:0"}
                values["results"]["1"] = FightResult(outcome[legacy["winner"]], legacy["first"], legacy["second"])
            pools.append(Pool(**values))
        participants = []
        for entry in data["participants"]:
            values = dict(entry)
            if version < 4:
                values.update(withdrawn=False, disqualified=False)
            if version < 6:
                values["bookmark"] = None
            participants.append(Participant(**values))
        state = cls(participants,
                    pools,
                    name=data.get("name", "Stadtmeisterschaft"),
                    event_date=data.get("event_date", ""),
                    age_classes=[AgeClass(**entry) for entry in data.get("age_classes", [])],
                    next_pool_number=data.get("next_pool_number", 1),
                    is_demo=data.get("is_demo", False))
        if "next_pool_number" not in data:
            numbers = [int(pool.id.split()[-1]) for pool in pools if pool.id.split()[-1].isdigit()]
            state.next_pool_number = max(numbers, default=0) + 1
        state.validate()
        return state

    def validate(self) -> None:
        if type(self.is_demo) is not bool:
            raise RuleError("Ungültige Kennzeichnung der Entwicklungsdaten.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise RuleError("Bitte einen Wettkampfnamen eintragen.")
        if not isinstance(self.event_date, str):
            raise RuleError("Bitte ein gültiges Wettkampfdatum auswählen.")
        if self.event_date:
            self._check_date(self.event_date)
        self._validate_age_classes(self.age_classes)
        if type(self.next_pool_number) is not int or self.next_pool_number < 1:
            raise RuleError("Ungültiger Zähler für neue Pools.")
        for entity in [*self.participants, *self.pools]:
            if entity.bookmark is not None and not isinstance(entity.bookmark, str):
                raise RuleError("Eine Lesezeichennotiz muss ein Text sein.")
        ids = [p.id for p in self.participants]
        if any(type(p.withdrawn) is not bool or type(p.disqualified) is not bool for p in self.participants):
            raise RuleError("Ungültiger Teilnehmerstatus.")
        if len(ids) != len(set(ids)):
            raise RuleError("Doppelte Teilnehmer-ID im gespeicherten Stand.")
        pool_ids = [p.id for p in self.pools]
        if len(pool_ids) != len(set(pool_ids)):
            raise RuleError("Doppelte Pool-ID.")
        assigned = []
        for pool in self.pools:
            if not isinstance(pool.reopen_reason, str) or (pool.reopen_reason and not pool.reopened):
                raise RuleError("Ungültiger Wiederöffnungsgrund.")
            if pool.kind not in {"regular", "friendship"}:
                raise RuleError("Unbekannte Poolart.")
            self._validate_pool_results(pool, pool.results)
            if type(pool.completed) is not bool or type(pool.reopened) is not bool:
                raise RuleError("Ungültiger Poolabschlussstatus.")
            if pool.completed and (not pool.started or not pool.ready_to_complete or pool.reopened):
                raise RuleError("Ein abgeschlossener Pool benötigt vollständige Pflichtkämpfe und eine gesperrte Besetzung.")
            if pool.reopened and not pool.started:
                raise RuleError("Ein wieder geöffneter Pool muss in seiner Besetzung gesperrt bleiben.")
            if not isinstance(pool.name, str):
                raise RuleError("Der Poolname muss ein Text sein.")
            if not isinstance(pool.mat, str):
                raise RuleError("Die Mattenangabe muss ein Text sein.")
            if type(pool.print_revision) is not int or pool.print_revision < 1:
                raise RuleError("Ungültige Standnummer der Poolliste.")
            if not isinstance(pool.age_class, str):
                raise RuleError("Die Startklasse muss ein Text sein.")
            if pool.results and not pool.started:
                raise RuleError("Ein Pool mit Ergebnissen muss als gestartet gespeichert sein.")
            if len(pool.members) > 5:
                raise RuleError("Ein Pool darf höchstens fünf Kinder enthalten.")
            if len(pool.members) != len(set(pool.members)):
                raise RuleError("Ein Kind darf innerhalb eines Pools nur einmal vorkommen.")
            if not set(pool.members).issubset(ids):
                raise RuleError("Ein Pool verweist auf unbekannte Kinder.")
            for number, (a, b) in enumerate(pool.fight_order, 1):
                first, second = self.participant(pool.members[a - 1]), self.participant(pool.members[b - 1])
                result = pool.results.get(str(number))
                expected = self._status_result(first, second)
                optional = len(pool.members) == 2 and number == 3 and pool.third_fight_optional
                if expected and result is None and not optional:
                    raise RuleError("Eine verpflichtende Statuswertung fehlt.")
                if (first.disqualified or second.disqualified) and result is not None and result != expected:
                    raise RuleError("Eine Disqualifikationswertung passt nicht zum Teilnehmerstatus.")
                if result and result.automatic and not (first.disqualified or second.disqualified):
                    valid = ((result.reason == "withdrawal" and (first.withdrawn or second.withdrawn)) or
                             (result.reason == "both_withdrawn" and first.withdrawn and second.withdrawn))
                    if not valid:
                        raise RuleError("Eine automatische Wertung passt nicht zum Teilnehmerstatus.")
            if not pool.is_friendship:
                assigned.extend(pool.members)
        if len(assigned) != len(set(assigned)):
            raise RuleError("Ein Kind darf nur einem regulären Pool angehören.")

    @staticmethod
    def _check_date(value: str) -> None:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError
        except (TypeError, ValueError):
            raise RuleError("Bitte ein gültiges Wettkampfdatum auswählen.") from None

    @staticmethod
    def _validate_age_classes(classes: list[AgeClass]) -> None:
        names = []
        for age_class in classes:
            age_class.validate()
            names.append(age_class.name.strip().casefold())
        if len(names) != len(set(names)):
            raise RuleError("Altersklassen müssen unterschiedliche Namen haben.")

    def configure(self, name: str, event_date: str, age_classes: list[AgeClass] | None = None) -> None:
        name = name.strip()
        if not name:
            raise RuleError("Bitte einen Wettkampfnamen eintragen.")
        self._check_date(event_date)
        if age_classes is not None:
            self._validate_age_classes(age_classes)
        self.name, self.event_date = name, event_date
        if age_classes is not None:
            self.age_classes = [AgeClass(c.name.strip(), sorted(set(c.years)), c.mixed) for c in age_classes]

    def create_pool(self, kind: str = "regular", name: str = "") -> str:
        if kind not in {"regular", "friendship"}:
            raise RuleError("Bitte einen regulären Pool oder Freundschaftspool anlegen.")
        if not isinstance(name, str):
            raise RuleError("Der Poolname muss ein Text sein.")
        # Bestehende Kennungen erhalten, Lücken auch aus älteren Ständen nutzen.
        number = 1
        used_ids = {pool.id for pool in self.pools}
        while f"Pool {number:02}" in used_ids:
            number += 1
        pool_id = f"Pool {number:02}"
        self.pools.append(Pool(pool_id, name=name.strip(), kind=kind))
        self.next_pool_number = max(self.next_pool_number, number + 1)
        return pool_id

    def delete_pool(self, pool_id: str) -> None:
        pool = self.pool(pool_id)
        if pool.started:
            raise RuleError("Gestartete Pools dürfen nicht gelöscht werden.")
        self.pools.remove(pool)

    def common_age_classes(self, pool_id: str) -> list[AgeClass]:
        pool = self.pool(pool_id)
        if not pool.members:
            return []
        return [c for c in self.age_classes
                if all(self.participant(pid).birth_year in c.years for pid in pool.members)]

    def friendship_search_available(self, pool_id: str) -> bool:
        pool = self.pool(pool_id)
        return (not pool.started and 1 <= len(pool.members) < 5
                and (pool.is_friendship or len(pool.members) == 1))

    def add_friendship_partners(self, pool_id: str, partners: list[str]) -> str:
        """Gruppe vollständig prüfen, bevor eine zusätzliche Teilnahme entsteht."""
        pool = self.pool(pool_id)
        if not self.friendship_search_available(pool_id):
            raise RuleError("Partnersuche braucht einen ungestarteten Einzelpool oder einen Freundschaftspool mit 1–4 Kindern.")
        if not partners or len(set(partners)) != len(partners):
            raise RuleError("Bitte mindestens einen Partner ohne doppelte Auswahl wählen.")
        members = pool.members + list(partners)
        if len(members) > 5 or len(set(members)) != len(members):
            raise RuleError("Höchstens fünf verschiedene Kinder je Freundschaftspool.")
        known = {p.id: p for p in self.participants}
        if any(pid not in known for pid in members):
            raise RuleError("Ein ausgewähltes Kind ist nicht mehr vorhanden.")
        if any(known[pid].withdrawn or known[pid].disqualified for pid in members):
            raise RuleError("Zurückgezogene oder disqualifizierte Kinder können nicht für neue Freundschaftskämpfe gewählt werden.")
        target = pool if pool.is_friendship else self.pool(self.create_pool("friendship"))
        target.members = members
        return target.id

    def recreate_regular_pools(self) -> None:
        from .pool_planning import plan_pools

        if not self.age_classes:
            raise RuleError("Bitte zuerst Altersklassen konfigurieren.")
        self.validate()
        protected = [p for p in self.pools if p.started or p.is_friendship]
        fixed = {pid for pool in protected if not pool.is_friendship for pid in pool.members}
        planned, _ = plan_pools([p for p in self.participants if p.id not in fixed], self.age_classes)
        # Erst nach vollständiger Berechnung bestehende Pools ersetzen.
        self.pools = protected
        for entry in planned:
            pool = self.pool(self.create_pool())
            pool.members = list(entry.members)
            pool.age_class = entry.age_class
            self._apply_status_results(pool)

    def participant_planning_note(self, participant_id: str) -> str:
        child = self.participant(participant_id)
        if not any(child.birth_year in c.years for c in self.age_classes):
            return "Keine passende Altersklasse konfiguriert"
        return ""

    def pool_class_note(self, pool_id: str) -> str:
        pool = self.pool(pool_id)
        if pool.age_class:
            return "Startklasse: " + pool.age_class
        classes = self.common_age_classes(pool_id)
        return "Jahrgangszuordnung: " + ", ".join(c.name for c in classes) if classes else ""

    def other_friendship_note(self, participant_id: str, pool_id: str) -> str:
        others = [p.display_name for p in self.pools
                  if p.is_friendship and p.id != pool_id and participant_id in p.members]
        return "Bereits in anderem Freundschaftspool: " + ", ".join(others) if others else ""

    def pool_member_warnings(self, pool_id: str, participant_id: str) -> list[str]:
        pool = self.pool(pool_id)
        child = self.participant(participant_id)
        people = [self.participant(pid) for pid in pool.members]
        note = self.participant_planning_note(participant_id)
        warnings = [note] if note else []
        if pool.is_friendship:
            friendship_note = self.other_friendship_note(participant_id, pool_id)
            if friendship_note:
                warnings.append(friendship_note)
        classes = [c for c in self.age_classes if not pool.age_class or c.name == pool.age_class]
        if pool.age_class and classes and child.birth_year not in classes[0].years:
            warnings.append(f"Jahrgang passt nicht zur Startklasse {pool.age_class}.")
        elif not pool.age_class and not note:
            eligible = [p for p in people if not self.participant_planning_note(p.id)]
            if not any(all(p.birth_year in c.years for p in eligible) for c in classes):
                warnings.append("Jahrgänge im Pool haben keine gemeinsame Altersklasse.")
        for other in people:
            if other.id == child.id:
                continue
            shared = [c for c in classes if child.birth_year in c.years and other.birth_year in c.years]
            if child.gender != other.gender and shared and not any(c.mixed for c in shared):
                warnings.append(f"Geschlechtermischung mit {other.name} nicht freigegeben.")
            if max(child.weight_grams, other.weight_grams) * 10 > min(child.weight_grams, other.weight_grams) * 11:
                warnings.append(f"Gewicht: mehr als 10 % Abstand zu {other.name}.")
        return warnings

    def sorted_pools(self) -> list[Pool]:
        def key(pool):
            people = [self.participant(pid) for pid in pool.members]
            classes = [c for c in self.age_classes if c.name == pool.age_class] if pool.age_class else [
                c for c in self.age_classes if any(p.birth_year in c.years for p in people)]
            # Manuelle Pools ohne feste Klasse nach der am besten passenden,
            # bei Gleichstand jüngsten Klasse einordnen.
            age_class = min(classes, key=lambda c: (
                -sum(p.birth_year in c.years for p in people), -max(c.years), -min(c.years), c.name.casefold()
            ), default=None)
            weights = [p.weight_grams for p in people]
            return (not bool(people), age_class is None,
                    -max(age_class.years) if age_class else 0,
                    -min(age_class.years) if age_class else 0,
                    age_class.name.casefold() if age_class else pool.age_class.casefold(),
                    min(weights, default=0), max(weights, default=0), pool.id)
        return sorted(self.pools, key=key)

    def pool_weight_note(self, pool_id: str) -> str:
        weights = [self.participant(pid).weight_grams for pid in self.pool(pool_id).members]
        return (f"{min(weights) / 1000:.1f}–{max(weights) / 1000:.1f} kg".replace(".", ",")
                if weights else "")

    def pool_warnings(self, pool_id: str) -> list[str]:
        pool = self.pool(pool_id)
        if not pool.members:
            return []
        people = [self.participant(pid) for pid in pool.members]
        warnings = []
        classes = self.common_age_classes(pool_id)
        if pool.reopened:
            warnings.append(pool.evaluation_note)
        if not pool.is_friendship and len(people) == 1:
            warnings.append("Einzelpool: noch kein regelkonformer Partner zugeordnet.")
        if pool.age_class:
            classes = [c for c in classes if c.name == pool.age_class]
            if not classes:
                warnings.append(f"Startklasse {pool.age_class}: nach aktuellen Jahrgängen nicht passend oder nicht mehr konfiguriert.")
        if self.age_classes:
            if not classes:
                warnings.append("Keine gemeinsame konfigurierte Altersklasse.")
            elif len({p.gender for p in people}) > 1 and not any(c.mixed for c in classes):
                warnings.append("Mädchen/Jungen gemeinsam: in keiner passenden Altersklasse freigegeben.")
        weights = [p.weight_grams for p in people]
        if max(weights) * 10 > min(weights) * 11:
            warnings.append("Gewichtsspanne überschreitet die 10-Prozent-Grenze.")
        return warnings

    def participant(self, participant_id: str) -> Participant:
        return next(p for p in self.participants if p.id == participant_id)

    def pool(self, pool_id: str) -> Pool:
        return next(p for p in self.pools if p.id == pool_id)

    def move(self, participant_id: str, target_id: str, source_id: str | None = None) -> None:
        self.participant(participant_id)
        target = self.pool(target_id) if target_id else None
        regular_source = next((p for p in self.pools if not p.is_friendship and participant_id in p.members), None)
        if source_id is None:
            source = regular_source
        else:
            source = self.pool(source_id) if source_id else None
        if source and participant_id not in source.members:
            raise RuleError("Das Kind ist dem Ausgangspool nicht zugeordnet.")
        if target and target.is_friendship:
            if participant_id in target.members:
                if source is target:
                    return
                raise RuleError("Das Kind nimmt an diesem Freundschaftspool bereits teil.")
            if target.started:
                raise RuleError("Gestartete Pools sind gesperrt.")
            if len(target.members) >= 5:
                raise RuleError("Der Zielpool ist voll: höchstens fünf Kinder pro Pool.")
            target.members.append(participant_id)
            self._apply_status_results(target)
            return
        if target:
            source = regular_source
        if source is target:
            return
        if (target and target.started) or (source and source.started):
            raise RuleError("Gestartete Pools sind gesperrt. Das Kind bleibt an seinem Platz.")
        if target and len(target.members) >= 5:
            raise RuleError("Der Zielpool ist voll: höchstens fünf Kinder pro Pool.")
        if source:
            source.members.remove(participant_id)
        if target:
            target.members.append(participant_id)
            self._apply_status_results(target)

    def evaluate_pool(self, pool_id: str):
        from .scoring import evaluate_pool
        return evaluate_pool(self.pool(pool_id), disqualified={p.id for p in self.participants if p.disqualified})

    def set_participant_status(self, participant_id: str, status: str) -> None:
        if status not in {"withdrawn", "disqualified"}:
            raise RuleError("Rückzug und Disqualifikation sind endgültig und können nicht zurückgenommen werden.")
        person = self.participant(participant_id)
        if getattr(person, status):
            return
        setattr(person, status, True)
        for pool in self.pools:
            if participant_id not in pool.members:
                continue
            before = dict(pool.results)
            self._apply_status_results(pool)
            if pool.completed and (before != pool.results or status == "disqualified"):
                pool.completed, pool.reopened = False, True
                cause = "eine Disqualifikation" if status == "disqualified" else "einen Rückzug"
                pool.reopen_reason = f"Durch {cause} wurde die Wertung geändert."

    def _apply_status_results(self, pool: Pool) -> None:
        for number, (a, b) in enumerate(pool.fight_order, 1):
            key = str(number)
            old = pool.results.get(key)
            if len(pool.members) == 2 and number == 3 and old is None and pool.third_fight_optional:
                continue
            first, second = self.participant(pool.members[a - 1]), self.participant(pool.members[b - 1])
            result = self._status_result(first, second) if old is None or first.disqualified or second.disqualified else None
            if result is not None:
                pool.results[key] = result
        pool.started = pool.started or bool(pool.results)

    @staticmethod
    def _status_result(first: Participant, second: Participant) -> FightResult | None:
        if first.disqualified and second.disqualified:
            return FightResult("0:0", 0, 0, "both_disqualified")
        if first.disqualified or second.disqualified:
            return (FightResult("0:1", 0, 10, "disqualification") if first.disqualified
                    else FightResult("1:0", 10, 0, "disqualification"))
        if first.withdrawn and second.withdrawn:
            return FightResult("0:0", 0, 0, "both_withdrawn")
        if first.withdrawn or second.withdrawn:
            return (FightResult("0:1", 0, 10, "withdrawal") if first.withdrawn
                    else FightResult("1:0", 10, 0, "withdrawal"))
        return None

    @staticmethod
    def _validate_pool_results(pool: Pool, results: dict[str, FightResult]) -> None:
        allowed = {str(number) for number in range(1, len(pool.fight_order) + 1)}
        if not set(results).issubset(allowed):
            raise RuleError("Ein Ergebnis verweist auf eine nicht vorgesehene Begegnung.")
        for result in results.values():
            result.validate()

    def pool_print_content(self, pool_id: str) -> tuple:
        """Gedruckte Inhalte ohne Erstellzeit und Standnummer zum Standvergleich.

        Bei zusätzlichen Druckinhalten diesen Vertrag mit output.draw_pool pflegen.
        Einzelgewichte und Regelwarnungen erscheinen nicht auf der Poolliste.
        """
        pool = self.pool(pool_id)
        people = [self.participant(pid) for pid in pool.members]
        weights = [p.weight_grams for p in people]
        return (self.name, self.event_date, self.is_demo, pool.id, pool.name, pool.kind,
                pool.age_class, pool.mat, pool.completed,
                tuple((p.id, p.name, p.club, p.withdrawn, p.disqualified) for p in people),
                (min(weights), max(weights)) if weights else (), pool.results)

    def save_pool(self, pool_id: str, name: str, results: dict[str, FightResult], *, mat: str | None = None) -> None:
        pool = self.pool(pool_id)
        self._validate_pool_results(pool, results)
        if not isinstance(name, str):
            raise RuleError("Der Poolname muss ein Text sein.")
        if mat is not None and not isinstance(mat, str):
            raise RuleError("Die Mattenangabe muss ein Text sein.")
        for number, (a, b) in enumerate(pool.fight_order, 1):
            key = str(number)
            old, new = pool.results.get(key), results.get(key)
            disqualified = any(self.participant(pool.members[pos - 1]).disqualified
                              for pos in (a, b)) if self.participants else False
            if (disqualified or (old and old.automatic) or (new and new.automatic)) and new != old:
                raise RuleError(f"Kampf {number}: Automatische Statuswertung oder Disqualifikation ist für Korrekturen gesperrt.")
        pool.name = name.strip()
        if mat is not None:
            pool.mat = mat.strip()
        pool.results = dict(results)
        if self.participants:
            self._apply_status_results(pool)
        # Das Leeren eines Ergebnisses gibt eine einmal gestartete Besetzung nicht frei.
        pool.started = pool.started or bool(results)
        if pool.completed and not pool.ready_to_complete:
            pool.completed, pool.reopened = False, True
            pool.reopen_reason = ""

    def complete_pool(self, pool_id: str) -> None:
        pool = self.pool(pool_id)
        if not pool.fight_order:
            raise RuleError("Zum Abschließen braucht der Pool mindestens zwei Kinder.")
        if pool.missing_required_fights:
            raise RuleError("Pflichtkämpfe ohne Ergebnis: " + ", ".join(map(str, pool.missing_required_fights)) + ".")
        pool.completed, pool.reopened, pool.started = True, False, True
        pool.reopen_reason = ""

    def add_participants(self, incoming: list[Participant], *, weights: dict[str, int] | None = None):
        from .participant_import import merge_participants

        return merge_participants(self, incoming, weights)

    def replace_participants(self, incoming: list[Participant]) -> None:
        """Gemeinsame Datei vollständig prüfen, danach IDs und Zuordnungen übernehmen."""
        known = {p.id: p for p in self.participants}
        known_signatures = {signature(p) for p in self.participants}
        frozen = {pid for pool in self.pools if pool.started for pid in pool.members}
        seen, signatures, people = set(), set(), []
        for person in incoming:
            if person.id:
                if person.id not in known or person.id in seen:
                    raise RuleError(f"{person.name}: unbekannte oder doppelte Teilnehmer-ID. Gesamtes Neueinlesen abgelehnt.")
                old = known[person.id]
                if person.id in frozen and (old.birth_year, old.gender, old.weight_grams) != (
                        person.birth_year, person.gender, person.weight_grams):
                    raise RuleError(f"{person.name}: Jahrgang, Geschlecht und Gewicht sind nach Poolstart gesperrt.")
            elif signature(person) in known_signatures:
                raise RuleError(f"Doppelte Meldung ohne ID: {person.name}.")
            if signature(person) in signatures:
                raise RuleError(f"Doppelte Meldung: {person.name}.")
            signatures.add(signature(person))
            participant_id = person.id or str(uuid4())
            old = known.get(participant_id)
            seen.add(participant_id)
            people.append(Participant(participant_id, person.first_name, person.last_name, person.club,
                                      person.birth_year, person.gender, person.weight_grams,
                                      old.withdrawn if old else False, old.disqualified if old else False,
                                      old.bookmark if old else None))
        if frozen - seen:
            person = known[sorted(frozen - seen)[0]]
            raise RuleError(f"{person.name}: Löschen nach Start eines regulären oder Freundschaftspools ist gesperrt.")
        self.participants = people
        for pool in self.pools:
            pool.members = [pid for pid in pool.members if pid in seen]
        self.validate()


def signature(p: Participant) -> tuple:
    return (p.first_name, p.last_name, p.club, p.birth_year, p.gender, p.weight_grams)


def parse_weight(value) -> int:
    try:
        number = re.sub(r"\s*(?:kg|kilo)\s*$", "", str(value).strip(), flags=re.IGNORECASE)
        grams = Decimal(number.replace(",", ".")) * 1000
        if not grams.is_finite() or grams <= 0 or grams % 100 != 0:
            raise ValueError
        return int(grams)
    except (InvalidOperation, ValueError):
        raise RuleError("Gewicht muss positiv sein und in 100-Gramm-Schritten vorliegen.") from None
