"""Eine Poolseite für Namen, Begegnungen und gespeicherte Ergebniseingaben."""
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
    QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem,
)
from PySide6.QtGui import QColor

from stadtmeisterschaft.domain import FightResult, RESULT_REASONS, RuleError
from .bookmarks import ParticipantSummary, install_bookmark_menu, show_bookmark_menu, update_button
from .planning_details import (FriendshipLinks, PlanningWarnings, pair_member_notes, participant_planning_text,
                               friendship_pools, pool_planning_notes, weight_comparison, weight_text)


class PoolPage(QDialog):
    def __init__(self, window, pool_id: str):
        super().__init__(window)
        self.main_window = window
        self.pool_id = pool_id
        self.next_pool_id = None
        install_bookmark_menu(self, window, "pool", pool_id, lambda: self.edit_bookmark("pool", pool_id))
        pool = window.state.pool(pool_id)
        self.setWindowTitle(pool.display_name)
        self.resize(1100, 850)
        self.setStyleSheet("QLabel { font-size: 13px; } QComboBox { min-width: 0px; } "
                          "QComboBox:disabled { color: #555555; background: #e4e4e4; }")
        layout = QVBoxLayout(self)
        self.heading = QLabel(("Freundschaftskampf · " if pool.is_friendship else "") + pool.display_name)
        self.heading.setWordWrap(True)
        self.heading.setStyleSheet("font-size: 22px; font-weight: 700;")
        heading_row = QHBoxLayout()
        heading_row.addWidget(self.heading, 1)
        self.bookmark_button = QPushButton()
        self.bookmark_button.clicked.connect(lambda: self.edit_bookmark("pool", self.pool_id))
        heading_row.addWidget(self.bookmark_button)
        layout.addLayout(heading_row)
        context = QLabel(window.event_label.text())
        context.setWordWrap(True)
        layout.addWidget(context)
        class_note = QLabel(window.state.pool_class_note(pool_id))
        class_note.setWordWrap(True)
        class_note.setVisible(bool(class_note.text()))
        layout.addWidget(class_note)
        self.members_context = ParticipantSummary(window, lambda pid: self.edit_bookmark("participant", pid))
        layout.addWidget(self.members_context)
        self.friendship_links = FriendshipLinks()
        self.friendship_links.activated.connect(self.open_related_pool)
        layout.addWidget(self.friendship_links)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Optionaler Poolname:"))
        self.pool_name = QLineEdit(pool.name)
        self.pool_name.setPlaceholderText("z. B. U11 – Gruppe A; leer lassen für die Poolnummer")
        name_row.addWidget(self.pool_name, 1)
        layout.addLayout(name_row)
        mat_row = QHBoxLayout()
        mat_row.addWidget(QLabel("Matte (optional):"))
        self.pool_mat = QLineEdit(pool.mat)
        self.pool_mat.setPlaceholderText("z. B. 1 oder Halle A; jederzeit änderbar")
        mat_row.addWidget(self.pool_mat, 1)
        layout.addLayout(mat_row)
        self.friendship_button = QPushButton("Freundschaftspartner suchen")
        self.friendship_button.setVisible(pool.is_friendship or len(pool.members) == 1)
        self.friendship_button.clicked.connect(self.search_friendship)
        layout.addWidget(self.friendship_button)
        status_row = QHBoxLayout()
        self.participant_choice = QComboBox()
        for pid in pool.members:
            person = window.state.participant(pid)
            self.participant_choice.addItem(person.name, pid)
        status_row.addWidget(self.participant_choice, 1)
        self.participant_choice.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.participant_choice.customContextMenuRequested.connect(self.participant_menu)
        for label, status in [("Rückzug festlegen", "withdrawn"), ("Disqualifizieren", "disqualified")]:
            button = QPushButton(label)
            button.setEnabled(bool(pool.members))
            button.clicked.connect(lambda checked=False, current=status: self.set_status(current))
            status_row.addWidget(button)
        layout.addLayout(status_row)
        self.pool_note = QLabel()
        self.pool_note.setWordWrap(True)
        layout.addWidget(self.pool_note)
        self.warnings = PlanningWarnings()
        layout.addWidget(self.warnings)
        legend = QLabel("Ausgang 1:0 = Erstgenannte/r gewinnt · 0:1 = Zweitgenannte/r gewinnt · 0:0 = Unentschieden")
        legend.setWordWrap(True)
        layout.addWidget(legend)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for column, label in enumerate(["Nr.", "Erstgenannte/r", "", "Zweitgenannte/r",
                                        "Ausgang 1. : 2.", "UB 1.", "", "UB 2.", "Ergebnisgrund"]):
            heading = QLabel(label)
            heading.setStyleSheet("font-weight: 700;")
            grid.addWidget(heading, 0, column)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.editors = []
        self.reason_editors = []
        self.name_labels = []
        for number, (first, second) in enumerate(pool.fight_order, 1):
            grid.addWidget(QLabel(str(number)), number, 0)
            for column, position, opponent in [(1, first, second), (3, second, first)]:
                pid = pool.members[position - 1]
                name = QLabel()
                name.setTextFormat(Qt.TextFormat.PlainText)
                name.setWordWrap(True)
                install_bookmark_menu(name, window, "participant", pid,
                                      lambda current=pid: self.edit_bookmark("participant", current))
                grid.addWidget(name, number, column)
                self.name_labels.append((name, pid, pool.members[opponent - 1]))
            grid.addWidget(QLabel("–"), number, 2)
            outcome = self._choice(["1:0", "0:1", "0:0"])
            outcome.setObjectName(f"outcome-{number}")
            outcome.setFixedWidth(130)
            outcome.setStyleSheet("QComboBox { min-width: 100px; }")
            first_ub = self._choice([0, 5, 7, 10])
            second_ub = self._choice([0, 5, 7, 10])
            for combo in (first_ub, second_ub):
                combo.setFixedWidth(90)
                combo.setStyleSheet("QComboBox { min-width: 60px; }")
            first_ub.setObjectName(f"first-ub-{number}")
            second_ub.setObjectName(f"second-ub-{number}")
            grid.addWidget(outcome, number, 4)
            grid.addWidget(first_ub, number, 5)
            grid.addWidget(QLabel(":"), number, 6)
            grid.addWidget(second_ub, number, 7)
            grid.setRowMinimumHeight(number, 40)
            result = pool.results.get(str(number))
            if result:
                for combo, value in [(outcome, result.outcome), (first_ub, result.first), (second_ub, result.second)]:
                    combo.setCurrentIndex(combo.findData(value))
            self.editors.append((outcome, first_ub, second_ub))
            reason = QComboBox()
            for key, label in RESULT_REASONS.items():
                reason.addItem(label, key)
            grid.addWidget(reason, number, 8)
            self.reason_editors.append(reason)
        if not self.editors:
            note = QLabel("Für diesen Pool ist noch keine Begegnung vorgesehen. Kinder über die Übersicht zuordnen.")
            note.setWordWrap(True)
            grid.addWidget(note, 1, 0, 1, 8)
        grid.setRowStretch(len(self.editors) + 2, 1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.evaluation_label = QLabel()
        self.evaluation_label.setWordWrap(True)
        layout.addWidget(self.evaluation_label)
        self.standings = QTableWidget(len(pool.members), 7)
        self.standings.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.standings.customContextMenuRequested.connect(self.standings_menu)
        self.standings.setStyleSheet("QTableWidget { font-size: 13px; } QHeaderView::section { font-size: 12px; }")
        self.standings.setHorizontalHeaderLabels(["Name", "Pkt.", "Siege", "UB +", "UB −", "Diff.", "Platz"])
        self.standings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.standings.verticalHeader().hide()
        self.standings.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.standings.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.standings.setFixedHeight(30 + 28 * len(pool.members))
        layout.addWidget(self.standings)

        explanation = QLabel("Vollständige Begegnungen über „Ergebnisse speichern“ übernehmen. "
                             "Leere Felder bedeuten noch kein Ergebnis. Auswertung und Ausgabe verwenden den gespeicherten Stand.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.delete_button = QPushButton("Pool löschen")
        self.delete_button.clicked.connect(self.delete_pool)
        self.delete_button.setEnabled(not pool.started)
        self.delete_button.setToolTip("Gestartete Pools bleiben geschützt. Teilnehmerdaten werden nicht gelöscht.")
        actions.addWidget(self.delete_button)
        self.complete_button = QPushButton("Pool abschließen")
        self.complete_button.clicked.connect(lambda: self.save(complete=True))
        actions.addWidget(self.complete_button)
        for label, callback in [("PDF exportieren", self.export_pdf), ("Druckvorschau", self.preview)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Ergebnisse speichern")
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Zur Übersicht")
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        layout.addLayout(actions)
        self._load_results()
        self._saved_signature = self._signature()
        self._refresh_note()

    def edit_bookmark(self, kind, entity_id):
        self.main_window.edit_bookmark(kind, entity_id, self)
        self._refresh_note()

    def participant_menu(self, point):
        pid = self.participant_choice.currentData()
        if pid:
            show_bookmark_menu(self.participant_choice, self.participant_choice.mapToGlobal(point),
                               self.main_window, "participant", pid,
                               lambda: self.edit_bookmark("participant", pid))

    def standings_menu(self, point):
        row = self.standings.rowAt(point.y())
        if row >= 0:
            pid = self.main_window.state.pool(self.pool_id).members[row]
            show_bookmark_menu(self.standings, self.standings.viewport().mapToGlobal(point),
                               self.main_window, "participant", pid,
                               lambda: self.edit_bookmark("participant", pid))

    @staticmethod
    def _choice(values):
        combo = QComboBox()
        combo.addItem("—", None)
        for value in values:
            combo.addItem(str(value), value)
        return combo

    def _signature(self):
        return (self.pool_name.text(), self.pool_mat.text(), tuple(tuple(combo.currentData() for combo in row) for row in self.editors),
                tuple(combo.currentData() for combo in self.reason_editors))

    def _load_results(self):
        state = self.main_window.state
        pool = state.pool(self.pool_id)
        for number, ((a, b), editors, reason) in enumerate(zip(pool.fight_order, self.editors, self.reason_editors), 1):
            result = pool.results.get(str(number))
            locked = bool(result and result.automatic) or any(
                state.participant(pool.members[pos - 1]).disqualified for pos in (a, b))
            for combo, value in zip(editors, (result.outcome, result.first, result.second) if result else (None,) * 3):
                combo.setCurrentIndex(combo.findData(value))
                combo.setEnabled(not locked)
            reason.setCurrentIndex(reason.findData(result.reason if result else "played"))
            reason.setEnabled(not locked)
            for index in range(reason.count()):
                reason.model().item(index).setEnabled(reason.itemData(index) in {"played", "injury", "nonattendance"})

    def _refresh_participant_labels(self):
        state = self.main_window.state
        pool = state.pool(self.pool_id)
        for label, pid, opponent in self.name_labels:
            person = state.participant(pid)
            notes = pair_member_notes(state, pool.id, pid, opponent)
            text = (person.name + " · " + weight_text(person.weight_grams)
                    + (" · " + person.status_label if person.withdrawn or person.disqualified else "")
                    + (" · Hinweis" if notes else ""))
            label.setText(text)
            other = state.participant(opponent)
            label.setToolTip(f"zu {other.name}: " + weight_comparison(person.weight_grams, other.weight_grams)
                             + ("\n" + "\n".join(notes) if notes else ""))
            if person.bookmark is not None:
                label.setToolTip("Lesezeichen: " + person.bookmark + "\n" + label.toolTip())
            label.setStyleSheet("color: #985000;" if notes else "")
            if person.disqualified:
                label.setStyleSheet("color: #666666; background: #e4e4e4; padding: 4px;")

    def _refresh_note(self):
        state = self.main_window.state
        pool = state.pool(self.pool_id)
        self._refresh_participant_labels()
        update_button(self.bookmark_button, pool.bookmark)
        self.members_context.set_entries([(pid, participant_planning_text(state, pid)) for pid in pool.members])
        self.friendship_links.refresh(state, self.pool_id)
        self.warnings.set_notes(pool_planning_notes(state, self.pool_id))
        self.friendship_button.setEnabled(self.main_window.state.friendship_search_available(self.pool_id))
        self.friendship_button.setToolTip("Für ungestartete Einzelpools und Freundschaftspools mit 1–4 Kindern.")
        self.delete_button.setEnabled(not pool.started)
        text = "Besetzung gesperrt: Der Pool wurde gestartet." if pool.started else "Das erste gespeicherte Ergebnis sperrt die Poolbesetzung."
        if len(pool.members) == 2:
            text += " Kampf 3 ist optional (zwei Siege derselben Person)." if pool.third_fight_optional else " Kampf 3 ist nur bei zwei Siegen derselben Person optional."
        self.pool_note.setText(text + f" · Papierstand {pool.print_revision}")
        self.complete_button.setEnabled(bool(pool.fight_order) and not pool.completed)
        evaluation_note = pool.evaluation_note
        if (not pool.is_friendship and len(pool.members) == 1
                and any(len(friend.members) >= 2 for friend in friendship_pools(state, pool.members[0]))):
            evaluation_note = "Regulärer Einzelpool · keine Platzierung"
        self.evaluation_label.setText("Auswertung · " + evaluation_note)
        rows, _ = self.main_window.state.evaluate_pool(self.pool_id)
        for index, row in enumerate(rows):
            person = self.main_window.state.participant(row.participant_id)
            values = [person.name + " · " + weight_text(person.weight_grams)
                      + (" · " + person.status_label if person.withdrawn or person.disqualified else ""),
                      row.points, row.wins, row.ub_for, row.ub_against, row.difference,
                      row.place if row.place is not None else "—"]
            for column, value in enumerate(values):
                self.standings.setItem(index, column, QTableWidgetItem(str(value)))
                if person.bookmark is not None:
                    self.standings.item(index, column).setToolTip("Lesezeichen: " + person.bookmark)
                if person.disqualified:
                    self.standings.item(index, column).setForeground(QColor("#666666"))
                    self.standings.item(index, column).setBackground(QColor("#e4e4e4"))
            self.standings.setRowHeight(index, 28)

    def save(self, complete=False, *, status=None) -> bool:
        try:
            results = {}
            for number, row in enumerate(self.editors, 1):
                values = tuple(combo.currentData() for combo in row)
                if all(value is None for value in values):
                    if self.reason_editors[number - 1].currentData() != "played":
                        raise RuleError(f"Kampf {number}: Bitte zum Ergebnisgrund auch das vollständige Ergebnis erfassen.")
                    continue
                if any(value is None for value in values):
                    raise RuleError(f"Kampf {number}: Bitte Ausgang und beide Unterbewertungen auswählen oder alle drei Felder leeren.")
                results[str(number)] = FightResult(*values, self.reason_editors[number - 1].currentData())
            def apply(state):
                state.save_pool(self.pool_id, self.pool_name.text(), results, mat=self.pool_mat.text())
                if status:
                    state.set_participant_status(*status)
                if complete:
                    state.complete_pool(self.pool_id)

            saved = self.main_window.change(apply, "Pool abgeschlossen." if complete else "Poolname, Matte und Ergebnisse gespeichert.")
            self.message.setText(self.main_window.message.text())
            if not saved:
                return False
            pool = self.main_window.state.pool(self.pool_id)
            self.pool_name.setText(pool.name)
            self.pool_mat.setText(pool.mat)
            self.setWindowTitle(pool.display_name)
            self.heading.setText(("Freundschaftskampf · " if pool.is_friendship else "") + pool.display_name)
            self._load_results()
            self._saved_signature = self._signature()
            self._refresh_note()
            return True
        except RuleError as exc:
            self.message.setText(f"Nicht gespeichert: {exc}")
            return False

    def search_friendship(self):
        if self._signature() != self._saved_signature:
            self.message.setText("Bitte Änderungen zuerst speichern oder verwerfen, dann Freundschaftspartner suchen.")
            return
        from .friendship_search import FriendshipSearch

        dialog = FriendshipSearch(self.main_window, self.pool_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.next_pool_id = dialog.target_pool_id
            self.accept()

    def open_related_pool(self, pool_id):
        if self._signature() != self._saved_signature:
            self.message.setText("Bitte Änderungen zuerst speichern oder verwerfen, dann den Freundschaftspool öffnen.")
            return
        self.next_pool_id = pool_id
        self.accept()

    def set_status(self, status):
        pid = self.participant_choice.currentData()
        if pid is None or not self.main_window.confirm_participant_status(pid, status):
            return False
        return self.save(status=(pid, status))

    def _can_export(self):
        if self._signature() != self._saved_signature:
            self.message.setText("Bitte die Änderungen zuerst speichern. Die Ausgabe verwendet den gespeicherten Stand.")
            return False
        return True

    def export_pdf(self):
        if self._can_export():
            self.main_window.export_pdf(pool_id=self.pool_id)
            self.message.setText(self.main_window.message.text())

    def preview(self):
        if self._can_export():
            self.main_window.preview(pool_id=self.pool_id)

    def delete_pool(self):
        if self.main_window.delete_pool(self.pool_id):
            self.accept()
        else:
            self.message.setText(self.main_window.message.text())

    def reject(self):
        if self._signature() != self._saved_signature:
            question = QMessageBox(self)
            question.setWindowTitle("Ungespeicherte Änderungen")
            question.setText("Die Änderungen an diesem Pool sind noch nicht gespeichert.")
            question.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            question.setDefaultButton(QMessageBox.StandardButton.Cancel)
            question.button(QMessageBox.StandardButton.Save).setText("Speichern")
            question.button(QMessageBox.StandardButton.Discard).setText("Verwerfen")
            question.button(QMessageBox.StandardButton.Cancel).setText("Weiter bearbeiten")
            answer = question.exec()
            if answer not in {QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Discard}:
                return
            if answer == QMessageBox.StandardButton.Save and not self.save():
                return
        super().reject()
