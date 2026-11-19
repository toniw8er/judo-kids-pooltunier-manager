"""Eine gemeinsame Zeichenroutine für A4-PDF und Druckvorschau."""
from pathlib import Path
from datetime import date, datetime

from PySide6.QtCore import QMarginsF, QRectF, QSaveFile, QIODevice, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPageLayout, QPageSize, QPdfWriter

from stadtmeisterschaft.domain import FIGHT_ORDER, RESULT_REASONS, Pool, RuleError, Tournament


def draw_pool(painter: QPainter, area: QRectF, state: Tournament, pool: Pool, *, created_at: datetime | None = None) -> None:
    painter.save()
    painter.translate(area.left(), area.top())
    painter.scale(area.width() / 1100, area.height() / 740)
    painter.setPen(Qt.GlobalColor.black)

    def text(x, y, w, h, value, size=10, bold=False, centered=False, right=False, muted=False):
        # Logische Pixel halten PDF und hochauflösenden Druck gleich groß.
        font = QFont("Segoe UI")
        font.setPixelSize(round(size * 1.5))
        font.setBold(bold)
        painter.setFont(font)
        alignment = Qt.AlignmentFlag.AlignVCenter
        if centered:
            alignment |= Qt.AlignmentFlag.AlignHCenter
        elif right:
            alignment |= Qt.AlignmentFlag.AlignRight
        painter.setPen(QColor("#555555") if muted else Qt.GlobalColor.black)
        painter.drawText(QRectF(x, y, w, h), Qt.TextFlag.TextWordWrap | alignment, str(value))
        painter.setPen(Qt.GlobalColor.black)

    def cell(x, y, w, h, value="", *, heading=False, centered=False, size=10, muted=False):
        rect = QRectF(x, y, w, h)
        if heading:
            painter.fillRect(rect, QColor("#e8e8e8"))
        painter.setPen(QColor("#999999"))
        painter.drawRect(rect)
        text(x + 6, y + 2, w - 12, h - 4, value, size, heading, centered, muted=muted)

    people = [state.participant(pid) for pid in pool.members]
    # Feste Kanten und drei Schriftstufen: Pool, Veranstaltung, Metadaten.
    title = "Freundschaftskampf" if pool.is_friendship else "Poolliste"
    text(0, 0, 740, 38, f"{title} · {pool.id}", 23, True)
    subtitle = f"{pool.name} · {state.name}" if pool.name else state.name
    text(0, 41, 740, 28, subtitle, 11)
    if pool.age_class:
        text(0, 68, 740, 12, f"Startklasse: {pool.age_class}", 7)
    if pool.mat:
        text(790, 65, 310, 13, f"Matte: {pool.mat}", 8, True, right=True)
    if people:
        weights = [p.weight_grams for p in people]
        weight_range = f"{min(weights) / 1000:.1f} - {max(weights) / 1000:.1f} kg".replace(".", ",")
        text(790, 0, 120, 30, "Gewichtsspanne", 9, muted=True)
        text(910, 0, 190, 30, weight_range, 13, True, right=True)
    text(790, 37, 120, 28, "Datum", 9, muted=True)
    text(910, 37, 190, 28, f"{date.fromisoformat(state.event_date):%d.%m.%Y}", 11, right=True)
    painter.drawLine(0, 79, 1100, 79)

    # Die Kampffolge ist der Hauptteil für Aushang und Kampfrichtertisch.
    fights = FIGHT_ORDER.get(len(pool.members), [])
    heading_y = 118
    text(0, 87, 440, 27, "Kampffolge", 14, True)
    text(460, 87, 640, 27, "Nur die weißen Ergebnisfelder ausfüllen", 9, right=True, muted=True)
    cell(0, heading_y, 40, 26, "Nr.", heading=True, centered=True, size=9)
    cell(40, heading_y, 345, 26, "Erstgenannte/r", heading=True)
    cell(385, heading_y, 30, 26, "-", heading=True, centered=True)
    cell(415, heading_y, 345, 26, "Zweitgenannte/r", heading=True)
    cell(760, heading_y, 180, 26, "Ausgang 1. : 2.", heading=True, centered=True, size=9)
    cell(940, heading_y, 160, 26, "UB 1. : 2.", heading=True, centered=True, size=9)
    fights_top = heading_y + 26
    row_height = min(54, 300 / max(len(fights), 1))
    fight_font = 11 if len(fights) == 10 else 12
    for index, (a, b) in enumerate(fights):
        y = fights_top + index * row_height
        outcome, score = "___ : ___", "____ : ____"
        result = pool.results.get(str(index + 1))
        if result:
            outcome = result.outcome.replace(":", " : ")
            if result.reason != "played":
                label = RESULT_REASONS[result.reason].split(" · ")[0]
                outcome += (" · 0 Punkte" if result.zero_points else "") + "\n" + label
            score = f"{result.first} : {result.second}"
        painter.fillRect(QRectF(0, y, 760, row_height), QColor("#f5f5f5"))
        cell(0, y, 40, row_height, str(index + 1), centered=True)
        if people[a - 1].disqualified:
            painter.fillRect(QRectF(40, y, 345, row_height), QColor("#dedede"))
        cell(40, y, 345, row_height, people[a - 1].name, size=fight_font, muted=people[a - 1].disqualified)
        cell(385, y, 30, row_height, "-", centered=True)
        if people[b - 1].disqualified:
            painter.fillRect(QRectF(415, y, 345, row_height), QColor("#dedede"))
        cell(415, y, 345, row_height, people[b - 1].name, size=fight_font, muted=people[b - 1].disqualified)
        cell(760, y, 180, row_height, outcome, centered=True, size=7 if result and result.reason != "played" else fight_font)
        cell(940, y, 160, row_height, score, centered=True, size=fight_font)
    if not fights:
        text(0, fights_top + 7, 1100, 32, "Kein Kampf vorgesehen: noch kein Partner im Pool.")

    # Auswertung bleibt nachgeordnet; diese grauen Felder sind keine Papier-Eingabe.
    standings, matrix = state.evaluate_pool(pool.id)
    matrix_heading = fights_top + max(len(fights) * row_height, 45) + 16
    status = "ABGESCHLOSSEN" if pool.completed else "VORLÄUFIG" if pool.ready_to_complete else "UNVOLLSTÄNDIG · keine Plätze"
    text(0, matrix_heading, 660, 24, "Auswertung · " + status, 9, muted=True)
    text(680, matrix_heading, 420, 24, "Matrix: Punkte / eigene UB · nicht ausfüllen", 8, right=True, muted=True)
    table_top = matrix_heading + 26
    name_width, club_width, opponent_width = 300, 240, 46
    matrix_x = name_width + club_width
    summary_x = matrix_x + 5 * opponent_width
    cell(0, table_top, name_width, 26, "Name", heading=True, size=9)
    cell(name_width, table_top, club_width, 26, "Verein", heading=True, size=9)
    for i in range(5):
        cell(matrix_x + i * opponent_width, table_top, opponent_width, 26,
             str(i + 1) if i < len(people) else "", heading=True, centered=True, size=9)
    for i, label in enumerate(["Pkt.", "Siege", "UB +", "UB -", "Diff.", "Platz"]):
        cell(summary_x + i * 55, table_top, 55, 26, label, heading=True, centered=True, size=9)
    for row, person in enumerate(people):
        y = table_top + 26 + row * 38
        if person.disqualified:
            painter.fillRect(QRectF(0, y, name_width + club_width, 38), QColor("#dedede"))
        status_note = "\n" + person.status_label if person.withdrawn or person.disqualified else ""
        cell(0, y, name_width, 38, f"{row + 1}. {person.name}{status_note}", size=9, muted=person.disqualified)
        cell(name_width, y, club_width, 38, person.club, size=8.5)
        painter.fillRect(QRectF(matrix_x, y, 1100 - matrix_x, 38), QColor("#f0f0f0"))
        for opponent in range(5):
            x = matrix_x + opponent * opponent_width
            if opponent == row or opponent >= len(people):
                painter.fillRect(QRectF(x, y, opponent_width, 38), QColor("#d8d8d8"))
            entry = matrix.get((person.id, people[opponent].id)) if opponent < len(people) else None
            value = "X" if opponent == row else f"{entry[0]}/{entry[1]}" if entry is not None else ""
            cell(x, y, opponent_width, 38, value, centered=True, size=8)
        standing = standings[row]
        values = [standing.points, standing.wins, standing.ub_for, standing.ub_against,
                  standing.difference, standing.place if standing.place is not None else ""]
        for column, value in enumerate(values):
            cell(summary_x + column * 55, y, 55, 38, value if pool.results else "", centered=True, size=9)

    text(740, 714, 360, 24,
         f"Stand {pool.print_revision} · erstellt am {created_at or datetime.now():%d.%m.%Y, %H:%M:%S}",
         7, right=True, muted=True)
    text(0, 714, 730, 24,
         "1:0 = Erstgenannte/r gewinnt · 0:1 = Zweitgenannte/r gewinnt · 0:0 = Unentschieden. UB = Unterbewertung."
         + (" ENTWICKLUNG / TESTDATEN." if state.is_demo else ""), 8)
    painter.restore()


