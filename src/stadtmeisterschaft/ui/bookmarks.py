"""Interne Lesezeichen: None ist unmarkiert, auch eine leere Notiz ist markiert."""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QMenu, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


def bookmark_icon(marked):
    if not marked:
        return QIcon()
    pixmap = QPixmap(24, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#7135ab"))
    painter.setBrush(QColor("#7135ab"))
    painter.drawPolygon(QPolygon([QPoint(4, 2), QPoint(20, 2), QPoint(20, 25),
                                  QPoint(12, 19), QPoint(4, 25)]))
    painter.end()
    return QIcon(pixmap)


def update_button(button, note):
    button.setIcon(bookmark_icon(note is not None))
    button.setText("Lesezeichen bearbeiten" if note is not None else "Lesezeichen setzen")
    button.setToolTip(note if note else "Interne Notiz · erscheint nicht auf Ausdrucken")
    button.setStyleSheet("QPushButton { color: #562483; }" if note is not None else "")


def show_bookmark_menu(widget, position, window, kind, entity_id, edit=None):
    entity = window.state.participant(entity_id) if kind == "participant" else window.state.pool(entity_id)
    menu = QMenu(widget)
    action = menu.addAction("Lesezeichen bearbeiten" if entity.bookmark is not None else "Lesezeichen setzen")
    callback = edit or (lambda: window.edit_bookmark(kind, entity_id, widget.window()))
    action.triggered.connect(lambda checked=False: callback())
    menu.exec(position)
    menu.deleteLater()


def install_bookmark_menu(widget, window, kind, entity_id, edit=None):
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    widget.customContextMenuRequested.connect(lambda point: show_bookmark_menu(
        widget, widget.mapToGlobal(point), window, kind, entity_id, edit))


class ParticipantSummary(QWidget):
    """Teilnehmerzeilen mit Rechtsklick, ohne zusätzliche sichtbare Bedienelemente."""
    def __init__(self, window, edit, parent=None):
        super().__init__(parent)
        self.main_window, self.edit = window, edit
        self.rows = QVBoxLayout(self)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        self.labels = []

    def set_entries(self, entries):
        while self.rows.count():
            old = self.rows.takeAt(0).widget()
            old.hide()
            old.deleteLater()
        self.labels = []
        for pid, text in entries:
            label = QLabel(text)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            if pid:
                install_bookmark_menu(label, self.main_window, "participant", pid,
                                      lambda current=pid: self.edit(current))
                note = self.main_window.state.participant(pid).bookmark
                if note is not None:
                    label.setToolTip("Lesezeichen: " + (note or "(ohne Notiz)"))
            self.rows.addWidget(label)
            self.labels.append(label)

    def text(self):
        return "\n".join(label.text() for label in self.labels)


class BookmarkDialog(QDialog):
    def __init__(self, window, kind, entity_id, parent=None):
        super().__init__(parent or window)
        self.main_window, self.kind, self.entity_id = window, kind, entity_id
        entity = self.entity(window.state)
        self.setWindowTitle("Lesezeichen · " + (entity.name if kind == "participant" else entity.display_name))
        self.resize(480, 300)
        layout = QVBoxLayout(self)
        label = QLabel("Interne Notiz · wird mit dem Turnier gespeichert.\nKeine Ausgabe auf Poollisten oder in Teilnehmerdateien.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.note = QPlainTextEdit()
        self.note.setPlainText(entity.bookmark or "")
        self.note.setPlaceholderText("z. B. Startgebühr fehlt noch …")
        layout.addWidget(self.note)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lesezeichen speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        remove = QPushButton("Lesezeichen entfernen")
        remove.setEnabled(entity.bookmark is not None)
        remove.clicked.connect(lambda: self.save(remove=True))
        buttons.addButton(remove, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(buttons)

    def entity(self, state):
        return state.participant(self.entity_id) if self.kind == "participant" else state.pool(self.entity_id)

    def save(self, *, remove=False):
        note = None if remove else self.note.toPlainText()
        if self.main_window.change(lambda state: setattr(self.entity(state), "bookmark", note),
                                   "Lesezeichen entfernt." if remove else "Lesezeichen gespeichert."):
            self.accept()
        else:
            self.message.setText(self.main_window.message.text())
