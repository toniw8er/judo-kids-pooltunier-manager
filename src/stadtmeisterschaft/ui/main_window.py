"""Poolübersicht und zentrale Benutzeraktionen."""
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QLockFile, QMimeData, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QDrag, QPalette
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QStyle, QStyleOptionButton, QStylePainter, QVBoxLayout, QWidget,
)

from stadtmeisterschaft.domain import RuleError, Tournament
from stadtmeisterschaft.application import TournamentSession
from stadtmeisterschaft.output import configure_page, paint_document, write_pdf
from stadtmeisterschaft.sheets import write_ods
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.bookmarks import BookmarkDialog, bookmark_icon, install_bookmark_menu, show_bookmark_menu
from stadtmeisterschaft.ui.import_merge import ImportMerge
from stadtmeisterschaft.ui.search_sidebar import SearchSidebar
from stadtmeisterschaft.ui.compact_participants import CompactParticipantDelegate, FIELDS_ROLE, ParticipantColumns
from stadtmeisterschaft.ui.pool_page import PoolPage
from stadtmeisterschaft.ui.tournament_config import TournamentConfig
from stadtmeisterschaft.ui.planning_details import (FriendshipLinks, PlanningWarnings, class_text,
    participant_planning_text, pool_planning_notes, warning_summary)

MIME = "application/x-stadtmeisterschaft-participant"


class ParticipantList(QListWidget):
    moved = Signal(str, str, str)

    def __init__(self, pool_id: str, is_friendship: bool = False):
        super().__init__()
        self.pool_id = pool_id
        self.is_friendship = is_friendship
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#142f42"))
        self.setPalette(palette)
        self.setIconSize(QSize(14, 18))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.bookmark_menu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setSpacing(0)
        self.setItemDelegate(CompactParticipantDelegate(self))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrap(True)
        self.setAutoScroll(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit_height)

    def fit_height(self):
        self.doItemsLayout()
        height = sum(self.sizeHintForRow(i) for i in range(self.count()) if not self.item(i).isHidden())
        self.setFixedHeight(max(30, height + 2 * self.frameWidth() + 2))
        self.updateGeometries()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.fit_timer.start(0)

    def bookmark_menu(self, point):
        item = self.itemAt(point)
        window = self.window()
        if item:
            self.setCurrentItem(item)
            show_bookmark_menu(self, self.viewport().mapToGlobal(point), window, "participant",
                               item.data(Qt.ItemDataRole.UserRole))
        elif self.pool_id:
            show_bookmark_menu(self, self.viewport().mapToGlobal(point), window, "pool", self.pool_id)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(MIME, json.dumps({"participant_id": item.data(Qt.ItemDataRole.UserRole),
                                      "source_pool_id": self.pool_id}).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        window = self.window()
        window.drag_scroll.start()
        try:
            drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction)
        finally:
            window.drag_scroll.stop()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            if self.is_friendship:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            try:
                payload = json.loads(bytes(event.mimeData().data(MIME)).decode())
                participant_id, source_id = payload["participant_id"], payload["source_pool_id"]
                if not isinstance(participant_id, str) or not isinstance(source_id, str):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                event.ignore()
                return
            self.moved.emit(participant_id, self.pool_id, source_id)
            # Keine Qt-interne Listenänderung: ausschließlich gespeichertes Modell anzeigen.
            if self.is_friendship:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
        else:
            event.ignore()


class PoolHeader(QPushButton):
    """Lange Poolnamen dürfen das Raster neben der Seitenleiste nicht verbreitern."""
    def __init__(self, text):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, self)
        width = rect.width() - 12 - (self.iconSize().width() + 4 if not self.icon().isNull() else 0)
        option.text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, max(0, width))
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)


class PoolCard(QFrame):
    """Die Kartenhöhe berücksichtigt auch umgebrochene Labels und Kinderzeilen."""
    def __init__(self):
        super().__init__()
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit_height)

    def fit_height(self):
        if self.layout():
            self.setMinimumHeight(self.layout().totalHeightForWidth(self.width()))

    def event(self, event):
        result = super().event(event)
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize):
            self.fit_timer.start(0)
        return result


class UnassignedCard(PoolCard):
    """Auch die geschlossene Leiste ist ein Ziel für das Zurückziehen."""
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        self.items.dragEnterEvent(event)

    def dragMoveEvent(self, event):
        self.items.dragMoveEvent(event)

    def dropEvent(self, event):
        self.items.dropEvent(event)


