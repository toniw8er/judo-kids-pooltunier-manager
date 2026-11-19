"""Mehrfachauswahl mit laufender Prüfung der vollständigen Gruppe."""
from fractions import Fraction
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QHBoxLayout, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from stadtmeisterschaft.domain import RuleError
from stadtmeisterschaft.friendship import group_warnings, load_age_factor, participant_class, suggestions
from .bookmarks import ParticipantSummary, bookmark_icon, show_bookmark_menu
from .planning_details import PlanningWarnings, describe_age_notes, weight_comparison, weight_text


class FriendshipSearch(QDialog):
    def __init__(self, window, pool_id: str, parent=None):
        super().__init__(parent or window)
        self.main_window, self.pool_id = window, pool_id
        self.selected = []
        self.target_pool_id = None
        self.setWindowTitle("Freundschaftspartner suchen")
        self.resize(1050, 760)
        layout = QVBoxLayout(self)
        self.context = QLabel()
        self.context.setWordWrap(True)
        header = QHBoxLayout()
        header.addWidget(self.context, 1)
        self.info = QPushButton("i")
        self.info.setFixedSize(28, 28)
        self.info.setStyleSheet("font-weight: 700; border-radius: 14px; padding: 0;")
        self.info.setAccessibleName("Information zur Partnersuche")
        self.info.setToolTip("Wie werden Vorschläge sortiert?")
        self.info.clicked.connect(self.show_info)
        header.addWidget(self.info)
        layout.addLayout(header)
        self.explanation_text = ""
        self.group = ParticipantSummary(window, self.edit_bookmark)
        layout.addWidget(self.group)
        self.remove = QPushButton("Letzte Auswahl zurücknehmen")
        self.remove.clicked.connect(self.remove_last)
        layout.addWidget(self.remove)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Partner", "Startklasse", "Gewicht", "Gewichtsvergleich", "Auswahl"])
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.participant_menu)
        self.table.setIconSize(QSize(14, 18))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        self.warnings = PlanningWarnings()
        layout.addWidget(self.warnings)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.confirm = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm.setText("Partner übernehmen" if window.state.pool(pool_id).is_friendship else "Freundschaftspool erstellen")
        self.buttons.accepted.connect(self.commit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        try:
            self.factor = load_age_factor(window.folder)
        except RuleError as exc:
            self.factor = None
            self.message.setText(str(exc))
        self.refresh()

    def refresh(self):
        state = self.main_window.state
        pool = state.pool(self.pool_id)
        people = pool.members + self.selected
        self.context.setText(pool.display_name + (" · ergänzen" if pool.is_friendship else " · neue zusätzliche Gruppe"))
        origin = participant_class(state, pool.members[0]) if pool.members else None
        self.explanation_text = (
            f"Rangwert = 100 × Gewichtsunterschied / kleineres Gewicht + {self.factor if self.factor is not None else 'Altersfaktor'} × Klassenschritte². "
            "Für die ganze Gruppe zählt das ungünstigste Paar. Kleinere Werte stehen oben; gleiche Werte nach Name. "
            "Ein Klassenschritt entspricht einer konfigurierten Altersklasse von jung nach alt. "
            f"Ausgangsklasse: {origin.name if origin else 'nicht zugeordnet'}; "
            + ("gemischte Vorschläge erlaubt. " if origin and origin.mixed else "Vorschläge desselben Geschlechts. ")
            + "Keine feste Alters-/Gewichtsgrenze. Ein Rangwert ist keine sportliche Freigabe. "
            "Zurückgezogene, disqualifizierte und Kinder ohne zuordenbare Klasse werden nicht vorgeschlagen. "
            "Gewichtsprozente beziehen sich auf das kleinere der beiden Gewichte, passend zur 10-%-Regel. "
            "Bei mehreren Kindern zeigt die Vergleichsspalte den größten relativen Gewichtsunterschied zum Vorschlag. "
            "Alle Einzelvergleiche sind im Tooltip der Zeile verfügbar.")
        members = [state.participant(pid) for pid in people]
        group_lines = [f"{p.name} · {participant_class(state, p.id).name if participant_class(state, p.id) else 'Klasse offen'} · "
                       + weight_text(p.weight_grams)
                       + (" · Hinweis: " + note if (note := state.other_friendship_note(p.id, self.pool_id)) else "")
                       for p in members]
        heading = (f"Gruppe ({len(people)}/5)"
                   + (f" · {weight_text(min(p.weight_grams for p in members))}–{weight_text(max(p.weight_grams for p in members))}" if len(members) > 1 else ""))
        self.group.set_entries([(None, heading)] + [(p.id, line) for p, line in zip(members, group_lines)])
        self.table.setHorizontalHeaderItem(3, QTableWidgetItem(
            "Vergleich zu " + members[0].name if len(members) == 1 else "Gewichtsvergleich"))
        self.remove.setEnabled(bool(self.selected))
        self.table.setRowCount(0)
        self.confirm.setEnabled(False)
        if self.factor is None:
            return
        try:
            ranked = suggestions(state, self.pool_id, self.selected, self.factor)
            self.warnings.set_notes(describe_age_notes(state, people, group_warnings(state, self.pool_id, self.selected)))
        except RuleError as exc:
            self.message.setText(str(exc))
            return
        self.confirm.setEnabled(bool(self.selected))
        self.message.setText("Gruppe vollständig. Bitte übernehmen oder die letzte Auswahl zurücknehmen." if len(people) == 5 else
                             f"{len(ranked)} Vorschläge · Änderungen werden erst mit der Bestätigung gespeichert.")
        if len(people) == 5:
            return
        self.table.setRowCount(len(ranked))
        for row, item in enumerate(ranked):
            person = state.participant(item.participant_id)
            reference = max(members, key=lambda p: Fraction(abs(person.weight_grams - p.weight_grams),
                                                           min(person.weight_grams, p.weight_grams)))
            comparison = weight_comparison(person.weight_grams, reference.weight_grams)
            if len(members) > 1:
                comparison = f"zu {reference.name}: " + comparison
            values = [person.name, item.age_class, weight_text(person.weight_grams), comparison]
            if note := state.other_friendship_note(person.id, self.pool_id):
                values[0] += "\nHinweis: " + note
            comparisons = [f"zu {p.name} ({weight_text(p.weight_grams)}): "
                           + weight_comparison(person.weight_grams, p.weight_grams) for p in members]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip("\n".join((["Lesezeichen: " + person.bookmark] if person.bookmark is not None else [])
                                         + comparisons + list(item.notes)))
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, person.id)
                    cell.setIcon(bookmark_icon(person.bookmark is not None))
                self.table.setItem(row, column, cell)
            button = QPushButton("Hinzufügen")
            button.clicked.connect(lambda checked=False, pid=item.participant_id: self.add_partner(pid))
            self.table.setCellWidget(row, 4, button)
        self.table.resizeRowsToContents()

    def participant_menu(self, point):
        row = self.table.rowAt(point.y())
        if row >= 0:
            pid = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            show_bookmark_menu(self.table, self.table.viewport().mapToGlobal(point), self.main_window,
                               "participant", pid, lambda: self.edit_bookmark(pid))

    def edit_bookmark(self, pid):
        self.main_window.edit_bookmark("participant", pid, self)
        self.refresh()

    def show_info(self):
        QMessageBox.information(self, "Wie werden Vorschläge sortiert?", self.explanation_text)

    def add_partner(self, pid):
        if len(self.main_window.state.pool(self.pool_id).members) + len(self.selected) >= 5:
            return
        try:
            valid = {s.participant_id for s in suggestions(self.main_window.state, self.pool_id, self.selected, self.factor)}
            if pid not in valid:
                raise RuleError("Dieser Partner ist nicht mehr verfügbar.")
        except RuleError as exc:
            self.message.setText(str(exc))
            return
        self.selected.append(pid)
        self.refresh()

    def remove_last(self):
        if self.selected:
            self.selected.pop()
        self.refresh()

    def commit(self):
        try:
            if self.factor is None:
                return
            # Jeden Schritt erneut gegen den aktuellen Stand prüfen.
            checked = []
            for pid in self.selected:
                available = suggestions(self.main_window.state, self.pool_id, checked, self.factor)
                if pid not in {item.participant_id for item in available}:
                    raise RuleError("Die Auswahl ist nicht mehr verfügbar. Bitte erneut wählen.")
                checked.append(pid)
            target = []
            if self.main_window.change(lambda state: target.append(state.add_friendship_partners(self.pool_id, checked)),
                                       "Freundschaftspartner übernommen."):
                self.target_pool_id = target[0]
                self.accept()
            else:
                self.message.setText(self.main_window.message.text())
        except RuleError as exc:
            self.message.setText(str(exc))
