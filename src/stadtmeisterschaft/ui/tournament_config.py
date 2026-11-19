"""Zentrale Veranstaltungseinstellungen ohne automatische Änderung der Poolbesetzung."""
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from stadtmeisterschaft.domain import AgeClass, RuleError, format_years, parse_years
from stadtmeisterschaft.age_class_defaults import suggested_class, suggested_classes


class TournamentConfig(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.main_window = window
        self.setWindowTitle("Wettkampf konfigurieren")
        self.resize(920, 560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(window.state.name)
        self.name.setObjectName("tournament-name")
        self.event_date = QDateEdit()
        self.event_date.setObjectName("tournament-date")
        self.event_date.setCalendarPopup(True)
        self.event_date.setDisplayFormat("dd.MM.yyyy")
        saved_date = QDate.fromString(window.state.event_date, "yyyy-MM-dd")
        self.event_date.setDate(saved_date if saved_date.isValid() else QDate.currentDate())
        form.addRow("Wettkampf", self.name)
        form.addRow("Veranstaltungsdatum", self.event_date)
        layout.addLayout(form)
        suggest = QPushButton("Altersklassen und Jahrgänge vorschlagen")
        suggest.clicked.connect(self.suggest_classes)
        layout.addWidget(suggest)
        preset_note = QLabel("BJV-Vorlage: U9, U11, U13, U15, U18 für das Veranstaltungsjahr. "
                             "Ergänzt fehlende Klassen und leere Jahrgangsfelder. Alle Werte bleiben bearbeitbar.")
        preset_note.setWordWrap(True)
        layout.addWidget(preset_note)
        note = QLabel("Jahrgänge als Bereich oder Liste eingeben, z. B. 2016-2018 oder 2014, 2016. "
                      "Überschneidungen zwischen Altersklassen sind möglich. Ohne Häkchen werden Mädchen und Jungen getrennt geplant.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.classes = QTableWidget(0, 3)
        self.classes.setObjectName("age-classes")
        self.classes.setHorizontalHeaderLabels(["Altersklasse", "Zulässige Jahrgänge", "Mädchen/Jungen gemeinsam"])
        self.classes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.classes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.classes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.classes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.classes.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.classes, 1)
        for age_class in window.state.age_classes:
            self.add_class(age_class)
        self.classes.itemChanged.connect(self.suggest_row_years)
        self.event_date.dateChanged.connect(self.update_suggested_years)
        actions = QHBoxLayout()
        add = QPushButton("Altersklasse hinzufügen")
        add.clicked.connect(lambda: self.add_class())
        remove = QPushButton("Ausgewählte Altersklasse entfernen")
        remove.clicked.connect(self.remove_class)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch()
        layout.addLayout(actions)
        info = QLabel("Die Einstellungen werden im Arbeitsordner gespeichert. Bestehende Pools bleiben besetzt; "
                      "ihre Abweichungshinweise werden aktualisiert. Datumsänderungen passen nur unveränderte neue Vorschläge an. "
                      "Gespeicherte oder manuell bearbeitete Jahrgänge bleiben erhalten.")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #a12621;")
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_suggested_years(self, row, age_class):
        item = self.classes.item(row, 1)
        text = format_years(age_class.years)
        previous = self.classes.blockSignals(True)
        try:
            item.setText(text)
            item.setData(Qt.ItemDataRole.UserRole, text)
        finally:
            self.classes.blockSignals(previous)

    def suggest_row_years(self, item):
        years = self.classes.item(item.row(), 1)
        if item.column() != 0 or years is None:
            return
        if years.text().strip() and years.text() != years.data(Qt.ItemDataRole.UserRole):
            return
        try:
            proposal = suggested_class(item.text(), self.event_date.date().year())
            if proposal:
                self.set_suggested_years(item.row(), proposal)
        except RuleError as exc:
            self.message.setText(str(exc))

    def suggest_classes(self):
        try:
            proposals = suggested_classes(self.event_date.date().year())
            rows = {self.classes.item(row, 0).text().strip().upper().replace(" ", ""): row
                    for row in range(self.classes.rowCount())}
            for proposal in proposals:
                if proposal.name not in rows:
                    self.add_class(proposal)
                    self.set_suggested_years(self.classes.rowCount() - 1, proposal)
                else:
                    row = rows[proposal.name]
                    if not self.classes.item(row, 1).text().strip():
                        self.set_suggested_years(row, proposal)
            self.message.setText("Vorschläge ergänzt. Jahrgänge und Geschlechtermischung bitte für eure Ausschreibung prüfen.")
        except RuleError as exc:
            self.message.setText(str(exc))

    def update_suggested_years(self):
        # Nur unveränderte Vorschläge dieser geöffneten Maske nachziehen.
        # Gespeicherte Konfiguration und manuell bearbeitete Werte bleiben erhalten.
        for row in range(self.classes.rowCount()):
            item = self.classes.item(row, 1)
            if item.text() == item.data(Qt.ItemDataRole.UserRole):
                try:
                    proposal = suggested_class(self.classes.item(row, 0).text(), self.event_date.date().year())
                    if proposal:
                        self.set_suggested_years(row, proposal)
                except RuleError as exc:
                    self.message.setText(str(exc))

    def add_class(self, age_class: AgeClass | None = None):
        row = self.classes.rowCount()
        self.classes.insertRow(row)
        self.classes.setItem(row, 0, QTableWidgetItem(age_class.name if age_class else ""))
        self.classes.setItem(row, 1, QTableWidgetItem(format_years(age_class.years) if age_class else ""))
        mixed = QCheckBox("Gemeinsam")
        mixed.setChecked(age_class.mixed if age_class else False)
        self.classes.setCellWidget(row, 2, mixed)
        self.classes.setRowHeight(row, 38)
        self.classes.setCurrentCell(row, 0)
        if age_class is None:
            self.classes.editItem(self.classes.item(row, 0))

    def remove_class(self):
        row = self.classes.currentRow()
        if row >= 0:
            self.classes.removeRow(row)

    def save(self):
        try:
            classes = []
            for row in range(self.classes.rowCount()):
                name = self.classes.item(row, 0).text().strip()
                years = self.classes.item(row, 1).text().strip()
                mixed = self.classes.cellWidget(row, 2).isChecked()
                if not name and not years and not mixed:
                    continue
                try:
                    classes.append(AgeClass(name, parse_years(years), mixed))
                except RuleError as exc:
                    raise RuleError(f"Zeile {row + 1}: {exc}") from exc
            if self.main_window.change(
                lambda state: state.configure(self.name.text(), self.event_date.date().toString("yyyy-MM-dd"), classes),
                "Wettkampf und Altersklassen gespeichert; Poolbesetzungen bleiben erhalten.",
            ):
                self.accept()
            else:
                self.message.setText(self.main_window.message.text())
        except RuleError as exc:
            self.message.setText(str(exc))
