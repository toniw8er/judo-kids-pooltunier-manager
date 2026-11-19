"""Entwicklungsszenario vorbereiten und dieselbe App starten."""
import argparse
from datetime import datetime
from pathlib import Path

from stadtmeisterschaft.storage import Store

from .demo_data import demo


ROOT = Path(__file__).resolve().parents[1]


def prepare_demo(count=40, event_year=2026, fresh=False, base=None):
    base = Path(base) if base is not None else ROOT / ".dev-data"
    base.mkdir(parents=True, exist_ok=True)
    pointer = base / f"aktuell-{count}-{event_year}.txt"
    folder = base / f"kinder-{count}-{event_year}"
    if not fresh and pointer.exists():
        name = pointer.read_text(encoding="utf-8").strip()
        if not name or Path(name).name != name or name in (".", ".."):
            raise ValueError("Ungültiger Entwicklungspfad.")
        folder = base / name
    if fresh:
        folder = base / f"kinder-{count}-{event_year}-{datetime.now():%Y%m%d-%H%M%S-%f}"
    if folder.exists():
        store = Store(folder)
        state = store.load()
        if state is None or not state.is_demo:
            raise ValueError("Der Entwicklungsordner enthält keinen gekennzeichneten Demo-Wettkampf.")
    else:
        folder.mkdir()
        Store(folder).save(demo(count, event_year))
    pointer.write_text(folder.name, encoding="utf-8")
    return folder.resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, choices=(10, 40, 100), default=40)
    parser.add_argument("--year", type=int, choices=range(1917, 2100), default=2026, metavar="JAHR")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    folder = prepare_demo(args.count, args.year, args.fresh)
    print(f"Entwicklungsdaten: {folder}")
    from stadtmeisterschaft.ui.main_window import Window
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    window = Window(folder)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
