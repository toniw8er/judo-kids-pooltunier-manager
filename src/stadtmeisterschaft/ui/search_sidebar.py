"""Gemeinsame Navigation und direkt bearbeitbare interne Orga-Notizen."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTabBar, QVBoxLayout, QWidget,
)

from stadtmeisterschaft.domain import RuleError
from stadtmeisterschaft.participant_search import name_words, search_participants
from stadtmeisterschaft.ui.planning_details import class_text


def entity_for(state, key):
    kind, entity_id = key
    return state.participant(entity_id) if kind == "participant" else state.pool(entity_id)


def contains_words(query, text):
    words = name_words(query)
    haystack = " ".join(name_words(text))
    return bool(words) and all(word in haystack for word in words)


class NoteLabel(QLabel):
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parentWidget().begin_edit()
        super().mouseReleaseEvent(event)


class EntryCard(QFrame):
    def __init__(self, sidebar, key, entity):
        super().__init__()
        self.sidebar, self.key = sidebar, key
        self.setObjectName("organizerCard")
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        kind, entity_id = key
        heading = QLabel(("KIND · " + entity.name) if kind == "participant" else "POOL · " + entity.display_name)
        heading.setObjectName("organizerHeading")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        if kind == "participant":
            pools = sorted((p for p in sidebar.main_window.state.sorted_pools() if entity_id in p.members),
                           key=lambda p: p.is_friendship)
            regular = next((p.id for p in pools if not p.is_friendship), "")
            context = f"{class_text(sidebar.main_window.state, entity_id)} · {entity.club} · Jg. {entity.birth_year}"
            context += "\n" + (" · ".join(p.display_name for p in pools) or "Noch ohne Pool")
            self.jump = QPushButton("Zum Kind ↗")
            self.jump.clicked.connect(lambda: sidebar.main_window.show_participant(entity_id, regular))
        else:
            pools = []
            context = "Freundschaftspool" if entity.is_friendship else "Regulärer Pool"
            context += f" · {len(entity.members)} Kinder"
            self.jump = QPushButton("Zum Pool ↗")
            self.jump.clicked.connect(lambda: sidebar.main_window.show_pool(entity_id))
        subtitle = QLabel(context)
        subtitle.setObjectName("organizerContext")
        subtitle.setTextFormat(Qt.TextFormat.PlainText)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        self.note = NoteLabel(entity.bookmark or ("Notiz ergänzen …" if entity.bookmark is not None else "Noch kein Lesezeichen"))
        self.note.setTextFormat(Qt.TextFormat.PlainText)
        self.note.setObjectName("organizerNote")
        self.note.setWordWrap(True)
        self.note.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.note)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName("Notiz zu " + (entity.name if kind == "participant" else entity.display_name))
        self.editor.setPlaceholderText("Interne Orga-Notiz …")
        self.editor.setMinimumHeight(90)
        self.editor.setMaximumHeight(160)
        self.editor.hide()
        layout.addWidget(self.editor)
        actions = QHBoxLayout()
        self.edit = QPushButton("Bearbeiten" if entity.bookmark is not None else "Lesezeichen setzen")
        self.edit.clicked.connect(self.begin_edit)
        self.done = QPushButton("Erledigt")
        self.done.setVisible(entity.bookmark is not None)
        self.done.clicked.connect(lambda: sidebar.complete(key))
        self.save = QPushButton("Speichern")
        self.save.clicked.connect(lambda: sidebar.save_note(key))
        self.cancel = QPushButton("Abbrechen")
        self.cancel.clicked.connect(lambda: sidebar.cancel_edit(key))
        self.save.hide()
        self.cancel.hide()
        for button in (self.edit, self.done, self.save, self.cancel):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(self.jump, alignment=Qt.AlignmentFlag.AlignLeft)
        self.pool_links = {}
        for pool in pools:
            button = QPushButton(("Freundschaft · " if pool.is_friendship else "") + pool.id + " ↗")
            button.clicked.connect(lambda checked=False, pool_id=pool.id: sidebar.main_window.show_participant(entity_id, pool_id))
            self.pool_links[pool.id] = button
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        if key in sidebar.drafts:
            self.show_editor(sidebar.drafts[key][1])
        self.editor.textChanged.connect(self.remember_draft)

    def begin_edit(self):
        if self.key not in self.sidebar.drafts:
            value = entity_for(self.sidebar.main_window.state, self.key).bookmark
            self.sidebar.drafts[self.key] = (value, value or "")
        self.show_editor(self.sidebar.drafts[self.key][1])
        self.editor.setFocus()

    def show_editor(self, text):
        self.editor.setPlainText(text)
        self.note.hide()
        self.edit.hide()
        self.done.hide()
        self.editor.show()
        self.save.show()
        self.cancel.show()

    def remember_draft(self):
        if self.key in self.sidebar.drafts:
            original, _ = self.sidebar.drafts[self.key]
            self.sidebar.drafts[self.key] = (original, self.editor.toPlainText())


class SearchSidebar(QWidget):
    def __init__(self, window):
        super().__init__()
        self.main_window = window
        self.folder = None
        self.drafts = {}
        self.cards = {}
        self.undo_entry = None
        self.saving = False
        self.setMinimumWidth(340)
        self.setObjectName("organizerSidebar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        title_row = QHBoxLayout()
        title = QLabel("Suche & Orga-Notizen")
        title.setObjectName("organizerHeading")
        title_row.addWidget(title, 1)
        self.close_button = QPushButton("×")
        self.close_button.setAccessibleName("Seitenleiste schließen")
        self.close_button.clicked.connect(self.hide)
        title_row.addWidget(self.close_button)
        layout.addLayout(title_row)
        self.query = QLineEdit()
        self.query.setAccessibleName("Kinder, Pools und Orga-Notizen suchen")
        self.query.setPlaceholderText("Name, Pool oder Notiz suchen …")
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(self.render)
        self.query.returnPressed.connect(self.jump_first)
        layout.addWidget(self.query)
        self.tabs = QTabBar()
        self.tabs.setExpanding(True)
        self.tabs.addTab("Suchen")
        self.tabs.addTab("Orga-Notizen · 0")
        self.tabs.currentChanged.connect(self.render)
        layout.addWidget(self.tabs)
        self.types = QTabBar()
        for label in ("Alle", "Kinder", "Pools"):
            self.types.addTab(label)
        self.types.setExpanding(True)
        self.types.currentChanged.connect(self.render)
        layout.addWidget(self.types)
        self.add = QPushButton("+ Lesezeichen")
        self.add.clicked.connect(self.add_bookmark)
        layout.addWidget(self.add, alignment=Qt.AlignmentFlag.AlignLeft)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message)
        self.undo_bar = QWidget()
        undo_row = QHBoxLayout(self.undo_bar)
        undo_row.setContentsMargins(0, 0, 0, 0)
        undo_row.addWidget(QLabel("Lesezeichen erledigt."), 1)
        self.undo_button = QPushButton("Rückgängig")
        self.undo_button.clicked.connect(self.undo)
        undo_row.addWidget(self.undo_button)
        layout.addWidget(self.undo_bar)
        self.undo_bar.hide()
        self.undo_timer = QTimer(self)
        self.undo_timer.setSingleShot(True)
        self.undo_timer.setInterval(8000)
        self.undo_timer.timeout.connect(self.clear_undo)

    def showEvent(self, event):
        self.main_window.sidebar_button.setChecked(True)
        super().showEvent(event)

    def hideEvent(self, event):
        self.main_window.sidebar_button.setChecked(False)
        super().hideEvent(event)

    def open(self, notes=None):
        self.show()
        if notes is not None:
            self.tabs.setCurrentIndex(1 if notes else 0)
        self.refresh()
        self.query.setFocus()

    def add_bookmark(self):
        self.types.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)
        self.query.clear()
        self.query.setFocus()
        self.message.setText("Kind oder Pool suchen und „Lesezeichen setzen“ wählen.")

    def refresh(self):
        window = self.main_window
        if self.folder != window.folder:
            self.folder = window.folder
            self.drafts.clear()
            self.clear_undo()
            self.query.clear()
            self.message.clear()
        count = sum(entity.bookmark is not None for entity in window.state.participants + window.state.pools)
        self.tabs.setTabText(1, f"Orga-Notizen · {count}")
        window.sidebar_button.setText(f"Suche && Orga-Notizen · {count}")
        children = sum(person.bookmark is not None for person in window.state.participants)
        for index, text in enumerate((f"Alle ({count})", f"Kinder ({children})", f"Pools ({count - children})")):
            self.types.setTabText(index, text)
        if not self.saving:
            self.render()

    def results(self):
        state = self.main_window.state
        query = self.query.text().strip()
        notes = self.tabs.currentIndex() == 1
        if not notes and not query:
            return []
        people = search_participants(state.participants, query)
        rank = {p.id: i for i, p in enumerate(people)}
        entries = [(('participant', p.id), p) for p in state.participants]
        entries += [(('pool', p.id), p) for p in state.sorted_pools()]
        result = []
        for key, entity in entries:
            kind, entity_id = key
            if notes and self.types.currentIndex() == 1 and kind != 'participant':
                continue
            if notes and self.types.currentIndex() == 2 and kind != 'pool':
                continue
            if notes and entity.bookmark is None:
                continue
            if kind == 'participant':
                pools = [p for p in state.pools if entity_id in p.members]
                text = f"{entity.name} {entity.club} {entity.birth_year} " + " ".join(p.display_name for p in pools)
            else:
                text = entity.display_name
            if notes:
                text += " " + (entity.bookmark or "")
            if not query or contains_words(query, text) or (kind == 'participant' and entity_id in rank):
                result.append((key, entity))
        # Namenssuche behält die etablierte Rangfolge: genaue Namen vor Tippfehlern.
        if not notes:
            result.sort(key=lambda entry: rank.get(entry[0][1], len(rank) + 1)
                        if entry[0][0] == 'participant' else len(rank))
        return result

    def render(self):
        if not hasattr(self, "scroll") or not hasattr(self.main_window, "state"):
            return
        position = self.scroll.verticalScrollBar().value()
        content = QWidget()
        rows = QVBoxLayout(content)
        rows.setContentsMargins(0, 0, 4, 0)
        rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards = {}
        for key, entity in self.results():
            card = EntryCard(self, key, entity)
            self.cards[key] = card
            rows.addWidget(card)
        if not self.cards:
            if not self.query.text().strip() and self.tabs.currentIndex() == 0:
                text = "Kind oder Pool suchen. Auch ähnliche Schreibweisen werden gefunden."
            elif self.tabs.currentIndex() == 1 and not self.query.text().strip():
                text = "Keine offenen Orga-Notizen."
            else:
                text = "Keine passenden Treffer."
            label = QLabel(text)
            label.setWordWrap(True)
            rows.addWidget(label)
            if self.query.text():
                clear = QPushButton("Suche zurücksetzen")
                clear.clicked.connect(self.query.clear)
                rows.addWidget(clear)
        self.types.setVisible(self.tabs.currentIndex() == 1)
        self.add.setVisible(self.tabs.currentIndex() == 1)
        old = self.scroll.takeWidget()
        if old:
            old.hide()
            old.deleteLater()
        self.scroll.setWidget(content)
        content.layout().activate()
        self.scroll.verticalScrollBar().setValue(position)

    def jump_first(self):
        if self.cards:
            next(iter(self.cards.values())).jump.click()

    def cancel_edit(self, key):
        self.drafts.pop(key, None)
        self.message.clear()
        self.render()

    def save_note(self, key):
        original, text = self.drafts[key]
        def update(state):
            entity = entity_for(state, key)
            if entity.bookmark != original:
                raise RuleError("Die Notiz wurde inzwischen geändert. Mit „Abbrechen“ den aktuellen Text laden.")
            entity.bookmark = text
        if self.commit(update, "Lesezeichen gespeichert."):
            self.drafts.pop(key, None)
            self.render()

    def commit(self, action, success):
        self.saving = True
        try:
            saved = self.main_window.change(action, success)
        finally:
            self.saving = False
        self.message.setText(success if saved else self.main_window.message.text())
        return saved

    def complete(self, key):
        note = entity_for(self.main_window.state, key).bookmark
        if note is None:
            return
        if self.commit(lambda state: setattr(entity_for(state, key), "bookmark", None), "Lesezeichen erledigt."):
            self.drafts.pop(key, None)
            self.undo_entry = (self.main_window.folder, key, note)
            self.undo_bar.show()
            self.undo_timer.start()
            self.render()

    def undo(self):
        if not self.undo_entry:
            return
        folder, key, note = self.undo_entry
        def restore(state):
            if folder != self.main_window.folder or entity_for(state, key).bookmark is not None:
                raise RuleError("Das Lesezeichen wurde inzwischen neu gesetzt. Es wird nicht überschrieben.")
            entity_for(state, key).bookmark = note
        if self.commit(restore, "Lesezeichen wiederhergestellt."):
            self.clear_undo()
            self.render()

    def clear_undo(self):
        self.undo_timer.stop()
        self.undo_entry = None
        self.undo_bar.hide()

    def resolve_drafts(self):
        if not any(original != text for original, text in self.drafts.values()):
            return True
        choice = QMessageBox.question(self.main_window, "Ungespeicherte Orga-Notizen",
            "Orga-Notizen vor dem Verlassen speichern?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            def update(state):
                for key, (original, text) in self.drafts.items():
                    entity = entity_for(state, key)
                    if entity.bookmark != original:
                        raise RuleError("Eine Notiz wurde inzwischen geändert. Bitte in der Seitenleiste prüfen.")
                    entity.bookmark = text
            if not self.commit(update, "Orga-Notizen gespeichert."):
                return False
        self.drafts.clear()
        self.render()
        return True
