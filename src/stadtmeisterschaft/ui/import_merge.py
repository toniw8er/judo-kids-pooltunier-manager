"""Eine gemeinsame Bestätigung für alle Gewichtsabweichungen einer Meldeliste."""
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .planning_details import weight_text


class ImportMerge(QDialog):
    def __init__(self, window, prepared):
        super().__init__(window)
        self.main_window, self.prepared = window, prepared
        self.setWindowTitle("Meldeliste importieren · Gewichte abgleichen")
        self.resize(1000, 480)
        layout = QVBoxLayout(self)
        comparison = prepared.comparison
        description = QLabel(
            f"{len(comparison.new)} neue Kinder · {comparison.unchanged} unveränderte Meldungen\n"
            "Gewicht je Kind auswählen. Standardmäßig bleibt das bestehende Gewicht erhalten. "
            "Gesperrte Gewichte werden übersprungen. Erst „Import übernehmen“ speichert die gesamte Meldeliste.")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.table = QTableWidget(len(comparison.conflicts), 5)
        self.table.setHorizontalHeaderLabels(["Kind", "Bestehendes Gewicht", "Neues Gewicht", "Übernehmen", "Hinweis"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.choices = {}
        for row, conflict in enumerate(comparison.conflicts):
            gender = "W" if conflict.gender == "F" else conflict.gender
            values = [f"{conflict.name}\n{conflict.club} · Jg. {conflict.birth_year} · {gender}",
                      weight_text(conflict.old_weight), weight_text(conflict.new_weight)]
            for column, text in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(text))
            if conflict.locked:
                self.table.setItem(row, 3, QTableWidgetItem("Bestehendes bleibt"))
                self.table.setItem(row, 4, QTableWidgetItem("Nach Poolstart gesperrt\nAbweichung wird übersprungen"))
            else:
                choice = QComboBox()
                choice.addItem("Bestehendes", conflict.old_weight)
                choice.addItem("Neues", conflict.new_weight)
                self.table.setCellWidget(row, 3, choice)
                self.choices[conflict.participant_id] = choice
        self.table.resizeRowsToContents()
        layout.addWidget(self.table, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import übernehmen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def commit(self):
        try:
            self.main_window.apply_import(self.prepared, {pid: choice.currentData() for pid, choice in self.choices.items()})
        except Exception as exc:
            self.message.setText(f"Import nicht übernommen: {exc}")
            return
        self.accept()