def configure_page(device) -> None:
    device.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    device.setPageOrientation(QPageLayout.Orientation.Landscape)
    device.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)


def paint_document(device, state: Tournament, pools: list[Pool]) -> None:
    if not state.event_date:
        raise RuleError("Bitte vor der Ausgabe den Wettkampf konfigurieren und das Veranstaltungsdatum speichern.")
    state.validate()
    painter = QPainter()
    if not painter.begin(device):
        raise OSError("Ausgabegerät konnte nicht geöffnet werden.")
    try:
        created_at = datetime.now()
        for i, pool in enumerate(pools):
            if i and not device.newPage():
                raise OSError("Neue Ausgabeseite konnte nicht erzeugt werden.")
            rect = device.pageLayout().paintRectPixels(device.resolution())
            # Qt platziert den Painter-Ursprung bereits am Rand des bedruckbaren Bereichs.
            draw_pool(painter, QRectF(0, 0, rect.width(), rect.height()), state, pool, created_at=created_at)
    finally:
        painter.end()


def write_pdf(path: Path, state: Tournament, pools: list[Pool]) -> None:
    output = QSaveFile(str(path))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(output.errorString())
    try:
        writer = QPdfWriter(output)
        writer.setResolution(120)
        configure_page(writer)
        writer.setTitle("Poollisten – Stadtmeisterschaft")
        paint_document(writer, state, pools)
        del writer
        if not output.commit():
            raise OSError(output.errorString())
    except Exception:
        output.cancelWriting()
        raise
