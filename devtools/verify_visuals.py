"""Erzeugt reproduzierbare Prüfmuster, keine echten Turnierdaten."""
from devtools.demo_data import demo
from devtools.helpers import demo_window
from pathlib import Path
from tempfile import TemporaryDirectory

from odf.opendocument import OpenDocumentSpreadsheet, load
from odf.table import Table, TableCell, TableRow
from odf.text import P
from openpyxl import Workbook
from PySide6.QtCore import QDate, QEvent, QTimer
from PySide6.QtGui import QFontDatabase, QHelpEvent
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtPrintSupport import QPrinter

from stadtmeisterschaft.domain import AgeClass, FightResult
from stadtmeisterschaft.age_class_defaults import suggested_classes
from stadtmeisterschaft.output import configure_page, paint_document, write_pdf
from stadtmeisterschaft.ui.bookmarks import BookmarkDialog
from stadtmeisterschaft.ui.friendship_search import FriendshipSearch
from stadtmeisterschaft.ui.import_merge import ImportMerge
from stadtmeisterschaft.ui.pool_page import PoolPage
from stadtmeisterschaft.ui.tournament_config import TournamentConfig
from stadtmeisterschaft.sheets import HEADERS, read_participants, write_ods


def sidebar_examples(app, folder, examples):
    """Gezielte Ansichten der gemeinsamen Suche und Orga-Notizen."""
    window = demo_window(folder, 10)
    def prepare(candidate):
        candidate.configure(candidate.name, "2026-11-19", suggested_classes(2026))
        person = candidate.participants[0]
        person.bookmark = "Trainer wegen zusätzlicher Teilnahme ansprechen.\nRückmeldung am Eingang hinterlegen."
        candidate.participants[1].bookmark = ""
        candidate.participants[2].bookmark = "Startgebühr fehlt noch. Vor dem ersten Kampf klären."
        candidate.pool("Pool 02").bookmark = "Aktuelle Poolliste zum Kampfrichter bringen. Alten Ausdruck ersetzen."
        candidate.pool("Pool 02").name = "Abgleich mit dem Kampfrichter und Rückmeldung zur aktuellen Besetzung"
        friend = candidate.create_pool("friendship", "Zusätzliche Begegnung")
        candidate.move(person.id, friend)
        candidate.move(candidate.participants[1].id, friend)
    window.change(prepare, "Prüfmuster Orga-Notizen")
    window.show()
    window.open_sidebar(True)
    def capture(name):
        for _ in range(15):
            app.processEvents()
        window.grab().save(str(examples / name))
    try:
        window.resize(1500, 950)
        capture("orga-notizen-breit.png")
        person = window.state.participants[0]
        window.sidebar.cards[("participant", person.id)].edit.click()
        window.sidebar.cards[("participant", person.id)].editor.setPlainText(
            "Trainer gesprochen. Zusätzliche Begegnung ist vereinbart.\nPoolliste noch abholen.")
        capture("orga-notizen-bearbeiten.png")
        window.sidebar.cards[("participant", person.id)].save.click()
        window.sidebar.cards[("participant", person.id)].done.click()
        capture("orga-notizen-erledigt.png")
        window.sidebar.undo_button.click()
        window.resize(1050, 900)
        capture("orga-notizen-schmal.png")
        window.sidebar.tabs.setCurrentIndex(0)
        window.sidebar.query.setText(person.name)
        capture("orga-suche.png")
        window.sidebar.cards[("participant", person.id)].jump.click()
        capture("orga-suche-kind-markiert.png")
    finally:
        window.close()


