# Projektarbeit

Python 3.14, uv, unittest, PySide6, SQLite und OR-Tools. Abhängigkeiten über
`pyproject.toml` und `uv.lock` verwalten; kein pip-Workflow. Fachliche Vorgaben
stehen in `docs/fachregeln.md`, technische Abläufe in `docs/entwicklung.md`.

## Effizient arbeiten

- Vor Änderungen relevante Implementierung, Aufrufer und vorhandene Tests lesen.
  Nicht bei jeder Teilaufgabe das gesamte Repository erneut analysieren.
- Mit `rg` gezielt in `src`, `tests`, `devtools`, `scripts` und `docs` suchen.
  `.git`, `.venv`, `.tools`, `.uv-cache`, `build`, `dist`, `tmp`, `.dev-data`
  und `local-data` bei Quellcodesuchen ausschließen.
- Unabhängige Lesevorgänge bündeln und Ausgaben auf relevante Stellen begrenzen.
  Keine vollständigen Erfolgsprotokolle oder wiederholten Dateiinhalte ausgeben.
- Zusätzliche Review-Agenten nur bei ausdrücklichem Auftrag oder nach den
  anwendbaren Vorgaben einsetzen. Keine routinemäßigen Review-Schleifen.
- Etablierte Bibliotheken nutzen; keine neue Testinfrastruktur einführen, wenn
  die vorhandene unittest-Auswahl genügt.

## Prüfungen auswählen

Vor der Umsetzung kurz Änderungsbereich, betroffene Verbraucher und geplante
Prüfungen nennen. Maßgeblich sind Wirkung und Fehlerrisiko, nicht Zeilenzahl oder
Dateiname. Entscheidungsmatrix und Testzuordnung: `docs/entwicklung.md`, Prüfen.

1. **Prosa, Kommentare, reine Formatierung:** Diff und passende Referenzen bzw.
   Formatierung prüfen; keine Anwendungstests. Ausführbare Beispiele, Direktiven,
   Imports und fachlich wirksame Texte sind keine bloße Prosaänderung.
2. **Lokales Verhalten:** Relevante Testdatei oder ausreichend abdeckende
   Klassen/Methoden prüfen. Bei Fehlerkorrekturen vorhandenen Regressionstest
   nutzen oder einen passenden ergänzen. Keine Tests, die nur Code nachbilden.
3. **Verbundene Komponenten:** Fach-, Integrations- und Bedienfälle der
   betroffenen Komponenten und Verbraucher zusammen auswählen. Gemeinsame
   Berechnungen für Oberfläche und Druck auf beiden Wegen berücksichtigen.
4. **Querschnittliche Änderungen:** Vollständige Suite bei zentralen Verträgen,
   Datenformaten/Migrationen, Speicher-/Übernahmeverhalten, breiten Refactorings
   oder globalen Laufzeitabhängigkeiten. Ein lokaler Helfer in einer zentralen
   Datei erfordert nicht automatisch alles; den begrenzten Wirkungsbereich belegen.

Wenn nach gezielter Analyse der Wirkungsbereich unklar bleibt, vollständig prüfen.
Bei neuen Fehlern, zusätzlichen Verbrauchern oder fehlender Abdeckung ausweiten.

## Befehle und zusätzliche Prüfungen

- Einrichtung: `uv sync --locked --group dev`; lokaler Ersatz für `uv`:
  `.\.tools\uv\uv.exe`. Die dev-Gruppe ist bewusst nicht standardmäßig aktiv.
- Gesamt: `uv run --locked python -m unittest discover -s tests`.
- Datei, Beispiel: `uv run --locked python -m unittest discover -s tests -p "test_scoring.py"`.
- Innerhalb einer Datei kann `-k` weiter filtern. Auswahl auf ausreichende
  Abdeckung prüfen. Null Tests sind kein Erfolg; übersprungene Tests offen nennen.
  `-k` verhindert nicht alle Modulimporte. Ohne Diagnosebedarf kein `-v`.
- Ruff auf geänderten Python-Dateien:
  `uv run --locked --group dev ruff check <Dateien>` (Regeln E9 und F).
  Bei Änderungen an Ruff-Konfiguration/-Version alle Quellpfade prüfen:
  `uv run --locked --group dev ruff check src devtools tests scripts`.
- Ruff-Formatierung ist separat und freiwillig, bis eine eigene Umstellung
  vereinbart wurde. `uv run --locked --group dev ruff format --check <Dateien>`
  prüft ohne Änderungen.
  Keine projektweite Umformatierung im Rahmen anderer Aufgaben.
- Bei geändertem UI-/Drucklayout oder sichtbaren Ausgabeinhalten relevante
  Prüfmuster erzeugen und tatsächlich ansehen. `devtools.verify_visuals` ist
  kein automatischer Bildvergleich. PDF-Erzeugung allein belegt keine korrekten
  gedruckten Wertungen; passende Inhaltsprüfung oder Sichtprüfung vorsehen.
- Build nur bei Paketierungs-/DLL-/Einstiegspunktänderungen, relevanten
  Laufzeitabhängigkeiten oder angeforderter Paketlieferung. Danach neu gebaute
  EXE separat gemäß `docs/entwicklung.md` prüfen. Build-Erfolg genügt nicht.

## Wiederholungen und Ergebnis

- Erfolgreiche Prüfungen gelten weiter, solange relevanter Code, Testeingaben,
  Abhängigkeiten und Umgebung unverändert sind. Nach relevanten Folgeänderungen
  die betroffenen Prüfungen erneut ausführen; reine Prosa entwertet sie nicht.
- Wenn eine Gesamtprüfung ohnehin folgt, erfolgreiche Teilprüfungen nicht davor
  nochmals unverändert ausführen. Keine abschließende Gesamtprüfung aus Gewohnheit.
- Fehlgeschlagene Prüfungen untersuchen; unveränderte Wiederholungen sind keine
  Reparatur. Umgebungsfehler von Anwendungsfehlern unterscheiden.
- Abschluss kurz: Änderung, ausgeführte Befehle mit Ergebnis und Testanzahl,
  relevante ausgelassene Prüfungen mit Begründung und verbleibende Unsicherheiten.
  Geplante, gestartete, übersprungene und erfolgreiche Prüfungen unterscheiden.
