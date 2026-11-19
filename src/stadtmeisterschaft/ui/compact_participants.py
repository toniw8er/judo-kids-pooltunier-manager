"""Kompakte Tabellendarstellung für die verschiebbaren Teilnehmerlisten."""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget


FIELDS_ROLE = Qt.ItemDataRole.UserRole + 1
HEADINGS = ("Name", "kg", "Klasse", "Jg.", "M/W")


def column_rects(rect):
    """Identische Spalten in Kopf und Kinderzeilen, mit Platz für Lesezeichen."""
    left = rect.x() + 24
    width = max(1, rect.width() - 30)
    boundaries = [round(width * ratio) for ratio in (0, .40, .55, .80, .92, 1)]
    return [QRect(left + start, rect.y(), max(1, end - start - 6), rect.height())
            for start, end in zip(boundaries, boundaries[1:])]


class ParticipantColumns(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(self.fontMetrics().height() + 8)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.setPen(QColor("#465c70"))
        for text, rect in zip(HEADINGS, column_rects(self.rect())):
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, text)


class CompactParticipantDelegate(QStyledItemDelegate):
    def geometry(self, option, index):
        fields, note = index.data(FIELDS_ROLE)
        width = max(1, self.parent().viewport().width())
        columns = column_rects(QRect(0, 0, width, 10000))
        flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop
        metrics = QFontMetrics(option.font)
        height = max(metrics.boundingRect(rect, flags, text).height()
                     for text, rect in zip(fields, columns))
        note_height = (metrics.boundingRect(
            QRect(0, 0, max(1, width - 30), 10000), flags, note).height() + 3 if note else 0)
        return columns, max(28, height + note_height + 10), height

    def sizeHint(self, option, index):
        self.initStyleOption(option, index)
        if not index.data(FIELDS_ROLE):
            return super().sizeHint(option, index)
        _, height, _ = self.geometry(option, index)
        return QSize(240, height)

    def paint(self, painter, option, index):
        if not index.data(FIELDS_ROLE):
            return super().paint(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        fields, note = index.data(FIELDS_ROLE)
        columns, _, text_height = self.geometry(opt, index)
        icon = QIcon(opt.icon)
        opt.text, opt.icon = "", QIcon()
        # Die vollständige Zeile markiert die Auswahl. Der native Fokusrahmen
        # um den (hier selbst gezeichneten) Text würde Namen und Symbol schneiden.
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        style = opt.widget.style()
        painter.save()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        painter.restore()
        painter.save()
        painter.setFont(opt.font)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(opt.palette.color(QPalette.ColorRole.HighlightedText) if selected else
                       brush.color() if brush else opt.palette.color(QPalette.ColorRole.Text))
        flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop
        for text, rect in zip(fields, columns):
            rect.translate(opt.rect.x(), opt.rect.y() + 5)
            rect.setHeight(text_height)
            painter.drawText(rect, flags, text)
        if not icon.isNull():
            icon.paint(painter, QRect(opt.rect.x() + 5, opt.rect.y() + 5, 14, 18))
        if note:
            painter.drawText(QRect(opt.rect.x() + 24, opt.rect.y() + text_height + 8,
                                   max(1, opt.rect.width() - 30), opt.rect.height() - text_height - 8), flags, note)
        painter.restore()
