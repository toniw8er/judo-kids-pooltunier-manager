"""Start der lokalen Windows-Anwendung."""
import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .ui.main_window import Window


def main():
    parser = argparse.ArgumentParser(description="PoolturnierManager – Pools und Ergebnisse")
    parser.add_argument("--folder", type=Path, default=Path.home() / "Documents" / "Stadtmeisterschaft")
    parser.add_argument("--smoke-test", type=Path, help="Paketprüfung in einem neuen Arbeitsordner ausführen")
    args = parser.parse_args()
    if args.smoke_test and args.folder.exists():
        parser.error("Die Paketprüfung benötigt einen neuen, noch nicht vorhandenen Arbeitsordner.")
    app = QApplication(sys.argv[:1])
    try:
        window = Window(args.folder)
        if args.smoke_test:
            from .smoke import check_package
            try:
                check_package(window, args.smoke_test)
            finally:
                window.close()
            return 0
        window.show()
        return app.exec()
    except Exception as exc:
        if args.smoke_test:
            raise
        QMessageBox.critical(None, "PoolturnierManager konnte nicht starten", str(exc))
        return 1