def main():
    app = QApplication.instance() or QApplication([])
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
    root = Path(__file__).resolve().parents[1]
    examples = root / "tmp" / "visuals"
    examples.mkdir(parents=True, exist_ok=True)
    ods = examples / "testmeldungen.ods"
    if not ods.exists() or not (examples / "testmeldungen.xlsx").exists():
        values = ["Jörg", "Müller", "Judoclub Äöü", 2016, "M", "25,3"]
        ods = examples / "testmeldungen.ods"
        write_ods(ods)
        doc = load(str(ods))
        row = TableRow()
        for value in values:
            cell = TableCell(valuetype="string")
            cell.addElement(P(text=str(value)))
            row.addElement(cell)
        doc.spreadsheet.getElementsByType(Table)[0].addElement(row)
        doc.save(str(ods), addsuffix=False)
        book = Workbook()
        book.active.append(HEADERS)
        book.active.append(values)
        book.save(examples / "testmeldungen.xlsx")
        book.close()
    assert read_participants(ods)[0].weight_grams == 25300
    varied = demo(40)
    varied_ods = examples / "testmeldungen-40-kinder.ods"
    write_ods(varied_ods)
    doc = load(str(varied_ods))
    table = doc.spreadsheet.getElementsByType(Table)[0]
    book = Workbook()
    book.active.append(HEADERS)
    for child in varied.participants:
        values = [child.first_name, child.last_name, child.club, child.birth_year,
                  "W" if child.gender == "F" else "J", str(child.weight_grams / 1000).replace(".", ",")]
        row = TableRow()
        for value in values:
            cell = TableCell(valuetype="string")
            cell.addElement(P(text=str(value)))
            row.addElement(cell)
        table.addElement(row)
        book.active.append(values)
    doc.save(str(varied_ods), addsuffix=False)
    varied_xlsx = examples / "testmeldungen-40-kinder.xlsx"
    book.save(varied_xlsx)
    book.close()
    for path in [varied_ods, varied_xlsx]:
        people = read_participants(path)
        assert len(people) == 40
        assert len({p.birth_year for p in people}) >= 10
    state = demo(10)
    state.configure("Stadtmeisterschaft · Testveranstaltung", "2026-11-18",
                    [AgeClass("U11", [2016, 2017, 2018], True), AgeClass("U13", [2014, 2015, 2016])])
    state.participants[3].first_name = "Anika"
    state.participants[3].last_name = "Müller"
    state.participants[4].first_name = "Betina"
    state.participants[4].last_name = "Dopfer"
    state.participants[5].first_name = "Alexandra-Maria"
    state.participants[5].last_name = "Müller-Lüdenscheidt"
    state.save_pool(state.pools[1].id, "U11 · Gruppe A", {
        "1": FightResult("1:0", 10, 5), "4": FightResult("0:1", 0, 7),
        "10": FightResult("1:0", 7, 7),
    }, mat="2")
    friend = state.create_pool("friendship", "Zusätzliche Begegnungen")
    for person in state.participants[:2]:
        state.move(person.id, friend)
    state.save_pool(friend, "Zusätzliche Begegnungen", {"1": FightResult("0:1", 5, 10)}, mat="Halle A")
    write_pdf(examples / "poollisten-beispiel.pdf", state, state.pools)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setResolution(1200)
    printer.setOutputFileName(str(root / "tmp" / "druck-1200dpi.pdf"))
    configure_page(printer)
    paint_document(printer, state, [state.pools[1]])
    with TemporaryDirectory(dir=root / "tmp") as directory:
        window = demo_window(Path(directory), 10)

        def prepare(candidate):
            candidate.configure(state.name, state.event_date, state.age_classes)
            for target, source in zip(candidate.participants, state.participants):
                target.first_name, target.last_name = source.first_name, source.last_name
            candidate.save_pool("Pool 02", "U11 · Gruppe A", state.pools[1].results, mat="2")
            friend_id = candidate.create_pool("friendship", "Zusätzliche Begegnungen")
            for person in candidate.participants[:2]:
                candidate.move(person.id, friend_id)
            candidate.save_pool(friend_id, "Zusätzliche Begegnungen", state.pool(friend).results, mat="Halle A")

        window.change(prepare, "Prüfdaten gespeichert.")
        window.show()
        app.processEvents()
        window.grab().save(str(examples / "oberflaeche.png"))
        page = PoolPage(window, "Pool 02")
        page.show()
        app.processEvents()
        page.grab().save(str(examples / "poolseite.png"))
        page.close()
        config = TournamentConfig(window)
        config.show()
        app.processEvents()
        config.grab().save(str(examples / "wettkampf-konfiguration.png"))
        config.close()
        friend_page = PoolPage(window, friend)
        friend_page.show()
        app.processEvents()
        friend_page.grab().save(str(examples / "freundschaftspool.png"))
        friend_page.close()
        window.scroll.verticalScrollBar().setValue(window.scroll.verticalScrollBar().maximum())
        app.processEvents()
        window.grab().save(str(examples / "freundschaft-uebersicht.png"))
        def bookmarks(candidate):
            candidate.pool("Pool 02").bookmark = "Trainer wegen der Besetzung fragen."
            candidate.participant(candidate.pool("Pool 02").members[0]).bookmark = "Startgebühr noch offen.\nVor dem ersten Kampf am Eingang klären."
        def capture_menu():
            menu = QApplication.activePopupWidget()
            if isinstance(menu, QMenu):
                menu.grab().save(str(examples / "lesezeichen-kontextmenue.png"))
                menu.close()
        QTimer.singleShot(0, capture_menu)
        window.headers[friend].customContextMenuRequested.emit(window.headers[friend].rect().center())
        window.change(bookmarks, "Lesezeichen gespeichert.")
        window.scroll.verticalScrollBar().setValue(0)
        window.bookmarks_only.setChecked(True)
        app.processEvents()
        window.grab().save(str(examples / "lesezeichen-uebersicht.png"))
        bookmarked_page = PoolPage(window, "Pool 02")
        bookmarked_page.show()
        app.processEvents()
        bookmarked_page.grab().save(str(examples / "lesezeichen-poolseite.png"))
        note = BookmarkDialog(window, "participant", window.state.pool("Pool 02").members[0], bookmarked_page)
        note.show()
        app.processEvents()
        note.grab().save(str(examples / "lesezeichen-notiz.png"))
        note.reject()
        bookmarked_page.close()
        # Eine ungestartete Gruppe für die zusätzliche Ansicht vorbereiten.
        window.change(lambda candidate: candidate.configure(candidate.name, candidate.event_date,
                      [AgeClass("Testklasse", list(range(2000, 2030)), True)]), "Prüfklasse")
        search_id = window.create_pool("friendship")
        window.move(window.state.pool("Pool 02").members[1], search_id)
        search = FriendshipSearch(window, search_id)
        search.show()
        app.processEvents()
        search.grab().save(str(examples / "lesezeichen-partnersuche.png"))
        search.reject()
        import_doc = OpenDocumentSpreadsheet()
        import_table = Table(name="Meldungen")
        import_doc.spreadsheet.addElement(import_table)
        editable = window.state.participant(window.state.pool("Pool 03").members[0])
        locked = window.state.participant(window.state.pool("Pool 02").members[0])
        import_rows = [HEADERS] + [
            [person.first_name, person.last_name, person.club, person.birth_year, person.gender,
             str((person.weight_grams + 800) / 1000)] for person in [editable, locked]]
        for values in import_rows:
            row = TableRow()
            for value in values:
                cell = TableCell(valuetype="string")
                cell.addElement(P(text=str(value)))
                row.addElement(cell)
            import_table.addElement(row)
        import_path = Path(directory) / "meldung-gewichte.ods"
        import_doc.save(str(import_path), addsuffix=False)
        merge = ImportMerge(window, window.session.prepare_import(import_path))
        merge.show()
        app.processEvents()
        merge.grab().save(str(examples / "import-gewichtsabgleich.png"))
        merge.reject()
        window.close()
        varied_window = demo_window(Path(directory) / "vierzig", 40)
        varied_window.show()
        app.processEvents()
        varied_window.grab().save(str(examples / "oberflaeche-40.png"))
        suggestions = TournamentConfig(varied_window)
        suggestions.event_date.setDate(QDate(2026, 11, 18))
        suggestions.suggest_classes()
        suggestions.show()
        app.processEvents()
        suggestions.grab().save(str(examples / "altersklassen-vorschlag.png"))
        suggestions.reject()
        varied_window.change(lambda s: s.configure(s.name, s.event_date, suggested_classes(2026)), "Klassen")
        varied_window.change(lambda s: s.recreate_regular_pools(), "Automatisch eingeteilt")
        varied_window.scroll.verticalScrollBar().setValue(0)
        app.processEvents()
        varied_window.grab().save(str(examples / "automatische-einteilung.png"))
        write_pdf(examples / "automatische-poollisten.pdf", varied_window.state, varied_window.state.sorted_pools())
        planned_page = PoolPage(varied_window, next(p.id for p in varied_window.state.pools if len(p.members) > 1))
        planned_page.show()
        app.processEvents()
        planned_page.grab().save(str(examples / "automatische-poolseite.png"))
        planned_page.close()
        target = varied_window.state.sorted_pools()[0].id
        unassigned = next(p.id for p in varied_window.state.participants
                          if varied_window.state.participant_planning_note(p.id))
        varied_window.move(unassigned, target)
        app.processEvents()
        varied_window.grab().save(str(examples / "regelhinweis-kind.png"))
        warning_page = PoolPage(varied_window, target)
        warning_page.show()
        app.processEvents()
        warning_page.grab().save(str(examples / "regelhinweis-poolseite.png"))
        warning_page.close()
        pair_window = demo_window(Path(directory) / "wertung", 10)
        def completed_pair(candidate):
            candidate.configure(candidate.name, candidate.event_date, [AgeClass("Testklasse", list(range(2000, 2030)), True)])
            candidate.save_pool("Pool 03", "Zweierpool", {
                "1": FightResult("1:0", 10, 7), "2": FightResult("1:0", 5, 5)})
            candidate.complete_pool("Pool 03")
        pair_window.change(completed_pair, "Abgeschlossen")
        scored_page = PoolPage(pair_window, "Pool 03")
        scored_page.show()
        app.processEvents()
        scored_page.grab().save(str(examples / "wertung-abgeschlossen.png"))
        write_pdf(examples / "wertung-abgeschlossen.pdf", pair_window.state, [pair_window.state.pool("Pool 03")])
        for combo, value in zip(scored_page.editors[1], ["0:1", 5, 10]):
            combo.setCurrentIndex(combo.findData(value))
        scored_page.save()
        app.processEvents()
        scored_page.grab().save(str(examples / "wertung-wieder-offen.png"))
        write_pdf(examples / "wertung-wieder-offen.pdf", pair_window.state, [pair_window.state.pool("Pool 03")])
        scored_page.close()
        def completed_five(candidate):
            pool = candidate.pool("Pool 02")
            candidate.save_pool(pool.id, "Fünferpool", {
                str(number): FightResult("1:0", 10, 5) for number in range(1, len(pool.fight_order) + 1)})
            candidate.complete_pool(pool.id)
        pair_window.change(completed_five, "Fünferpool abgeschlossen")
        write_pdf(examples / "wertung-fuenferpool.pdf", pair_window.state, [pair_window.state.pool("Pool 02")])
        pair_window.close()
        varied_window.close()
        status_window = demo_window(Path(directory) / "status", 10)
        def prepare_status(candidate):
            pool = candidate.pool("Pool 02")
            candidate.save_pool(pool.id, "Rückzug und Disqualifikation", {
                "1": FightResult("0:1", 7, 10, "injury"),
                "2": FightResult("1:0", 10, 0, "nonattendance"),
            })
            candidate.set_participant_status(pool.members[0], "withdrawn")
            candidate.set_participant_status(pool.members[2], "disqualified")
            candidate.set_participant_status(pool.members[3], "disqualified")
        status_window.change(prepare_status, "Endgültige Status gespeichert.")
        status_window.show()
        app.processEvents()
        status_window.grab().save(str(examples / "teilnehmerstatus-uebersicht.png"))
        status_page = PoolPage(status_window, "Pool 02")
        status_page.show()
        app.processEvents()
        status_page.grab().save(str(examples / "teilnehmerstatus-poolseite.png"))
        status_pool = status_window.state.pool("Pool 02")
        write_pdf(examples / "teilnehmerstatus.pdf", status_window.state, [status_pool])
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QImage, QPainter
        from stadtmeisterschaft.output import draw_pool
        status_image = QImage(1650, 1110, QImage.Format.Format_ARGB32)
        status_image.fill(Qt.GlobalColor.white)
        status_painter = QPainter(status_image)
        try:
            draw_pool(status_painter, QRectF(0, 0, 1650, 1110), status_window.state, status_pool)
        finally:
            status_painter.end()
        status_image.save(str(examples / "teilnehmerstatus-druck.png"))
        status_page.close()
        status_window.close()
        large = demo_window(Path(directory) / "hundert", 100)
        large.show()
        app.processEvents()
        large.grab().save(str(examples / "oberflaeche-100.png"))
        large.close()
        compact = demo_window(Path(directory) / "kompaktes-raster", 40)
        def compact_pools(candidate):
            classes = suggested_classes(2026)
            for age_class in classes:
                age_class.mixed = True
            candidate.configure(candidate.name, candidate.event_date, classes)
            candidate.pools = []
            offset = 0
            for index, size in enumerate([2, 3, 4, 5, 1, 5, 5, 5, 5, 5]):
                pool = candidate.pool(candidate.create_pool())
                pool.age_class = classes[index // 2].name
                pool.members = [p.id for p in candidate.participants[offset:offset + size]]
                for number, pid in enumerate(pool.members):
                    person = candidate.participant(pid)
                    person.birth_year = max(classes[index // 2].years)
                    person.weight_grams = 20000 + index * 3000 + number * 300
                offset += size
            candidate.participants[0].last_name = "von Bergmann-Langenfeld"
            candidate.participants[0].bookmark = "Vor dem ersten Kampf melden."
            first = candidate.pool(candidate.create_pool("friendship", "Zusätzliche Begegnung"))
            first.members = list(candidate.pools[0].members)
            second = candidate.pool(candidate.create_pool("friendship", "Partner für Einzelpool"))
            second.members = [candidate.pools[4].members[0], candidate.pools[5].members[0]]
            candidate.create_pool("friendship", "Noch zu besetzen")
        compact.change(compact_pools, "Prüfmuster: kompakte Pools und getrennte Freundschaftskämpfe")
        compact.resize(1900, 1200)
        compact.show()
        for _ in range(15):
            app.processEvents()
        hovered = compact.lists[compact.state.pools[0].id]
        point = hovered.visualItemRect(hovered.item(0)).center()
        app.sendEvent(hovered.viewport(), QHelpEvent(QEvent.Type.ToolTip, point,
                                                    hovered.viewport().mapToGlobal(point)))
        app.processEvents()
        compact.grab().save(str(examples / "planung-kompakt-breit.png"))
        compact.scroll.ensureWidgetVisible(compact.section_widgets["friendship"])
        app.processEvents()
        compact.grab().save(str(examples / "planung-kompakt-freundschaft.png"))
        compact.resize(1050, 900)
        compact.scroll.verticalScrollBar().setValue(0)
        for _ in range(15):
            app.processEvents()
        compact.grab().save(str(examples / "planung-kompakt-schmal.png"))
        compact.move(compact.state.pools[9].members[-1], "")
        compact.resize(1500, 1000)
        for _ in range(15):
            app.processEvents()
        compact.grab().save(str(examples / "planung-kompakt-ohne-pool.png"))
        compact.close()
        search_window = demo_window(Path(directory) / "freundschaftssuche", 10)
        def prepare_search(candidate):
            candidate.participants = candidate.participants[:6]
            for person, name, year, weight in zip(candidate.participants,
                    ["Alex", "Ben", "Mia", "Leon", "Tom", "Finn"],
                    [2017, 2015, 2017, 2017, 2015, 2013],
                    [30000, 30500, 33200, 33500, 35000, 30100]):
                person.first_name, person.last_name = name, "Beispiel"
                person.birth_year, person.weight_grams = year, weight
                person.gender = "F" if name == "Mia" else "M"
            candidate.pools = []
            candidate.configure(candidate.name, candidate.event_date, [AgeClass("U11", [2017, 2018], True),
                AgeClass("U13", [2015, 2016]), AgeClass("U15", [2013, 2014])])
            source = candidate.pool(candidate.create_pool())
            source.members, source.age_class = [candidate.participants[0].id], "U11"
            existing = candidate.pool(candidate.create_pool("friendship", "Bereits geplante Freundschaft"))
            existing.members = [candidate.participants[1].id, candidate.participants[3].id]
        search_window.change(prepare_search, "Prüfdaten Freundschaftssuche")
        source = search_window.state.pools[0].id
        single_page = PoolPage(search_window, source)
        single_page.show()
        app.processEvents()
        single_page.grab().save(str(examples / "freundschaftssuche-einstieg.png"))
        single_page.close()
        search = FriendshipSearch(search_window, source, parent=single_page)
        search.show()
        app.processEvents()
        search.grab().save(str(examples / "freundschaftssuche.png"))
        search.add_partner(search_window.state.participants[1].id)
        search.add_partner(search_window.state.participants[2].id)
        app.processEvents()
        search.grab().save(str(examples / "freundschaftssuche-gruppe.png"))
        search.warnings.toggle.click()
        app.processEvents()
        search.grab().save(str(examples / "freundschaftssuche-details.png"))
        search.reject()
        organized = []
        search_window.change(lambda candidate: organized.append(candidate.add_friendship_partners(
            source, [candidate.participants[1].id])), "Freundschaftskampf organisiert")
        search_window.show()
        app.processEvents()
        search_window.grab().save(str(examples / "planung-freundschaftsverweis.png"))
        search_window.pool_filter.setCurrentIndex(search_window.pool_filter.findData("friendship"))
        app.processEvents()
        search_window.grab().save(str(examples / "planung-filter-freundschaft.png"))
        search_window.pool_filter.setCurrentIndex(search_window.pool_filter.findData("single"))
        app.processEvents()
        search_window.grab().save(str(examples / "planung-filter-einzelpools.png"))
        organized_page = PoolPage(search_window, source)
        organized_page.show()
        app.processEvents()
        organized_page.grab().save(str(examples / "planung-einzelpool-organisiert.png"))
        organized_page.close()
        ages_page = PoolPage(search_window, organized[0])
        ages_page.show()
        ages_page.warnings.toggle.click()
        app.processEvents()
        ages_page.grab().save(str(examples / "planung-altersklassen.png"))
        ages_page.close()
        search_window.close()
        sidebar_examples(app, Path(directory) / "orga-notizen", examples)
    print(f"Prüfmuster erzeugt: {examples}")


if __name__ == "__main__":
    main()
