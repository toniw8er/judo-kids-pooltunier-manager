"""Begrenzter ODS/XLSX-Import für die Anwendung; keine Office-Automation."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from math import isfinite, ulp
from pathlib import Path
from uuid import uuid4

from odf import teletype
from odf.opendocument import OpenDocumentSpreadsheet, load
from odf.table import Table, TableCell, TableRow
from odf.text import P
from openpyxl import load_workbook

from stadtmeisterschaft.domain import Participant, RuleError, parse_weight

HEADERS = ["Vorname", "Nachname", "Verein", "Geburtsjahr", "Geschlecht", "Gewicht in kg"]
MAX_ROWS = 10000


def ods_rows(path: Path, content: bytes | None = None) -> list[list]:
    doc = load(BytesIO(content) if content is not None else str(path))
    tables = doc.spreadsheet.getElementsByType(Table)
    if len(tables) != 1:
        raise RuleError("Für den Import ist genau ein Tabellenblatt erforderlich.")
    rows = []
    for row in tables[0].getElementsByType(TableRow):
        values = []
        for cell in row.childNodes:
            if cell.qname[1] not in {"table-cell", "covered-table-cell"}:
                continue
            if cell.getAttribute("formula"):
                raise RuleError("Formelzellen werden im Import nicht übernommen.")
            value = (cell.getAttribute("datevalue") if cell.getAttribute("valuetype") == "date"
                     else cell.getAttribute("value"))
            if value is None:
                value = teletype.extractText(cell)
            elif cell.getAttribute("valuetype") == "float" and len(values) == 5:
                # Spalte F: Zahlenwert erhalten, um binäre Gewichtsartefakte zu erkennen.
                try:
                    value = float(value)
                except ValueError:
                    pass  # Fehler mit Datei und Zeile bei der Feldprüfung melden.
            repeated = int(cell.getAttribute("numbercolumnsrepeated") or 1)
            # Calc speichert große leere Restbereiche komprimiert.
            if repeated > 100 and str(value).strip():
                raise RuleError("Zu viele wiederholte belegte Spalten.")
            values.extend([value] * min(repeated, 100))
        repeated = int(row.getAttribute("numberrowsrepeated") or 1)
        if not any(str(v).strip() for v in values):
            # Leere Wiederholungen als Zeilenzahl erhalten, ohne riesige Listen.
            repeated = min(repeated, MAX_ROWS - len(rows))
        if len(rows) + repeated > MAX_ROWS:
            raise RuleError("Die Datei überschreitet die Grenze von 10.000 Zeilen beim Import.")
        rows.extend([values] * repeated)
    return rows


def read_participants(path: Path, *, with_ids: bool = False,
                      content: bytes | None = None,
                      known_ids: set[str] | None = None) -> list[Participant]:
    if with_ids and path.suffix.lower() != ".ods":
        raise RuleError("Die gemeinsame Teilnehmerdatei muss eine ODS-Datei sein.")
    if path.suffix.lower() == ".ods":
        rows = ods_rows(path, content)
    elif path.suffix.lower() == ".xlsx":
        book = load_workbook(path, read_only=True, data_only=False)
        try:
            if len(book.worksheets) != 1:
                raise RuleError("Für den Import ist genau ein Tabellenblatt erforderlich.")
            sheet = book.worksheets[0]
            if sheet.max_row > MAX_ROWS or sheet.max_column > 100:
                raise RuleError("Zu viele Zeilen oder Spalten für die Anwendung.")
            rows = []
            for row in sheet.iter_rows():
                if any(c.data_type == "f" for c in row):
                    raise RuleError("Formelzellen werden im Import nicht übernommen.")
                rows.append([c.value for c in row])
        finally:
            book.close()
    else:
        raise RuleError("Bitte eine ODS- oder XLSX-Datei auswählen.")
    if not rows:
        raise RuleError("Die Teilnehmerdatei ist leer.")
    headers = [str(v or "").strip() for v in rows[0]]
    while headers and not headers[-1]:
        headers.pop()
    expected = HEADERS + (["Teilnehmer-ID"] if with_ids else [])
    if "Geburtsjahr" in headers and "Geburtsdatum" in headers:
        raise RuleError("Bitte genau eine Spalte verwenden: Geburtsjahr oder Geburtsdatum, niemals beide.")
    date_headers = expected.copy()
    date_headers[3] = "Geburtsdatum"
    if headers not in (expected, date_headers):
        raise RuleError("Erwartete Spalten in dieser Reihenfolge: Vorname, Nachname, Verein, "
                        "Geburtsjahr oder Geburtsdatum (genau eine Spalte), Geschlecht, Gewicht in kg"
                        + (", Teilnehmer-ID." if with_ids else ". Für die gemeinsame Datei bitte „Teilnehmerdatei neu einlesen“ verwenden."))
    people = []
    seen_ids = set()
    for number, row in enumerate(rows[1:], 2):
        values = [str(v).strip() if v is not None else "" for v in row]
        if not any(values):
            continue
        try:
            if len(values) < 6 or not all(values[:6]) or any(values[7 if with_ids else 6:]):
                raise RuleError("Alle sechs Pflichtfelder ausfüllen; keine zusätzlichen Werte.")
            year = birth_year(row[3], from_date=headers[3] == "Geburtsdatum")
            gender = {"M": "M", "J": "M", "W": "F", "F": "F"}.get(values[4].upper())
            if gender is None:
                raise RuleError("Geschlecht als M oder J für männlich/Junge bzw. W oder F für weiblich angeben.")
            participant_id = (values[6] if len(values) > 6 else "") if with_ids else str(uuid4())
            if participant_id in seen_ids:
                raise RuleError("Doppelte Teilnehmer-ID.")
            if participant_id and known_ids is not None and participant_id not in known_ids:
                raise RuleError("Unbekannte Teilnehmer-ID. Bestehende IDs dürfen nicht geändert werden.")
            if participant_id:
                seen_ids.add(participant_id)
            people.append(Participant(participant_id, *values[:3], int(year), gender, import_weight(row[5])))
        except RuleError as exc:
            raise RuleError(f"{path.name}, Zeile {number}: {exc}") from exc
    if not people and not with_ids:
        raise RuleError("Die Datei enthält keine Meldungen.")
    return people


def import_weight(value) -> int:
    if isinstance(value, float) and isfinite(value):
        nearest = round(value, 1)
        # Nur binäre Speicherabweichungen numerischer Zellen ausgleichen.
        # Textwerte und tatsächlich genauere Gewichte bleiben unverändert streng.
        if abs(value - nearest) <= 2 * ulp(value):
            value = nearest
    return parse_weight(value)


def birth_year(value, *, from_date: bool) -> int:
    if from_date:
        try:
            if isinstance(value, date):
                year = value.year
            elif isinstance(value, str):
                text = value.strip()
                if len(text) >= 10 and text[4] == "-" and text[7] == "-":
                    year = datetime.fromisoformat(text).year
                else:
                    year = datetime.strptime(text, "%d.%m.%Y").year
            else:
                raise ValueError
            if not 1900 <= year <= 2100:
                raise ValueError
            return year
        except ValueError:
            raise RuleError("Geburtsdatum muss ein gültiges Datum sein, z. B. 15.03.2016 "
                            "oder 2016-03-15, mit einem Jahr zwischen 1900 und 2100.") from None
    try:
        year = Decimal(str(value).strip())
        if not year.is_finite() or year != year.to_integral_value() or not 1900 <= year <= 2100:
            raise ValueError
        return int(year)
    except (InvalidOperation, ValueError):
        raise RuleError("Geburtsjahr muss eine ganze Jahreszahl sein.") from None


def ods_content(people: list[Participant] | None = None) -> bytes:
    doc = OpenDocumentSpreadsheet()
    table = Table(name="Teilnehmer")
    doc.spreadsheet.addElement(table)
    rows = [HEADERS + (["Teilnehmer-ID"] if people is not None else [])]
    for p in people or []:
        rows.append([p.first_name, p.last_name, p.club, p.birth_year, "W" if p.gender == "F" else p.gender,
                     f"{p.weight_grams / 1000:.1f}".replace(".", ","), p.id])
    for values in rows:
        row = TableRow()
        for value in values:
            cell = TableCell(valuetype="string")
            cell.addElement(P(text=str(value)))
            row.addElement(cell)
        table.addElement(row)
    stream = BytesIO()
    doc.save(stream, addsuffix=False)
    return stream.getvalue()


def write_bytes_atomic(path: Path, content: bytes) -> None:
    from os import fsync, replace
    from tempfile import NamedTemporaryFile

    # Erst fertig schreiben, dann die Zieldatei ersetzen. Fehler lässt Original stehen.
    with NamedTemporaryFile(dir=path.parent, suffix=".ods", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            fsync(handle.fileno())
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_ods(path: Path, people: list[Participant] | None = None) -> None:
    """Vorlage ohne IDs; gemeinsame Teilnehmerdatei und Datenexport mit IDs."""
    write_bytes_atomic(path, ods_content(people))
