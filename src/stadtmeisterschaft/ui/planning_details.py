"""Kompakte Planungshinweise; ausschließlich für die Oberfläche."""
from fractions import Fraction
from copy import deepcopy
from datetime import date
from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from stadtmeisterschaft.friendship import participant_class


def weight_text(grams: int) -> str:
    return f"{Fraction(grams, 1000):.1f} kg".replace(".", ",")


def weight_comparison(grams: int, reference: int) -> str:
    difference = grams - reference
    if not difference:
        return "gleich schwer (0,0 %)"
    percent = Fraction(100 * abs(difference), min(grams, reference))
    direction, sign = ("schwerer", "+") if difference > 0 else ("leichter", "−")
    return f"{weight_text(abs(difference))} {direction} ({sign}{percent:.1f} %)".replace(".", ",")


def class_text(state, participant_id: str) -> str:
    actual = next((p.age_class for p in state.pools if not p.is_friendship
                   and participant_id in p.members and p.age_class), "")
    if actual:
        return actual if any(c.name == actual for c in state.age_classes) else actual + " (nicht mehr konfiguriert)"
    inferred = participant_class(state, participant_id)
    return inferred.name + " (Jahrgang)" if inferred else "Klasse offen"


def participant_planning_text(state, participant_id: str) -> str:
    person = state.participant(participant_id)
    values = [person.name, class_text(state, participant_id), f"Jg. {person.birth_year}"]
    if state.event_date:
        age = date.fromisoformat(state.event_date).year - person.birth_year
        if age >= 0:
            values.append(f"{age} Jahre im Wettkampfjahr")
    values.append(weight_text(person.weight_grams))
    return " · ".join(values)


def friendship_pools(state, participant_id: str):
    return [p for p in state.sorted_pools() if p.is_friendship and participant_id in p.members]


def describe_age_notes(state, members: list[str], notes: list[str]) -> list[str]:
    def is_age_note(note):
        return any(word in note.casefold() for word in ("jahrgang", "jahrgänge", "altersklasse", "startklasse"))
    if not any(is_age_note(note) for note in notes):
        return notes
    result = [note for note in notes if not is_age_note(note)]
    classes = list(dict.fromkeys(class_text(state, pid) for pid in members))
    result.append(("Unterschiedliche Altersklassen: " if len(classes) > 1 else "Altersklasse prüfen: ")
                  + " / ".join(classes))
    result.extend("Altersangaben: " + participant_planning_text(state, pid) for pid in members)
    return result


def pool_planning_notes(state, pool_id: str) -> list[str]:
    pool = state.pool(pool_id)
    notes = state.pool_warnings(pool_id)
    # Zusätzliche Kämpfe lösen den organisatorischen Hinweis des Einzelpools ab.
    if not pool.is_friendship and len(pool.members) == 1 and any(
            len(p.members) >= 2 for p in friendship_pools(state, pool.members[0])):
        notes = [note for note in notes if not note.startswith("Einzelpool:")]
    for pid in pool.members:
        notes.extend(f"{state.participant(pid).name}: {note}" for note in state.pool_member_warnings(pool_id, pid))
    return describe_age_notes(state, pool.members, notes)


class FriendshipLinks(QWidget):
    activated = Signal(str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.labels = []

    def refresh(self, state, pool_id: str):
        for label in self.labels:
            self.layout.removeWidget(label)
            label.deleteLater()
        self.labels = []
        source = state.pool(pool_id)
        if not source.is_friendship and len(source.members) == 1:
            for pool in friendship_pools(state, source.members[0]):
                status = "Freundschaftskampf organisiert" if len(pool.members) >= 2 else "Freundschaftspool angelegt · noch ohne Partner"
                label = QLabel(status + ' · <a href="' + escape(pool.id, quote=True) + '">' + escape(pool.display_name) + '</a>')
                label.setWordWrap(True)
                label.linkActivated.connect(self.activated.emit)
                self.layout.addWidget(label)
                self.labels.append(label)
        self.setVisible(bool(self.labels))


def warning_summary(notes: list[str], *, compact: bool = False) -> str:
    categories = []
    for note in notes:
        lowered = note.casefold()
        if "bereits in anderem freundschaftspool:" in lowered:
            category = "Weitere Freundschaftsteilnahme"
        elif "gewicht" in lowered or "10 %" in lowered:
            category = "Gewichtsspanne über 10 %"
        elif "geschlecht" in lowered or "mädchen/jungen" in lowered:
            category = "Geschlechtermischung prüfen"
        elif any(word in lowered for word in ("jahrgang", "jahrgänge", "altersklasse", "startklasse", "altersangaben")):
            category = note if note.startswith("Unterschiedliche Altersklassen:") else "Altersklasse prüfen"
        elif "einzelpool" in lowered:
            category = "Noch kein Partner"
        else:
            category = "Weitere Hinweise"
        if category not in categories:
            categories.append(category)
    if any(category.startswith("Unterschiedliche Altersklassen:") for category in categories):
        categories = [category for category in categories if category != "Altersklasse prüfen"]
    if compact:
        short = {"Gewichtsspanne über 10 %": "Gewicht", "Geschlechtermischung prüfen": "Geschlecht",
                 "Altersklasse prüfen": "Altersklasse"}
        return " / ".join(short.get(category, category) for category in categories)
    return " · ".join(categories)


def pair_member_notes(state, pool_id: str, participant_id: str, opponent_id: str) -> list[str]:
    preview = deepcopy(state)
    preview.pool(pool_id).members = [participant_id, opponent_id]
    return preview.pool_member_warnings(pool_id, participant_id)


class PlanningWarnings(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #985000;")
        row.addWidget(self.summary, 1)
        self.toggle = QPushButton("Details anzeigen")
        self.toggle.setCheckable(True)
        self.toggle.toggled.connect(self._toggle)
        row.addWidget(self.toggle)
        layout.addLayout(row)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setStyleSheet("color: #985000;")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.details)
        self.scroll.setMaximumHeight(140)
        self.scroll.hide()
        layout.addWidget(self.scroll)
        self.set_notes([])

    def _toggle(self, expanded):
        self.scroll.setVisible(expanded)
        self.toggle.setText("Details ausblenden" if expanded else "Details anzeigen")

    def set_notes(self, notes: list[str]):
        notes = list(dict.fromkeys(notes))
        self.details.setText("\n".join(notes))
        self.summary.setText(warning_summary(notes) if notes else "")
        self.setVisible(bool(notes))
        if not notes:
            self.toggle.setChecked(False)

    def text(self):
        return self.details.text()