class Window(QMainWindow):
    def __init__(self, folder: Path):
        super().__init__()
        self.folder = None
        self.lock = None
        self.lists = {}
        self.headers = {}
        self.pool_details = {}
        self.warning_labels = {}
        self.visible_pool_ids = []
        self.board_columns = 0
        self.unassigned_expanded = False
        self.unassigned_count = 0
        self.setWindowTitle("PoolturnierManager")
        self.resize(1250, 850)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title = QLabel("Pools planen")
        title.setObjectName("title")
        title_row.addWidget(title)
        self.event_label = QLabel()
        self.event_label.setWordWrap(True)
        title_row.addWidget(self.event_label, 1)
        layout.addLayout(title_row)
        self.context_hint = ("Kinder per Drag-and-drop zuordnen. Doppelklick entfernt die Zuordnung.\n"
                             "Poolüberschrift: Ergebnisse öffnen · Rechtsklick: Lesezeichen.")
        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        tools = QHBoxLayout()
        admin = QPushButton("Verwaltung")
        menu = QMenu(admin)
        for label, callback in [
            ("Arbeitsordner öffnen", self.choose_folder),
            ("Wettkampf konfigurieren", self.configure_tournament),
            ("Meldeliste importieren", self.import_sheet),
            ("ODS-Vorlage erstellen", lambda: self.export_ods(False)),
            ("Teilnehmer exportieren", lambda: self.export_ods(True)),
        ]:
            menu.addAction(label, callback)
        menu.addAction("Teilnehmerdatei neu einlesen", self.reload_participant_file)
        admin.setMenu(menu)
        tools.addWidget(admin)
        self.recreate_button = QPushButton("Reguläre Pools neu einteilen")
        self.recreate_button.clicked.connect(self.recreate_regular_pools)
        tools.addWidget(self.recreate_button)
        for label, kind in [("Pool anlegen", "regular"), ("Freundschaftspool anlegen", "friendship")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, current=kind: self.create_pool(current))
            tools.addWidget(button)
        self.context_info = QPlainTextEdit()
        self.context_info.setObjectName("contextInfo")
        self.context_info.setAccessibleName("Kontextinformationen")
        self.context_info.setReadOnly(True)
        self.context_info.setFixedHeight(68)
        self.context_info.setMinimumWidth(180)
        self.context_info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.context_target = None
        self.context_timer = QTimer(self)
        self.context_timer.setSingleShot(True)
        self.context_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.context_timer.setInterval(2000)
        self.context_timer.timeout.connect(self.show_hover_context)
        self.set_context(self.context_hint)
        tools.addWidget(self.context_info, 1)
        for label, callback in [("PDF exportieren", lambda: self.export_pdf()),
                                ("Druckvorschau", lambda: self.preview())]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            tools.addWidget(button)
        layout.addLayout(tools)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Pools anzeigen:"))
        self.pool_filter = QComboBox()
        for label, key in [("Alle", "all"), ("Reguläre Pools", "regular"),
                           ("Einzelpools", "single"), ("Freundschaftspools", "friendship")]:
            self.pool_filter.addItem(label, key)
        self.pool_filter.setToolTip("Filtert nur die Übersicht. Sammel-PDF und Druckvorschau enthalten weiterhin alle belegten Pools.")
        self.pool_filter.currentIndexChanged.connect(self.apply_pool_filter)
        filter_row.addWidget(self.pool_filter)
        self.bookmarks_only = QCheckBox("Nur mit Lesezeichen")
        self.bookmarks_only.toggled.connect(self.apply_pool_filter)
        filter_row.addWidget(self.bookmarks_only)
        self.filter_count = QLabel()
        filter_row.addWidget(self.filter_count)
        filter_row.addStretch()
        self.sidebar_button = QPushButton("Suche && Orga-Notizen · 0")
        self.sidebar_button.setObjectName("sidebarToggle")
        self.sidebar_button.setCheckable(True)
        self.sidebar_button.clicked.connect(lambda checked: self.open_sidebar() if checked else self.sidebar.hide())
        filter_row.addWidget(self.sidebar_button)
        layout.addLayout(filter_row)
        self.status_actions_widget = QWidget()
        status_actions = QHBoxLayout(self.status_actions_widget)
        status_actions.setContentsMargins(0, 0, 0, 0)
        status_actions.addWidget(QLabel("Ausgewähltes Kind · endgültiger Status für alle Pools:"))
        for label, status in [("Rückzug festlegen", "withdrawn"), ("Disqualifizieren", "disqualified")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, current=status: self.set_selected_status(current))
            status_actions.addWidget(button)
        status_actions.addStretch()
        self.status_actions_widget.hide()
        layout.addWidget(self.status_actions_widget)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().installEventFilter(self)
        self.reflow_timer = QTimer(self)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.timeout.connect(self.arrange_pool_cards)
        self.drag_scroll = QTimer(self)
        self.drag_scroll.setInterval(60)
        self.drag_scroll.timeout.connect(self.scroll_while_dragging)
        self.board_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.board_splitter.setChildrenCollapsible(False)
        self.board_splitter.addWidget(self.scroll)
        self.sidebar = SearchSidebar(self)
        self.board_splitter.addWidget(self.sidebar)
        self.board_splitter.setStretchFactor(0, 1)
        self.board_splitter.setStretchFactor(1, 0)
        self.sidebar.hide()
        layout.addWidget(self.board_splitter, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.setCentralWidget(root)
        self.setStyleSheet("""
            QMainWindow { background: #f2f5f7; }
            QLabel { color: #243447; font-size: 12px; }
            QLabel#title { font-size: 23px; font-weight: 700; }
            QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
            QFrame#card, QFrame#unassignedCard { background: white; border: 1px solid #d4dde5; border-radius: 6px; }
            QFrame#friendshipSection { background: #edf4ff; border: 1px solid #8daee0; border-radius: 6px; }
            QFrame#friendshipCard { background: white; border: 1px solid #becfe5; border-radius: 6px; }
            QListWidget { border: none; background: white; font-size: 13px; }
            QListWidget::item:selected { background: #b9dcf0; color: #142f42; }
            QPlainTextEdit#contextInfo { background: #edf4f8; color: #243447; border: 1px solid #d4dde5;
                                        border-radius: 5px; padding: 4px; font-size: 12px; }
            QPushButton { padding: 5px 8px; background: white; border: 1px solid #becbd5; border-radius: 5px; }
            QPushButton:hover { background: #e1eef5; }
            QPushButton#sidebarToggle:checked { background: #e9dcf6; color: #562483; }
            QComboBox { padding: 7px; min-width: 115px; }
            QLineEdit { padding: 7px; background: white; border: 1px solid #becbd5; border-radius: 5px; }
            QFrame#organizerCard { background: white; border: 1px solid #d4dde5; border-radius: 6px; }
            QLabel#organizerHeading { font-weight: 700; color: #562483; }
            QLabel#organizerContext { color: #596a7b; }
            QLabel#organizerNote { font-size: 13px; }
            QTabBar::tab { padding: 7px 8px; background: #e6ebef; color: #243447; }
            QTabBar::tab:selected { background: #e9dcf6; color: #562483; font-weight: 600; }
            QSplitter::handle { background: #d4dde5; width: 4px; }
        """)
        self.open_folder(folder)
        QApplication.instance().installEventFilter(self)

    def scroll_while_dragging(self):
        viewport = self.scroll.viewport()
        point = viewport.mapFromGlobal(QCursor.pos())
        if not viewport.rect().contains(point):
            return
        direction = -1 if point.y() < 45 else (1 if point.y() > viewport.height() - 45 else 0)
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.value() + direction * 24)

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.reflow_timer.start(0)
        if isinstance(watched, QWidget) and watched.window() is self:
            if event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                if self.context_target and self.context_target[0] is watched:
                    self.cancel_hover_context()
            elif event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.Wheel, QEvent.Type.WindowDeactivate):
                self.cancel_hover_context()
            if event.type() in (QEvent.Type.ToolTip, QEvent.Type.MouseMove, QEvent.Type.Enter):
                target = None
                parent = watched.parentWidget()
                if isinstance(parent, ParticipantList) and watched is parent.viewport():
                    point = event.pos() if event.type() == QEvent.Type.ToolTip else event.position().toPoint()
                    item = parent.itemAt(point)
                    if item:
                        target = (watched, item.data(Qt.ItemDataRole.UserRole), item.toolTip())
                elif watched.toolTip():
                    target = (watched, None, watched.toolTip())
                # Qt reicht Mausereignisse an Eltern ohne eigene Hilfe weiter.
                # Diese dürfen den Timer des eigentlichen Ziels nicht abbrechen.
                if target != self.context_target and (target or (
                        self.context_target and self.context_target[0] is watched)):
                    self.cancel_hover_context()
                    self.context_target = target
                    if target:
                        self.context_timer.start()
                # Hilfen stehen in der Übersicht im Kopf statt über den Kinderzeilen.
                if event.type() == QEvent.Type.ToolTip:
                    return True
        return super().eventFilter(watched, event)

    def cancel_hover_context(self):
        self.context_timer.stop()
        self.context_target = None

    def show_hover_context(self):
        if self.context_target:
            self.set_context(self.context_target[2])

    def set_context(self, text):
        self.cancel_hover_context()
        if text.startswith("Lesezeichen:") and "\n\n" in text:
            note, _, participant = text.partition("\n\n")
            text = participant + "\n" + note
        text = "\n".join(line for line in text.splitlines() if line.strip())
        if self.context_info.toPlainText() != text:
            self.context_info.setPlainText(text)

    def notify(self, text: str, error=False):
        self.message.setStyleSheet("color: #a12621; font-weight: 600;" if error else "color: #245d47;")
        self.message.setText(text)

    def open_folder(self, folder: Path):
        folder = folder.resolve()
        if self.folder and folder != self.folder and not self.sidebar.resolve_drafts():
            return
        if folder == self.folder:
            self.state = self.store.load()
            self.session = TournamentSession(self.store, self.state)
            error = self.check_participant_file_at_start()
            self.refresh()
            self.notify(error or "Gespeicherten Stand erneut geladen.", bool(error))
            return
        folder.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(folder / ".technikversuch.lock"))
        if not lock.tryLock(100):
            raise RuleError("Dieser Arbeitsordner ist bereits geöffnet oder gesperrt.")
        try:
            store = Store(folder)
            state = store.load()
            if state is None:
                state = Tournament([], [])
                store.save(state)
        except Exception:
            lock.unlock()
            raise
        if self.lock:
            self.lock.unlock()
        self.lock, self.store, self.state, self.folder = lock, store, state, folder
        self.session = TournamentSession(store, state)
        error = self.check_participant_file_at_start()
        self.folder_label.setText(f"Arbeitsordner: {folder}")
        self.event_label.setToolTip(self.folder_label.text())
        self.build_board()
        self.refresh()
        self.notify(error or "Gespeicherten Stand geöffnet. Alle folgenden Änderungen werden automatisch gespeichert.", bool(error))

    def check_participant_file_at_start(self):
        try:
            self.state = self.session.check_participants_at_start()
        except Exception as exc:
            self.state = self.session.state
            return f"Teilnehmerdatei beim Start nicht übernommen: {exc} Weiterarbeit mit letztem gültigen gespeicherten Stand."
        return None

    def build_board(self):
        board = QWidget()
        board_layout = QVBoxLayout(board)
        board_layout.setContentsMargins(8, 8, 8, 8)
        board_layout.setSpacing(14)
        board_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards = {}
        self.section_widgets, self.section_headers, self.section_grids = {}, {}, {}
        for key, label in [("regular", "Reguläre Pools"), ("friendship", "Freundschaftskämpfe")]:
            section = QFrame()
            section.setObjectName("friendshipSection" if key == "friendship" else "regularSection")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(8, 8, 8, 8)
            heading = QLabel(label)
            heading.setObjectName("sectionTitle")
            section_layout.addWidget(heading)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)
            section_layout.addLayout(grid)
            board_layout.addWidget(section)
            self.section_widgets[key], self.section_headers[key], self.section_grids[key] = section, heading, grid
        self.board_columns = 0
        self.lists, self.headers, self.pool_details, self.warning_labels = {}, {}, {}, {}
        self.friendship_links = {}
        entries = [("", "Noch ohne Pool")] + [(p.id, p.id) for p in self.state.sorted_pools()]
        for pool_id, label in entries:
            pool = self.state.pool(pool_id) if pool_id else None
            card = PoolCard() if pool_id else UnassignedCard()
            self.cards[pool_id] = card
            card.setObjectName("friendshipCard" if pool and pool.is_friendship else "card" if pool_id else "unassignedCard")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(4)
            header = PoolHeader(label)
            header.setStyleSheet("font-weight: 700; font-size: 14px; text-align: left;")
            layout.addWidget(header)
            detail = QLabel()
            detail.setWordWrap(True)
            layout.addWidget(detail)
            self.pool_details[pool_id] = detail
            if pool_id:
                install_bookmark_menu(card, self, "pool", pool_id)
                install_bookmark_menu(header, self, "pool", pool_id)
                install_bookmark_menu(detail, self, "pool", pool_id)
                links = FriendshipLinks()
                links.activated.connect(self.open_pool)
                layout.addWidget(links)
                self.friendship_links[pool_id] = links
            warning = PlanningWarnings()
            layout.addWidget(warning)
            self.warning_labels[pool_id] = warning
            items = ParticipantList(pool_id, pool.is_friendship if pool else False)
            items.moved.connect(self.move)
            items.itemSelectionChanged.connect(lambda current=items: self.exclusive_selection(current))
            columns = ParticipantColumns()
            layout.addWidget(columns)
            layout.addWidget(items)
            self.lists[pool_id], self.headers[pool_id] = items, header
            if pool_id:
                header.clicked.connect(lambda checked=False, current=pool_id: self.open_pool(current))
                items.itemDoubleClicked.connect(
                    lambda item, current=pool_id: self.remove_from_pool(item.data(Qt.ItemDataRole.UserRole), current))
                header.setToolTip("Pool öffnen: Ergebnisse und optionalen Poolnamen bearbeiten")
            else:
                self.unassigned_columns = columns
                card.items = items
                header.setCheckable(True)
                header.setChecked(self.unassigned_expanded)
                header.toggled.connect(self.toggle_unassigned)
                header.setToolTip("Kinder ohne regulären Pool ein-/ausblenden. Hierherziehen entfernt die Ausgangszuordnung.")
                board_layout.insertWidget(0, card)
        # Auch ausgeblendete Karten gehören zum aktuellen Board und werden damit freigegeben.
        for pool_id, card in self.cards.items():
            if pool_id:
                card.setParent(self.section_widgets["friendship" if self.state.pool(pool_id).is_friendship else "regular"])
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(board)

    def toggle_unassigned(self, expanded):
        self.unassigned_expanded = expanded
        self.lists[""].setVisible(expanded)
        self.unassigned_columns.setVisible(expanded)
        self.pool_details[""].setVisible(expanded)

    def arrange_pool_cards(self):
        if not hasattr(self, "section_grids"):
            return
        columns = max(1, (self.scroll.viewport().width() - 40) // 440)
        for grid in self.section_grids.values():
            while grid.count():
                grid.takeAt(0)
            for column in range(max(self.board_columns, columns)):
                grid.setColumnStretch(column, 1 if column < columns else 0)
        self.board_columns = columns
        for key, label in [("regular", "Reguläre Pools"), ("friendship", "Freundschaftskämpfe")]:
            ids = [pid for pid in self.visible_pool_ids if self.state.pool(pid).is_friendship == (key == "friendship")]
            self.section_widgets[key].setVisible(bool(ids))
            self.section_headers[key].setText(f"{label} · {len(ids)}")
            for index, pid in enumerate(ids):
                self.section_grids[key].addWidget(self.cards[pid], index // columns, index % columns,
                                                 Qt.AlignmentFlag.AlignTop)
        for items in self.lists.values():
            items.fit_height()

    def exclusive_selection(self, current):
        if current.selectedItems():
            for items in self.lists.values():
                if items is not current:
                    items.clearSelection()
        self.status_actions_widget.setVisible(any(items.selectedItems() for items in self.lists.values()))
        selected = current.selectedItems()
        self.set_context(selected[0].toolTip() if selected else self.context_hint)

    def refresh(self):
        self.set_context(self.context_hint)
        self.setWindowTitle("PoolturnierManager" + (" · ENTWICKLUNG / TESTDATEN" if self.state.is_demo else ""))
        event_date = QDate.fromString(self.state.event_date, "yyyy-MM-dd")
        date_label = event_date.toString("dd.MM.yyyy") if event_date.isValid() else "Datum bitte konfigurieren"
        classes_label = f"{len(self.state.age_classes)} Altersklassen" if self.state.age_classes else "Altersklassen noch nicht konfiguriert"
        self.event_label.setText(f"{self.state.name} · {date_label} · {classes_label}")
        assigned = {pid for pool in self.state.pools if not pool.is_friendship for pid in pool.members}
        for pool_id, items in self.lists.items():
            items.clear()
            if pool_id:
                pool = self.state.pool(pool_id)
                ids = pool.members
                self.headers[pool_id].setIcon(bookmark_icon(pool.bookmark is not None))
                self.headers[pool_id].setToolTip(pool.display_name + "\nPool öffnen · Rechtsklick: Lesezeichen"
                    + ("\nLesezeichen: " + (pool.bookmark or "(ohne Notiz)") if pool.bookmark is not None else ""))
                self.headers[pool_id].setText(("Freundschaftskampf · " if pool.is_friendship else "") + pool.display_name)
                result = f" · {len(pool.results)} Ergebnisse gespeichert" if pool.results else ""
                status = (" · Abgeschlossen · Besetzung gesperrt" if pool.completed else
                          " · Offen · Besetzung gesperrt" if pool.started else " · Noch nicht gestartet")
                note = self.state.pool_class_note(pool_id)
                class_note = " · " + note if note else ""
                weight_note = self.state.pool_weight_note(pool_id)
                class_note += " · " + weight_note if weight_note else ""
                class_note += " · Matte: " + pool.mat if pool.mat else ""
                class_note += f" · Papierstand {pool.print_revision}"
                extra = "Zusätzliche Teilnahme · " if pool.is_friendship else ""
                self.pool_details[pool_id].setText(f"{extra}{len(ids)}/5 Kinder{result}{status}{class_note}")
                self.friendship_links[pool_id].refresh(self.state, pool_id)
                self.warning_labels[pool_id].set_notes(pool_planning_notes(self.state, pool_id))
            else:
                ids = [p.id for p in self.state.participants if p.id not in assigned]
                self.headers[pool_id].setText(f"Noch ohne Pool · {len(ids)}")
                self.pool_details[pool_id].setText("Ohne regulären Pool. Hierherziehen entfernt die Zuordnung aus dem Ausgangspool; andere Teilnahmen bleiben erhalten.")
                self.warning_labels[pool_id].hide()
                if ids and not self.unassigned_count:
                    self.unassigned_expanded = True
                if not ids:
                    self.unassigned_expanded = False
                self.unassigned_count = len(ids)
                self.headers[pool_id].setChecked(self.unassigned_expanded)
                self.toggle_unassigned(self.unassigned_expanded)
            for pid in ids:
                p = self.state.participant(pid)
                weight = f"{p.weight_grams / 1000:.1f}".replace(".", ",")
                gender = "W" if p.gender == "F" else p.gender
                warnings = self.state.pool_member_warnings(pool_id, pid) if pool_id else []
                note = ("Hinweis: " + warning_summary(warnings, compact=True)) if warnings else (
                    self.state.participant_planning_note(pid) if not pool_id else "")
                status_note = "\n" + p.status_label if p.withdrawn or p.disqualified else ""
                item = QListWidgetItem(f"{p.name}{status_note}\n{weight} kg · {class_text(self.state, pid)} · Jg. {p.birth_year} · {gender}" + ("\n" + note if note else ""))
                item.setData(FIELDS_ROLE, ((p.name, weight, class_text(self.state, pid), str(p.birth_year), gender),
                                          " · ".join(part for part in (status_note.strip(), note) if part)))
                item.setIcon(bookmark_icon(p.bookmark is not None))
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                item.setToolTip("\n".join([participant_planning_text(self.state, pid), p.club, *warnings]))
                item.setBackground(QColor("#edf4f8"))
                if warnings:
                    item.setForeground(QColor("#7a4000"))
                if p.disqualified:
                    item.setForeground(QColor("#666666"))
                    item.setBackground(QColor("#e4e4e4"))
                if p.bookmark is not None:
                    item.setToolTip("Lesezeichen: " + (p.bookmark or "(ohne Notiz)") + "\n\n" + item.toolTip())
                items.addItem(item)
        self.apply_pool_filter()
        self.sidebar.refresh()

    def open_sidebar(self, notes=None):
        was_hidden = self.sidebar.isHidden()
        self.sidebar.open(notes)
        if was_hidden:
            self.board_splitter.setSizes([max(400, self.board_splitter.width() - 390), 390])

    def show_pool(self, pool_id):
        if pool_id not in self.cards:
            return
        reset_filters = self.cards[pool_id].isHidden()
        if reset_filters:
            self.pool_filter.setCurrentIndex(self.pool_filter.findData("all"))
            self.bookmarks_only.setChecked(False)
        header = self.headers[pool_id]
        header.setFocus()
        original = header.property("navigationBaseStyle") or header.styleSheet()
        header.setProperty("navigationBaseStyle", original)
        header.setStyleSheet(original + "background: #e9dcf6; border: 2px solid #7135ab;")
        QTimer.singleShot(1800, header, lambda: header.setStyleSheet(original))
        QTimer.singleShot(0, self, lambda: self.scroll.ensureWidgetVisible(self.headers[pool_id], 40, 80)
                          if pool_id in self.headers else None)
        self.notify(self.state.pool(pool_id).display_name
                    + (" · Ansichtsfilter zurückgesetzt." if reset_filters else ""))

    def show_participant(self, participant_id, pool_id):
        items = self.lists.get(pool_id)
        if items is None:
            return
        item = next((items.item(i) for i in range(items.count())
                     if items.item(i).data(Qt.ItemDataRole.UserRole) == participant_id), None)
        if item is None:
            return
        reset_filters = self.cards[pool_id].isHidden() or item.isHidden()
        if reset_filters:
            self.pool_filter.setCurrentIndex(self.pool_filter.findData("all"))
            self.bookmarks_only.setChecked(False)
        if not pool_id:
            self.headers[""].setChecked(True)
        items.setCurrentItem(item)
        item.setSelected(True)
        items.setFocus()
        # Filter und aufgeklappte Karten müssen vor dem Scrollen neu angeordnet sein.
        def reveal():
            items = self.lists.get(pool_id)
            if items is None or not items.currentItem():
                return
            item = items.currentItem()
            if item.data(Qt.ItemDataRole.UserRole) != participant_id:
                return
            self.scroll.widget().layout().activate()
            point = items.mapTo(self.scroll.widget(), items.visualItemRect(item).center())
            self.scroll.ensureVisible(point.x(), point.y(), 40, 80)
        QTimer.singleShot(0, self, reveal)
        label = self.state.pool(pool_id).display_name if pool_id else "Noch ohne Pool"
        self.notify(f"{self.state.participant(participant_id).name} · {label}"
                    + (" · Ansichtsfilter zurückgesetzt." if reset_filters else ""))

    def apply_pool_filter(self):
        key = self.pool_filter.currentData()
        visible = []
        for pool in self.state.sorted_pools():
            if (key == "all" or key == "regular" and not pool.is_friendship
                    or key == "single" and not pool.is_friendship and len(pool.members) == 1
                    or key == "friendship" and pool.is_friendship):
                if (not self.bookmarks_only.isChecked() or pool.bookmark is not None
                        or any(self.state.participant(pid).bookmark is not None for pid in pool.members)):
                    visible.append(pool.id)
        show_unassigned = key == "all" and (not self.bookmarks_only.isChecked() or any(
            self.state.participant(self.lists[""].item(i).data(Qt.ItemDataRole.UserRole)).bookmark is not None
            for i in range(self.lists[""].count())))
        ordered = ([""] if show_unassigned else []) + visible
        for i in range(self.lists[""].count()):
            item = self.lists[""].item(i)
            item.setHidden(self.bookmarks_only.isChecked() and self.state.participant(
                item.data(Qt.ItemDataRole.UserRole)).bookmark is None)
        for pool_id, card in self.cards.items():
            card.setVisible(pool_id in ordered)
            if pool_id not in ordered:
                self.lists[pool_id].clearSelection()
        self.visible_pool_ids = visible
        self.arrange_pool_cards()
        self.filter_count.setText(f"{len(visible)} von {len(self.state.pools)} Pools"
                                  + (" · Keine passenden Pools" if not visible else ""))

    def edit_bookmark(self, kind, entity_id, parent=None):
        return BookmarkDialog(self, kind, entity_id, parent).exec()

    def confirm_participant_status(self, participant_id, status):
        person = self.state.participant(participant_id)
        label = "Rückzug" if status == "withdrawn" else "Disqualifikation"
        question = QMessageBox(self)
        question.setWindowTitle(label + " endgültig festlegen")
        question.setText(f"{person.name}: {label} für alle regulären und Freundschaftsteilnahmen festlegen?\n\n"
                         "Das kann nicht zurückgenommen werden. Betroffene Begegnungen werden sofort gewertet. "
                         "Geänderte abgeschlossene Pools müssen erneut abgeschlossen werden.")
        question.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        question.button(QMessageBox.StandardButton.Yes).setText(label + " festlegen")
        question.button(QMessageBox.StandardButton.No).setText("Abbrechen")
        question.setDefaultButton(QMessageBox.StandardButton.No)
        return question.exec() == QMessageBox.StandardButton.Yes

    def set_selected_status(self, status):
        selected = [item for items in self.lists.values() for item in items.selectedItems()]
        if not selected:
            self.notify("Bitte zuerst ein Kind in einer Liste auswählen.", True)
            return False
        pid = selected[0].data(Qt.ItemDataRole.UserRole)
        if not self.confirm_participant_status(pid, status):
            return False
        return self.change(lambda state: state.set_participant_status(pid, status), "Endgültiger Teilnehmerstatus gespeichert.")

    def change(self, action, success):
        try:
            candidate = self.session.change(action)
        except Exception as exc:
            self.notify(f"Nicht übernommen: {exc}", True)
            return False
        self.state = candidate
        if set(self.lists) != {"", *(pool.id for pool in candidate.pools)}:
            self.build_board()
        self.refresh()
        self.notify(f"Gespeichert um {datetime.now():%H:%M:%S} · {success}")
        return True

    def move(self, participant_id, target_id, source_id=None):
        self.change(lambda state: state.move(participant_id, target_id, source_id), "Poolzuordnung aktualisiert.")

    def recreate_regular_pools(self):
        if not self.state.age_classes:
            self.notify("Bitte zuerst über „Wettkampf konfigurieren“ Altersklassen festlegen.", True)
            return False
        question = QMessageBox(self)
        question.setWindowTitle("Reguläre Pools neu einteilen")
        question.setText("Alle ungestarteten regulären Pools werden einschließlich manueller Zuordnungen "
                         "und Poolnamen durch eine automatische Einteilung ersetzt.\n\n"
                         "Gestartete Pools und alle Freundschaftspools bleiben erhalten. "
                         "Kinder ohne passende Altersklasse bleiben als Klärfälle unter „Noch ohne Pool“.\n\n"
                         "Jetzt neu einteilen?")
        question.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        question.button(QMessageBox.StandardButton.Yes).setText("Neu einteilen")
        question.button(QMessageBox.StandardButton.No).setText("Abbrechen")
        question.setDefaultButton(QMessageBox.StandardButton.No)
        if question.exec() != QMessageBox.StandardButton.Yes:
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.recreate_button.setEnabled(False)
        try:
            success = self.change(lambda state: state.recreate_regular_pools(), "Reguläre Pools neu erstellt.")
            if success:
                regular = [p for p in self.state.pools if not p.is_friendship]
                assigned = {pid for pool in regular for pid in pool.members}
                missing = sum(p.id not in assigned for p in self.state.participants)
                singles = sum(len(p.members) == 1 for p in regular)
                self.notify(f"Gespeichert · {len(regular)} reguläre Pools · {singles} Einzelpools · "
                            f"{missing} Kinder ohne passende Altersklasse noch ohne Pool.")
            return success
        finally:
            self.recreate_button.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def remove_from_pool(self, participant_id, pool_id):
        pool = self.state.pool(pool_id)
        name = self.state.participant(participant_id).name
        message = (f"{name}: zusätzliche Teilnahme entfernt." if pool.is_friendship
                   else f"{name} ist jetzt unter „Noch ohne Pool“.")
        return self.change(lambda state: state.move(participant_id, "", pool_id), message)

    def create_pool(self, kind="regular"):
        created = []
        if self.change(lambda state: created.append(state.create_pool(kind)), "Pool angelegt. Kinder per Drag-and-drop hinzufügen."):
            self.scroll.ensureWidgetVisible(self.headers[created[0]])
            self.headers[created[0]].setFocus()
            return created[0]
        return None

    def delete_pool(self, pool_id):
        pool = self.state.pool(pool_id)
        if pool.started:
            self.notify("Gestartete Pools dürfen nicht gelöscht werden.", True)
            return False
        consequence = ("Nur die zusätzlichen Teilnahmen in diesem Freundschaftspool werden entfernt."
                       if pool.is_friendship else "Die Kinder bleiben erhalten und erscheinen ohne reguläre Zuordnung unter „Noch ohne Pool“.")
        question = QMessageBox(self)
        question.setWindowTitle("Pool löschen")
        question.setText(f"{pool.display_name} löschen?\n\n{consequence}\n"
                         "Ungespeicherte Eingaben auf der Poolseite werden verworfen.")
        question.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        question.button(QMessageBox.StandardButton.Yes).setText("Pool löschen")
        question.button(QMessageBox.StandardButton.No).setText("Abbrechen")
        question.setDefaultButton(QMessageBox.StandardButton.No)
        answer = question.exec()
        if answer != QMessageBox.StandardButton.Yes:
            return False
        return self.change(lambda state: state.delete_pool(pool_id), "Pool gelöscht; Teilnehmerdaten bleiben erhalten.")

    def open_pool(self, pool_id):
        while pool_id:
            page = PoolPage(self, pool_id)
            page.exec()
            pool_id = page.next_pool_id

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Arbeitsordner auswählen", str(self.folder))
        if folder:
            try:
                self.open_folder(Path(folder))
            except Exception as exc:
                self.notify(str(exc), True)

    def import_sheet(self):
        path, _ = QFileDialog.getOpenFileName(self, "Neue Meldungen importieren", str(self.folder), "Tabellen (*.ods *.xlsx)")
        if not path:
            return
        try:
            prepared = self.session.prepare_import(Path(path))
            if prepared.comparison.conflicts:
                dialog = ImportMerge(self, prepared)
                if not dialog.exec():
                    self.notify("Import abgebrochen; keine Meldungen übernommen.")
            else:
                self.apply_import(prepared)
        except Exception as exc:
            self.notify(f"Import nicht übernommen: {exc}", True)

    def apply_import(self, prepared, weights=None):
        self.state, result = self.session.commit_import(prepared, weights)
        self.refresh()
        self.notify(result.message + " Neue Kinder noch ohne Pool. Gemeinsame Datei: teilnehmer.ods im Arbeitsordner.")

    def reload_participant_file(self):
        try:
            self.state = self.session.reload_participants()
            self.refresh()
            self.notify("teilnehmer.ods übernommen. Extern bearbeiten, speichern und schließen; neue Kinder ohne Teilnehmer-ID ergänzen.")
            return True
        except Exception as exc:
            self.notify(f"Teilnehmerdatei nicht übernommen: {exc}", True)
            return False

    def export_ods(self, populated):
        name = "teilnehmer-export.ods" if populated else "teilnehmervorlage.ods"
        path, _ = QFileDialog.getSaveFileName(self, "ODS exportieren", str(self.folder / name), "ODS (*.ods)")
        if path:
            try:
                if Path(path).resolve() == self.store.participant_path.resolve():
                    raise RuleError("Die gemeinsame teilnehmer.ods bitte über „Teilnehmerdatei neu einlesen“ verwalten.")
                write_ods(Path(path), self.state.participants if populated else None)
                self.notify("ODS-Datei geschrieben. Gemeinsame Bearbeitungsdatei: teilnehmer.ods im Arbeitsordner.")
            except Exception as exc:
                self.notify(f"ODS nicht geschrieben: {exc}", True)

    def configure_tournament(self):
        TournamentConfig(self).exec()

    def export_pdf(self, *, pool_id=None):
        pools = [self.state.pool(pool_id)] if pool_id else [p for p in self.state.sorted_pools() if p.members]
        title = "Pool als PDF exportieren" if pool_id else "Alle belegten Pools als PDF exportieren"
        name = "poolliste.pdf" if pool_id else "poollisten.pdf"
        path, _ = QFileDialog.getSaveFileName(self, title, str(self.folder / name), "PDF (*.pdf)")
        if path:
            try:
                write_pdf(Path(path), self.state, pools)
                self.notify(f"PDF geschrieben: {path}")
            except Exception as exc:
                self.notify(f"PDF nicht geschrieben: {exc}", True)

    def preview(self, *, pool_id=None):
        pools = [self.state.pool(pool_id)] if pool_id else [p for p in self.state.sorted_pools() if p.members]
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        configure_page(printer)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("A4-Poollisten · Druckvorschau")

        def render(device):
            try:
                paint_document(device, self.state, pools)
            except Exception as exc:
                self.notify(f"Druck fehlgeschlagen: {exc}", True)

        preview.paintRequested.connect(render)
        preview.exec()

    def closeEvent(self, event):
        if not self.sidebar.resolve_drafts():
            event.ignore()
            return
        self.cancel_hover_context()
        QApplication.instance().removeEventFilter(self)
        if self.lock:
            self.lock.unlock()
        event.accept()
