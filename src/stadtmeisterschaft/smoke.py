"""Prüft die tatsächlich gebündelten Datei- und Oberflächenfunktionen."""
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from .domain import AgeClass, FightResult, Participant
from .output import write_pdf
from .sheets import HEADERS, read_participants, write_ods
from .storage import Store
from .scoring import evaluate_pool


def check_package(window, report: Path):
    assert not window.state.participants and not window.state.pools and not window.state.is_demo
    window.show()
    QApplication.processEvents()

    def prepare(state):
        state.is_demo = True
        state.configure("Paketprüfung", "2026-11-18", [AgeClass("U11", [2016], True)])
        state.add_participants([
            Participant("smoke-1", "Jörg", "Müller", "JC Test", 2016, "M", 25300),
            Participant("smoke-2", "Mia", "Weiß", "JC Test", 2016, "F", 25500),
        ])
        state.recreate_regular_pools()
        assert len(state.pools) == 1 and state.pools[0].age_class == "U11"
        pool = state.pools[0].id
        results = {"1": FightResult("1:0", 10, 7), "2": FightResult("1:0", 10, 0)}
        state.save_pool(pool, "Prüfpool", results)
        state.complete_pool(pool)
        results["2"] = FightResult("0:1", 0, 10)
        state.save_pool(pool, "Prüfpool", results)
        assert state.pool(pool).reopened and not state.pool(pool).completed
        results["3"] = FightResult("0:0", 5, 5)
        state.save_pool(pool, "Prüfpool", results)
        state.complete_pool(pool)
        assert [r.place for r in evaluate_pool(state.pool(pool))[0]] == [2, 1]
        friend = state.create_pool("friendship")
        for person in state.participants:
            state.move(person.id, friend)

    assert window.change(prepare, "Paketprüfung")
    folder = window.folder
    loaded = Store(folder).load()
    assert loaded.to_dict() == window.state.to_dict()
    write_pdf(folder / "smoke.pdf", loaded, loaded.pools)
    write_ods(folder / "smoke-export.ods", loaded.participants)
    write_ods(folder / "smoke-template.ods")
    book = Workbook()
    book.active.append(HEADERS)
    book.active.append(["Jörg", "Müller", "JC Test", 2016, "M", "25,3"])
    book.save(folder / "smoke.xlsx")
    book.close()
    assert read_participants(folder / "smoke.xlsx")[0].weight_grams == 25300
    # Der vollständige ODS-Import wird zusätzlich mit einer Meldeliste geprüft.
    from odf.opendocument import load
    from odf.table import Table, TableCell, TableRow
    from odf.text import P
    doc = load(str(folder / "smoke-template.ods"))
    row = TableRow()
    for value in ["Mia", "Weiß", "JC Test", 2016, "W", "25,5"]:
        cell = TableCell(valuetype="string")
        cell.addElement(P(text=str(value)))
        row.addElement(cell)
    doc.spreadsheet.getElementsByType(Table)[0].addElement(row)
    doc.save(str(folder / "smoke-import.ods"), addsuffix=False)
    assert read_participants(folder / "smoke-import.ods")[0].weight_grams == 25500
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        "empty_start": True, "participants": len(loaded.participants),
        "pools": len(loaded.pools), "saved_result": loaded.pools[0].results["1"].outcome,
        "pdf_bytes": (folder / "smoke.pdf").stat().st_size,
        "ods_imported": 1, "xlsx_imported": 1, "automatic_pool_planning": True,
        "pool_completion_and_correction": True,
        "frozen": bool(getattr(sys, "frozen", False)),
    }, indent=2), encoding="utf-8")
