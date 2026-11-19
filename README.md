# PoolturnierManager

Lokale Windows-App für die Organisation eines Judo-Kinderturniers. Wir entwickeln direkt an der Anwendung. Git enthält frühere Stände, Experimente und abgeschlossene Reviews.

Die App kann Meldelisten importieren, reguläre Pools automatisch einteilen, reguläre und Freundschaftspools manuell verwalten, Ergebnisse auswerten, Pools abschließen und Poollisten drucken. Details und offene Fachfragen stehen im [Backlog](docs/backlog.md).

Nach Import und Altersklassenkonfiguration startet „Reguläre Pools neu erstellen“ die bewusste Neuverteilung. Ungestartete reguläre Pools werden ersetzt; gestartete Pools und Freundschaftspools bleiben erhalten. Kinder ohne passende Altersklasse bleiben als Klärfälle sichtbar, Kinder ohne passenden Partner erhalten markierte Einzelpools.

Die Poolseite und Ausdrucke berechnen Punkte, Siege, UB-Summen und Platzierungen aus den gespeicherten Ergebnissen. Fehlende Pflichtkämpfe verhindern einen Abschluss. Wird durch Korrektur ein weiterer Kampf verpflichtend, öffnet sich ein abgeschlossener Pool wieder; seine Besetzung bleibt gesperrt. Nach Ergänzung erneut bewusst abschließen.

## Starten

Python 3.14 und Abhängigkeiten werden mit **uv** verwaltet. Kein pip-Workflow, keine requirements.txt, keine manuelle Aktivierung der Umgebung.

```powershell
.\Start-App.ps1
# Einen bestimmten Wettkampf öffnen oder neu anlegen:
.\Start-App.ps1 --folder C:\Turniere\Stadtmeisterschaft-2026
```

Neue Wettkämpfe starten leer. Ohne Ordnerangabe verwendet die App `Documents\Stadtmeisterschaft` im Benutzerverzeichnis. Ein Arbeitsordner entspricht einem Wettkampf. Änderungen werden nach erfolgreicher Prüfung automatisch gespeichert.

## Mit Testkindern entwickeln

```powershell
.\Start-Entwicklung.ps1                 # 40 Kinder, bisherigen Entwicklungsstand öffnen
.\Start-Entwicklung.ps1 -Kinder 10      # Kleines Szenario mit Zweier-, Dreier- und Fünferpool
.\Start-Entwicklung.ps1 -Kinder 100     # Größere Übersicht
.\Start-Entwicklung.ps1 -Kinder 40 -Neu # Frischer Stand; vorheriger Ordner bleibt erhalten
```

Die Testkinder bleiben dauerhaft als reproduzierbare Szenarien verfügbar. Entwicklungsstände liegen unter `.dev-data/`, getrennt von echten Wettkämpfen. Standardjahr ist 2026; `-Jahr 2027` erzeugt ein separates Szenario. Fenster und Ausdrucke kennzeichnen Entwicklungsdaten.

## Prüfen und bauen

Prüfungen nach Änderungsrisiko auswählen; nicht alle Befehle bei jeder Änderung
ausführen. Die [Entscheidungsmatrix](docs/entwicklung.md#prüfen) nennt Testauswahl,
visuelle Prüfungen und Paketprüfung. Für KI-Aufträge gilt [AGENTS.md](AGENTS.md).

```powershell
uv sync --locked --group dev
# Bei Einrichtung oder Ruff-Änderungen; sonst nur betroffene Python-Dateien
uv run --locked --group dev ruff check src devtools tests scripts
# Beispiel: nur Wertung und zugehörige Bedienfälle
uv run --locked python -m unittest discover -s tests -p "test_scoring.py"
# Vollständige Suite bei querschnittlichen Änderungen
uv run --locked python -m unittest discover -s tests
```

Ruff prüft mit den Fehlerregeln `E9` und `F`; die Formatprüfung ist vorerst separat
und freiwillig. Die dev-Gruppe wird nur ausdrücklich zugeschaltet und gehört
nicht zu den Laufzeitabhängigkeiten.

Falls uv nicht im PATH liegt, funktioniert hier auch `.\.tools\uv\uv.exe`. Die PowerShell-Skripte finden diese lokale Installation automatisch. Ein Windows-Paket wird bei Bedarf mit `.\Build-App.ps1` gebaut und separat geprüft; siehe [Windows-Build](docs/entwicklung.md#windows-build). Es liegt unter `dist\PoolturnierManager\PoolturnierManager.exe`. Für die Weitergabe den **gesamten Ordner `PoolturnierManager`** einschließlich `_internal` kopieren. Für den Desktop eine Verknüpfung zur EXE erstellen; die EXE im Paketordner belassen. Laufende EXE nach Codeänderungen schließen und für die Weitergabe neu bauen.

## Projektdokumentation

- [Fachregeln](docs/fachregeln.md): Anforderungen, Regeln und verbindliche Beispiele.
- [Entwicklung](docs/entwicklung.md): Aufbau, Datenhaltung, Testdaten und Build.
- [Backlog](docs/backlog.md): fehlende Funktionen, offene Entscheidungen und Reihenfolge.
- [Fachliche Referenzen](docs/referenzen/): bisherige Recherchen mit Quellen und Grenzen.

Gespeicherte Wettkämpfe und Entwicklungsstände gehören nicht in Git. Vorhandene Datenbanken aus entfernten Build- und Versuchsordnern liegen lokal unter `local-data/uebernommen/`; die dortige Zuordnung nennt die ursprünglichen Pfade.
