# Entwicklung

## Technische Grundlage

Die bestehende Anwendung wird weiterentwickelt: Python 3.14, uv, PySide6/Qt Widgets, SQLite, odfpy für ODS, openpyxl für XLSX, Google OR-Tools CP-SAT für die Pooleinteilung und PyInstaller für das Windows-Paket. `pyproject.toml`, `uv.lock` und `.python-version` bestimmen die Umgebung. Setuptools baut das lokale Python-Paket aus `src/`; das Entwicklungswerkzeug `devtools` gehört nicht zum verteilten Anwendungspaket.

```powershell
uv sync --locked --group build
uv run --locked python -m stadtmeisterschaft --folder C:\Turniere\Test
```

Auf diesem Rechner ist uv auch unter `.tools\uv\uv.exe` verfügbar. Die Start-/Buildskripte nutzen diesen Ersatz und einen projektlokalen Cache samt TEMP. Das vermeidet Probleme mit umgeleiteten Windows-Temppfaden beim Paketbau. Die erste Einrichtung kann Internet brauchen, eine eingerichtete Anwendung läuft offline. Kein pip-Workflow und keine requirements.txt.

## Aufbau

| Bereich | Aufgabe |
|---|---|
| `src/stadtmeisterschaft/domain.py` | Qt-freies Fachmodell, Kampffolgen, Regeln, Zuordnungen, Ergebnisse, Sperren und Datenformat |
| `application.py` | Fachaktion auf einer Kopie ausführen, prüfen/speichern, erst dann übernehmen |
| `friendship.py` | Konfiguration, Altersbasis, exakte paarweise Rangwerte und Hinweise für die vollständige Freundschaftsgruppe |
| `pool_planning.py` | Turnierregeln als OR-Tools-Modell, vier nacheinander optimierte Ziele und feste Solverparameter |
| `scoring.py` | Gemeinsame Summen, Gegnermatrix und Platzierungen für Oberfläche und Druck |
| `storage.py` | SQLite-Snapshot mit Transaktion und Revisionsprüfung |
| `sheets.py` | ODS/XLSX einlesen, normalisieren, Vorlage und ODS-Export schreiben |
| `output.py` | Gemeinsame Zeichenroutine für PDF und Druck |
| `age_class_defaults.py` | Bearbeitbare BJV-Jahrgangsvorschläge |
| `ui/` | Übersicht, Poolseite, Konfiguration und Qt-Ereignisse |
| `cli.py`, `__main__.py` | App-Start und bewusste Paketprüfung |
| `tests/` | Fach-, Integrations-, Fehler- und Qt-Bedientests |
| `tests/fixtures/` | Versionierte ODS-/XLSX-Meldelisten mit einer bzw. 40 Testpersonen |
| `devtools/` | Zentraler Demo-Generator, Entwicklungsstart und visuelle Prüfmuster |
| `scripts/` | Gemeinsame PowerShell-Umgebung und PyInstaller-Einstieg |

Fachregeln gehören in den Fachbereich. Oberfläche und Druck sollen dieselben Berechnungen verwenden. Qt-Signale und normale Methodenaufrufe reichen für die lokale App; zusätzliche Dienste oder eine Ereignishistorie sind nicht erforderlich. Die vorhandene Kopier-/Speicherfolge bleibt zentral in `TournamentSession`.

## Testkinder und Entwicklungsstände

`devtools/demo_data.py` ist die zentrale Quelle. Die Szenarien behalten die bisherigen Namen, langen Vereine, Gewichtsbereiche, gemischten Jahrgänge und absichtlichen Abweichungen:

- 10 Kinder: Pools mit 3, 5 und 2 Kindern.
- 40 Kinder: sieben Fünferpools und fünf noch ohne regulären Pool.
- 100 Kinder: 19 Fünferpools und fünf noch ohne regulären Pool.

Das sind vorbereitete Testgruppen, keine Ausgabe einer automatischen Einteilung. Für dieselbe Anzahl und dasselbe Veranstaltungsjahr sind IDs, Jahrgänge, Datum und Zuordnungen reproduzierbar. Standardjahr ist ausdrücklich 2026, nicht das zufällige Kalenderjahr des Testlaufs. IDs der Demo sind deterministische UUIDs; echte Importe vergeben weiterhin neue IDs.

```powershell
.\Start-Entwicklung.ps1 -Kinder 40
.\Start-Entwicklung.ps1 -Kinder 40 -Neu
.\Start-Entwicklung.ps1 -Kinder 100 -Jahr 2027
```

Der Entwicklungsstart speichert nach `.dev-data/`. Je Kombination aus Kinderzahl und Jahr merkt eine kleine Zeigerdatei den zuletzt verwendeten Ordner. Ohne `-Neu` werden dortige Änderungen weitergeladen. `-Neu` erstellt einen neuen eindeutig benannten Ordner und erhält den alten. Ein nicht als Demo gekennzeichneter Stand wird nicht als Entwicklungsszenario übernommen. Die normale App öffnet dieselben Daten und dieselbe Oberfläche; sie importiert keinen Demo-Generator.

`is_demo` liegt im gespeicherten Wettkampfstand und steuert die Kennzeichnung in Fenster und Ausdruck. Bei alten Daten wird dieser Wert nicht anhand von Namen geraten. Die vier versionierten Importdateien sind feste Schnittstellen-Prüfmuster und bleiben unabhängig von einer Regeneration erhalten. `devtools.verify_visuals` erzeugt aktuelle Beispiele und Ansichten unter `tmp/visuals/`, ohne die Prüfmuster zu überschreiben.

## Datenhaltung und ältere Stände

`Tournament.create_pool` vergibt die kleinste freie Kennung ab `Pool 01`, gemeinsam für reguläre und Freundschaftspools. Bestehende Kennungen bleiben unverändert. Das alte Feld `next_pool_number` bleibt für Dateikompatibilität als Zähler erhalten, steuert die Vergabe aber nicht mehr; auch ältere Stände mit hohem Zähler nutzen sofort freie Nummern. Das Snapshotformat bleibt unverändert.

Neue Arbeitsordner enthalten `wettkampf.sqlite3`. Ist nur `technikversuch.sqlite3` vorhanden, wird diese Datei direkt weiterverwendet. Sind beide vorhanden, lehnt die App den Ordner als mehrdeutig ab. Keine automatische Umbenennung oder Auswahl eines möglicherweise falschen Stands.

Die SQLite-Tabelle `current_state` enthält eine Zeile mit Revision und JSON-Snapshot. Schreibvorgänge sind transaktional; eine veraltete Revision wird abgelehnt. Der Snapshot hat `schema_version: 6` mit endgültigen Teilnehmerstatus, Ergebnisgrund, gespeichertem Wiederöffnungsgrund sowie optionaler Matte und Papierstand je Pool sowie internen Lesezeichen an Teilnehmern und Pools. Version 0/1 wird beim Laden normalisiert: Startklasse leer lassen, keine Klasse aus Jahrgängen erraten, alte einzelne Testergebnisse übernehmen. Version 0/1/2 erhält ausdrücklich keinen abgeleiteten Abschlussstatus; vollständige ältere Pools bleiben bis zum bewussten Abschluss offen. Version 0–3 erhält aktive Teilnehmer, ausgetragene Ergebnisse und keinen zusätzlichen Wiederöffnungsgrund; keine Status aus alten Wertungen erraten. Version 0–4 erhält eine leere Matte und Papierstand 1. Version 0–5 erhält keine Lesezeichen. Erst beim nächsten erfolgreichen Speichern Version 6 schreiben. Unbekannte Formatversionen sowie widersprüchliche Statuswertungen werden vor Übernahme abgelehnt. Künftige Formatänderungen brauchen eine ausdrückliche Migration und Prüffälle mit alten Daten.

`Pool.missing_required_fights` und `third_fight_optional` bestimmen die Vollständigkeit zentral. `save_pool` öffnet einen abgeschlossenen Pool wieder, wenn anschließend Pflichtkämpfe fehlen; `started` bleibt gesetzt. `complete_pool` setzt den Abschluss nur für vollständige Pools ab zwei Kindern. Der Hinweis zur Wiederöffnung bleibt bis zum erneuten Abschluss erhalten. `evaluate_pool` verändert den gespeicherten Stand nicht: Summen immer berechnen, Plätze erst bei vollständigen Pflichtkämpfen vergeben. Eine kleine Standardbibliotheksberechnung genügt für maximal fünf Kinder; hierfür ist keine weitere Optimierungsbibliothek nötig. Ergebnisänderungen und ein gewünschter Abschluss werden gemeinsam über `TournamentSession.change` gespeichert.

`set_participant_status` setzt Rückzug oder Disqualifikation endgültig für alle
Teilnahmen. Zwei Wahrheitswerte erhalten auch einen vorherigen Rückzug bei
späterer Disqualifikation; die Disqualifikation hat in Anzeige und Wertung Vorrang.
`_apply_status_results` vergibt fehlende Pflichtwertungen und ersetzt bei
Disqualifikation auch vorhandene Ergebnisse. Gespeicherte Rückzugswertungen
bleiben bei späterem zweitem Rückzug erhalten. Ein leerer optionaler dritter
Zweierpoolkampf bleibt leer. Bei Wertungsänderung durch Statusaktionen einen
abgeschlossenen Pool wieder öffnen und den Grund bis zum erneuten Abschluss
speichern. Automatische Ergebnisse sind nicht manuell korrigierbar; ausgetragene
Ergebnisse und Aufgabe bleiben bei Rückzug bearbeitbar. `FightResult.reason`
unterscheidet auch die beidseitigen Nullwertungen vom normalen Remis.

Oberfläche und Druck verwenden `Tournament.evaluate_pool`, das disqualifizierte
Kinder an die gemeinsame Berechnung übergibt. Diese erhalten keine Platzierung
und beeinflussen die Platznummern der übrigen Kinder nicht. In der Übersicht ein
Kind auswählen und den endgültigen Status festlegen; auf der Poolseite steht
dieselbe Aktion mit Teilnehmerauswahl zur Verfügung. Dort werden aktuelle
Ergebniseingaben und Status in einer Aktion gespeichert. Eine Aufgabe mit dem
Ergebnisgrund „Aufgabe / Verletzung“ und den erreichten UB erfassen; anschließend
über „Rückzug festlegen“ das verletzte Kind wählen und beides gemeinsam speichern.
Einzelnen Nichtantritt über den Ergebnisgrund erfassen, ohne automatisch den
Teilnehmerstatus zu ändern. Vor endgültigen Statusaktionen bestätigt der Bediener
den Geltungsbereich und die Unwiderruflichkeit.

Die Einteilung verwendet den CP-SAT-Solver statt einer eigenen Optimierungssuche. Jeder mögliche Pool wird von seinem leichtesten Kind repräsentiert; kompatible Teilprobleme werden getrennt gelöst. Gemeinsame Klassen erlauben eine äquivalente Intervallaufteilung nach Gewicht. Feste Sortierung, ein Solverworker und Seed 0 gewährleisten reproduzierbare Ergebnisse innerhalb derselben Version. Einzelpoolzahl, Poolzahl und Summe quadrierter Größen werden nacheinander exakt optimiert und festgeschrieben. Die Summe relativer Gewichtsspannen wird zuletzt als Fließkommaziel minimiert (mit Faktor 1.000.000 zur numerischen Skalierung). Nach 15 deterministischen Solverzeiteinheiten je Ziel/Teilproblem ohne Optimalitätsnachweis wird der gesamte Vorgang ohne Änderung abgelehnt. Das ist keine Garantie für beliebig große oder stark überlappende Fälle. 10/40/100-Teststände und ein dichter 100er-Fall werden geprüft.

Der Windows-Build sammelt mit `--collect-binaries ortools` die nativen Solverbibliotheken einschließlich ihrer Abhängigkeiten. Die Paketprüfung führt eine automatische Einteilung tatsächlich aus; ein erfolgreicher Python-Test allein prüft die DLL-Bündelung nicht.

Die Ordnersperre verwendet vorerst weiter `.technikversuch.lock`, damit alte und neue Programmversionen denselben Arbeitsordner nicht gleichzeitig öffnen. Der Name ist eine Kompatibilitätsentscheidung. Sie bedeutet keine fortbestehende Prototypstruktur.

Aktive Wettkämpfe lokal speichern. Keine Datenbankdateien in Git aufnehmen. Für eine einfache Sicherung einer laufenden Datenbank die SQLite-Backupfunktion verwenden.

### Gemeinsame Teilnehmerdatei

Die gemeinsame Bearbeitungsdatei heißt fest `teilnehmer.ods` im Arbeitsordner.
Der erste zusätzliche Meldelistenimport erstellt sie mit allen vorhandenen und
neuen Kindern. Für bereits gefüllte Arbeitsordner erstellt „Teilnehmerdatei neu
einlesen“ die Datei, solange dort noch keine gemeinsame Datei registriert ist.
Eine vorhandene Datei wird dabei geprüft, niemals ungeprüft überschrieben.
ODS-Vorlage und separater Export bleiben eigene Dateien; die Exportaktion darf
die gemeinsame Datei nicht ersetzen.

In OpenOffice bearbeiten, speichern und schließen, anschließend bewusst
„Teilnehmerdatei neu einlesen“ wählen. Die sechs Pflichtspalten bleiben in ihrer
Reihenfolge, gefolgt von `Teilnehmer-ID`. An vierter Stelle darf statt
`Geburtsjahr` genau eine Spalte `Geburtsdatum` stehen; beide zusammen sind
unzulässig. ODS-Datumszellen werden über `office:date-value` gelesen, XLSX über
die von openpyxl gelieferten Datumswerte. Textdaten im deutschen Format oder
ISO-Format werden ebenfalls akzeptiert. Intern wird nur das Jahr übernommen;
Vorlage und Ausgabe verwenden weiter `Geburtsjahr`. Beim Neueinlesen bleibt
die Jahrgangssperre gestarteter Teilnehmer unverändert wirksam. Bestehende IDs erhalten; neue Kinder mit
leerer ID ergänzen. Zusätzliche Meldelisten verwenden weiterhin die sechs
Pflichtspalten ohne IDs. Neueinlesen aktualisiert bekannte IDs und entfernt
fehlende Kinder samt ungestarteten Zuordnungen. Ein gültiges Blatt nur mit
Spaltenüberschriften ist eine bewusste leere Liste; eine fehlende, beschädigte
oder unlesbare Datei ist das nicht. Gestartete reguläre und Freundschaftspools
schützen vor Löschung sowie Änderungen an Jahrgang, Geschlecht und Gewicht.
Namen und Verein bleiben korrigierbar. Keine automatische Neuverteilung.

Eine SQLite-Transaktion allein kann ODS und Datenbank nicht gemeinsam atomar
ersetzen. `Store.save_with_participants` verwendet deshalb eine dauerhafte,
einzelne Übernahmeabsicht, keine Historie:

1. Den vollständigen Kandidaten prüfen und die ODS mit allen IDs im Speicher
   erzeugen. Dateisperrhinweis von Office und unveränderten Dateiinhalt prüfen.
2. Unter SQLite-Schreibsperre die Revision prüfen und in `participant_transfer`
   den bisherigen und neuen ODS-Inhalt, Kandidaten und Ausgangsrevision speichern.
3. Dateiinhalt nochmals vergleichen, ODS zunächst temporär im selben Ordner
   schreiben, flush/fsync ausführen und die Zieldatei ersetzen. Bei einem Fehler
   vor dem Ersetzen die Absicht verwerfen; Original und Snapshot bleiben erhalten.
4. Den Kandidaten und den SHA-256 des neuen Dateiinhalts in einer SQLite-
   Transaktion übernehmen, die Absicht entfernen und erst dann den sichtbaren
   Sitzungsstand ersetzen. `participant_file` hält nur den letzten akzeptierten
   Dateifingerabdruck; das Snapshotformat ist aktuell Version 6.

Beim Öffnen zuerst offene Übernahmen auflösen: Entspricht die Datei dem neuen
Inhalt, exakt den vorgemerkten Kandidaten einschließlich bereits vergebener IDs
übernehmen. Entspricht sie noch dem alten Inhalt, die Absicht verwerfen. Bei
abweichender oder fehlender Datei nichts überschreiben. Nach einem Fehler beim
abschließenden SQLite-Speichern bleibt die Absicht erhalten und blockiert weitere
Schreibvorgänge; die Datei unverändert lassen und den Arbeitsordner erneut öffnen.
Bei einer zusätzlichen externen Änderung ist eine manuelle Konfliktklärung nötig;
keine automatische Wahl oder Identitätsrekonstruktion.

Danach beim Start registrierte gemeinsame Dateien auf externe Änderungen prüfen
und nach denselben Regeln neu einlesen. Fehler werden in der Oberfläche gemeldet;
der letzte gültige SQLite-Stand bleibt sichtbar. Fehlende registrierte Dateien
nicht automatisch neu erzeugen. Zusätzliche Meldelisten nur übernehmen, wenn die
gemeinsame Datei noch dem akzeptierten Fingerabdruck entspricht. So gehen keine
noch nicht eingelesenen externen Änderungen durch einen Import verloren.

Office-Dateisperren und Inhaltsvergleiche schützen den vorgesehenen lokalen
Ablauf. Es gibt keine atomare Dateisperre gegenüber beliebigen Fremdprogrammen;
während der Übernahme nicht parallel extern speichern. Mehrere gleichzeitig
schreibende Helfer und Netzlaufwerke sind weiterhin nicht zugesagt. Der reale
OpenOffice-Rundlauf wurde am 19.11.2026 vom Nutzer als funktionierend bestätigt.

Aus den entfernten lokalen Versuchsordnern übernommene Datenbanken liegen unter `local-data/uebernommen/`. Das lokale Manifest ordnet Sicherungen den Originalpfaden zu. Dieser Ordner bleibt ignoriert und kann nach bewusster Prüfung der enthaltenen Stände separat aufgeräumt werden.

## Prüfen

Prüfungen nach Wirkung und Fehlerrisiko auswählen. Die Beispiele sind keine
feste Liste, die bei jedem Auftrag vollständig abgearbeitet werden muss.
Verbindliche KI-Arbeitsregeln stehen in [AGENTS.md](../AGENTS.md).

### Einrichtung und Ruff

```powershell
uv sync --locked --group dev
uv run --locked --group dev ruff check src devtools tests scripts
```

Ruff ist als Entwicklungsabhängigkeit in `uv.lock` festgehalten. Die dev-Gruppe
wird über `--group dev` ausdrücklich aktiviert; Start und Paketbau benötigen
sie nicht. Zum gleichzeitigen Einrichten der Buildwerkzeuge:
`uv sync --locked --group dev --group build`. Falls uv nicht im PATH liegt,
`uv` in den Beispielen durch `.\.tools\uv\uv.exe` ersetzen.

Die Konfiguration in `pyproject.toml` aktiviert `E9` und `F`, setzt Python 3.14
voraus und beschränkt die Dateisuche auf Anwendung, Entwicklungswerkzeuge,
Tests und Paketeinstieg. Generierte Ordner und lokale Wettkampfdaten ausschließen.
Bei einer normalen Codeänderung nur die betroffenen Python-Dateien prüfen:

```powershell
uv run --locked --group dev ruff check src/stadtmeisterschaft/scoring.py tests/test_scoring.py
```

Ruff ersetzt keine Verhaltens-, Integrations- oder Typprüfung. Es gibt noch
keinen verbindlichen Typchecker. Formatierung bleibt bis zu einer separat
vereinbarten Umstellung freiwillig; keine projektweite Formatierung mit
Fachänderungen vermischen. Schreibfreie Formatprüfung einer einzelnen Datei:

```powershell
uv run --locked --group dev ruff format --check src/stadtmeisterschaft/scoring.py
```

Ein nicht erfolgreicher Formatcheck zeigt dabei gegebenenfalls bestehenden
Formatierungsbedarf, keinen fehlgeschlagenen Verhaltenstest.

### Entscheidungsmatrix

| Änderung | Erforderlicher Umfang | Befehlsbeispiel |
|---|---|---|
| Reine Prosa, Kommentare oder nachweislich reine Formatierung | Diff, Referenzen bzw. passende Formatprüfung; keine Anwendungstests | `git diff --check` |
| Lokales Verhalten, begrenzte Aufrufer | Relevante Testdatei oder ausreichend abdeckende Klassen/Methoden; Ruff auf geänderten Python-Dateien | `uv run --locked python -m unittest discover -s tests -p "test_scoring.py"` |
| Einzelner reproduzierbarer Fehler | Passender Regressionsfall und betroffene Nachbarfälle | `uv run --locked python -m unittest discover -s tests -p "test_tournament.py" -k test_invalid_weights_not_rounded` |
| Mehrere verbundene Komponenten | Betroffene Fach-, Integrations- und Bedienfälle zusammen auswählen | `uv run --locked python -m unittest discover -s tests -k test_pool_management -k test_pool_display` |
| Zentrale Fachverträge, Datenformat/Migration, Speicher-/Übernahmeverhalten, breite Refactorings, globale Laufzeitabhängigkeiten oder unklarer Wirkungsbereich | Vollständige Testsuite, zusätzlich passende Spezialprüfungen | `uv run --locked python -m unittest discover -s tests` |
| UI-/Drucklayout oder sichtbare Ausgabeinhalte | Betroffene Tests sowie erzeugte Ansichten/PDFs tatsächlich ansehen | `uv run --locked python -m devtools.verify_visuals` |
| Ruff-Konfiguration oder Ruff-Version | Linter über alle Quellpfade, keine Anwendungstests allein wegen einer dev-Abhängigkeit | `uv run --locked --group dev ruff check src devtools tests scripts` |
| Paketierung, DLLs, Einstiegspunkt, paketwirksame Laufzeitabhängigkeiten oder angeforderte Paketlieferung | Build und separat die neu gebaute EXE prüfen | `.\Build-App.ps1`, danach Paketprüfung unten |

Kriterien können zusammenfallen: Eine Schemaänderung mit sichtbaren neuen
Ausgaben benötigt beispielsweise vollständige Tests und eine Ausgabeprüfung.
Ein lokaler Helfer in einer zentralen Datei erfordert nicht automatisch alles,
wenn seine begrenzte Wirkung nachvollziehbar belegt ist. Ausführbare Beispiele,
Imports, Direktiven und fachlich wirksame Texte sind keine reine Prosaänderung.

### Vorhandene Tests gezielt auswählen

| Bereich | Ausgangspunkt für die Auswahl |
|---|---|
| Wertung, Platzierung, Abschluss und Wiederöffnung | `test_scoring.py`; bei geändertem Ausgabe-/Bedienvertrag zusätzlich dessen Verbraucher prüfen |
| Endgültige Teilnehmerstatus, automatische Wertungen, Nullwertungen, Korrektursperren und Ausgabe | `test_participant_status.py`; ergänzend Wertungs-, Speicher- und Migrationsfälle |
| Solver und automatische Einteilung | `test_pool_planning.py`, einschließlich Orakel- und 100-Kinder-Fällen bei Algorithmusänderungen |
| Reguläre und Freundschaftspools, Regeln und Konfiguration | `test_pool_management.py`, je nach Wirkung Anzeige-, Planungs- und Bedienfälle ergänzen |
| Regelhinweise, Sortierung, Anzeige und Export | `test_pool_display.py` |
| Import, Dateifehler, Speichern, Neustart und ältere Bedienfälle | `test_tournament.py`; für Datenformate auch Lebenszyklus- und Migrationsfälle |
| Gemeinsame Teilnehmerdatei, ID-Änderungen, Einfrierschutz, Dateikonflikte und Übernahmeabbruch | `test_participant_file.py`; ergänzend Speicher- und Lebenszyklusfälle |
| Start, Demo-Daten, Migration und Import-Prüfmuster | `test_app_lifecycle.py`; bei Demo-Änderungen auch andere Nutzer von `devtools/demo_data.py` und `helpers.py` |
| Mausabläufe und Altersklassenvorschläge | `test_usability.py`; Konfiguration zusätzlich in Management-/Turniertests |

Diese Zuordnung ist ein Einstieg, kein vollständiger Abhängigkeitsgraph.
Testdateien enthalten zum Teil sowohl Fach- als auch Qt- und Dateiprüfungen.
Mit `-p` zuerst die Datei einschränken; `-k` kann anschließend weiter filtern.
Mehrere `-k`-Filter verknüpfen sich als ODER, nicht als UND. `-k` begrenzt die
Testfälle, verhindert aber bei Discovery nicht grundsätzlich alle Modulimporte.
Null ausgewählte Tests gelten nicht als erfolgreiche Prüfung. Testanzahl,
Fehler und übersprungene Tests im Ergebnis beachten; wichtige übersprungene
Prüfungen bleiben offen. Im Normalfall ohne `-v` ausführen. Laufzeiten bei Bedarf
beim nächsten ohnehin erforderlichen Lauf mit `--durations 10` untersuchen,
statt allein dafür die Suite erneut zu starten.

Bei Fehlerkorrekturen vorhandene Regressionstests nutzen oder gezielt ergänzen.
Bei unerwarteten Fehlern, fehlender Abdeckung oder weiteren betroffenen
Verbrauchern den Umfang ausweiten. Nach relevanten Folgeänderungen neu prüfen;
sonst bereits erfolgreiche Prüfungen nicht unverändert wiederholen. Eine ohnehin
folgende Gesamtprüfung ersetzt die erneute Ausführung erfolgreicher Teilprüfungen.
Keine abschließende Gesamtprüfung allein aus Gewohnheit.

### Visuelle Prüfung

```powershell
uv run --locked python -m devtools.verify_visuals
```

Dieser Generator erzeugt den gesamten Mustersatz unter `tmp/visuals/` sowie
`tmp/druck-1200dpi.pdf`; er unterstützt derzeit keine Auswahl einzelner Szenarien.
Nur bei passendem Anlass ausführen und die betroffenen Ansichten/PDFs tatsächlich
ansehen. Es gibt keinen automatischen Screenshotvergleich. Der bestehende
PDF-Test prüft Erzeugung, grobe Dateimerkmale und Kampfreihenfolge, aber keine
gedruckten Platzierungen. Bei geänderten Druckwerten auch ohne Layoutänderung
passende Inhaltsassertionen oder tatsächliche Sichtprüfung vorsehen.

Für unsichtbare Qt-Tests kann im jeweiligen Prozess `QT_QPA_PLATFORM=offscreen`
gesetzt werden. Tests decken Regeln, Importablehnung, Speicherfehler,
parallele/veraltete Schreiber, Neustart, Sperren und Bedienereignisse ab.
Offscreen-Erfolg ersetzt keinen erforderlichen realen Maus- oder Drucktest.

## Windows-Build

```powershell
.\Build-App.ps1
# Optional separater Ausgabeordner:
.\Build-App.ps1 -OutputDirectory dist-pruefung
```

Der Build verwendet einen eingeschränkten PATH und einen lokalen PyInstaller-Cache, damit fremde ICU-/Qt-DLLs nicht eingebunden werden. Paketordner und EXE heißen `PoolturnierManager`. Zur Weitergabe den gesamten Ordner einschließlich `_internal` kopieren; für den Desktop eine Verknüpfung zur EXE anlegen, statt die EXE herauszukopieren. Das Skript schützt laufende Pakete und Paketordner mit Wettkampfdaten und sammelt Lizenztexte. Es erstellt lokale, unsignierte Pakete.

Paketprüfung mit einem **noch nicht vorhandenen** Arbeitsordner:

```powershell
dist\PoolturnierManager\PoolturnierManager.exe --folder tmp\paketpruefung --smoke-test tmp\paketbericht.json
```

Die Prüfung weist zunächst den leeren normalen Start nach, erzeugt dann ausdrücklich gekennzeichnete synthetische Daten und prüft Speicherung, Ergebnis, Freundschaftspool, PDF, ODS und XLSX. Danach beendet sich die App. Der Bericht enthält `frozen: true`, wenn tatsächlich die EXE geprüft wurde. Ein separater Windows-Rechner, Papierausdruck und OpenOffice-Rundlauf bleiben eigenständige Praxistests.

## Arbeitsweise

Eine aktive App und ein aktiver Backlog. Git hält Zwischenstände und abgeschlossene Experimente; keine Archivkopien, nummerierten Plandateien oder buildspezifischen Dokumentationsstände im Projekt. Fachliche Entscheidungen in `fachregeln.md`, offene Arbeit in `backlog.md`, technische Abläufe hier pflegen. Sinnvolle, geprüfte Zwischenstände committen. Generierte Pakete liegen unter `dist/`, Prüfausgaben unter `tmp/`.

Nutzerpräferenz: etablierte öffentlich verfügbare Bibliotheken verwenden und eigenen Code klein halten. Standardalgorithmen nicht selbst entwickeln, wenn eine passende Bibliothek sie bereits zuverlässig bereitstellt. Eigener Code konzentriert sich auf Fachregeln und die Anbindung an die App.

### Papierstand je Pool

`Store.save` und `save_with_participants` vergleichen unter SQLite-Schreibsperre die gedruckten Inhalte mit dem letzten gespeicherten Snapshot. `Tournament.pool_print_content` beschreibt diese Inhalte; bei Änderungen an `output.draw_pool` den Vergleich mitpflegen. Neue Pools beginnen bei 1, geänderte Druckinhalte erhöhen die Nummer einmal pro erfolgreicher Speicherung. Die sichtbaren Nummern erst nach dem Commit übernehmen. Eine vorgemerkte Teilnehmerübernahme enthält bereits die neuen Nummern, sodass Wiederanlauf sie exakt einmal übernimmt. Kein Druckjournal und keine gespeicherten PDFs.

PDF und Druckvorschau verwenden dieselbe Zeichnung. Standnummer und lokale Erstellzeit stehen klein und grau rechts im Footer; ein gemeinsamer Zeitstempel gilt für alle Seiten einer Ausgabe. Erneutes Zeichnen oder Drucken verändert weder Snapshot noch Standnummer. Vor Einführung dieser Kennzeichnung erzeugte Blätter haben keinen rückwirkend ermittelbaren Papierstand.

### Freundschaftspartner suchen

Auf der Poolseite eines regulären Einzelpools oder eines Freundschaftspools mit 1–4 Kindern „Freundschaftspartner suchen“ wählen. Gestartete Pools bleiben gesperrt. Hinzufügen und „Letzte Auswahl zurücknehmen“ berechnen die vollständige Gruppe neu; erst „Freundschaftspool erstellen“ bzw. „Partner übernehmen“ speichert alle Ergänzungen in einer Sitzungstransaktion. Bei Erfolg öffnet sich die aktualisierte Poolseite mit neuer Besetzung und Kampffolge. Ungespeicherte Poolseitenänderungen vorher speichern oder verwerfen.

Optional im jeweiligen Arbeitsordner `freundschaft.json` mit folgendem Inhalt anlegen:

```json
{"altersfaktor": 8}
```

Ohne Datei gilt 8. Genau dieses Feld mit einer ganzen Zahl ab 0 ist zulässig; ungültiges JSON, Werte und Lesefehler sperren die Partnersuche mit verständlicher Meldung. Die Datei wird bei jedem Öffnen der Suche neu gelesen. Kein zusätzliches Snapshotfeld, keine Migration und keine neue Laufzeitabhängigkeit. Rangwerte werden mit `fractions.Fraction` ohne Rundungsfehler verglichen und ausschließlich intern für die Reihenfolge verwendet. Die tatsächliche reguläre Startklasse hat Vorrang, sonst die jüngste konfigurierte passende Klasse. Nicht zuordenbare Klassen werden erklärt, nicht geraten. Die Geschlechterfreigabe des ersten bestehenden Kindes bleibt der Ausgangsfilter; der größte Rangwert aller Paare bestimmt die Reihenfolge für die erweiterte Gruppe. O-25: Weitere Freundschaftsteilnahmen und wiederholte Paarungen bleiben erlaubt. `Tournament.other_friendship_note` nennt die anderen Freundschaftspools eines Kindes; der aktuelle Pool wird ausgenommen. Die Partnersuche zeigt den Hinweis direkt bei Vorschlägen und Gruppenmitgliedern, `pool_member_warnings` versorgt bestehende Freundschaftspools in Übersicht und Poolseite. Keine Rangänderung, Sperre oder Änderung der Druckausgabe.

Neue Fach-, Konfigurations-, Speicherfehler- und Mausfälle stehen in `tests/test_friendship_search.py`; relevante bestehende Verbraucher sind Poolverwaltung, Teilnehmerstatus, Übersicht und Poolseite. `devtools.verify_visuals` erzeugt zusätzlich `freundschaftssuche-einstieg.png`, `freundschaftssuche.png` und `freundschaftssuche-gruppe.png`.

Die Planungshinweise sind in `ui/planning_details.py` gebündelt: Einzelgewichte, gerichteter Vergleich mit Prozentbetrag bezogen auf das kleinere Gewicht und kompakte Warnungen mit aufklappbaren Details. Diese Helfer werden nur von der Oberfläche verwendet; `output.py` und `Tournament.pool_print_content` bleiben von der Anzeigeumstellung unberührt. In der Partnersuche steht die Berechnung hinter dem Info-Button. Der interne Rangwert wird weiter zur Sortierung verwendet, aber nicht als Spalte gezeigt. Bei mehreren Kindern benennt der sichtbare Gewichtsvergleich den Partner mit dem größten relativen Gewichtsunterschied; die Rangfolge prüft unverändert alle Paare der erweiterten Gruppe. Begegnungsbeschriftungen zeigen nur Hinweise zum jeweiligen Paar. Die Druckprüfung zählt ausdrücklich nur die gemeinsame Gewichtsspanne als gedruckte Gewichtsangabe.

### Planungsübersicht: Alter, Freundschaftsverweise und Filter

Die bestätigte Arbeitsanweisung umfasst nachvollziehbare Altersklassen, bereits organisierte Freundschaftskämpfe erkennen, weitere Kämpfe über die vorhandene Partnersuche organisieren und die Poolübersicht filtern. `ui/planning_details.py` erzeugt Klassen-/Altersangaben und konkrete Alterswarnungen. Tatsächliche reguläre Startklassen bleiben maßgeblich; Jahrgangsableitungen sind gekennzeichnet. Das angezeigte Alter verwendet das gespeicherte Veranstaltungsjahr. Ohne Veranstaltungsdatum kein Alter aus dem heutigen Jahr erfinden.

`FriendshipLinks` leitet alle Freundschaftsverweise aus aktuellen Mitgliedschaften ab. Mindestens zwei Mitglieder bedeuten organisiert, ein Mitglied nur angelegt. Keine zusätzliche Datenhaltung, keine Migration und keine neue Druckrevision des regulären Einzelpools allein durch die Anzeige. Entfernen/Löschen oder Neueinlesen berechnen die Anzeige neu. Navigation von der Poolseite schützt ungespeicherte Formulareingaben.

`Window.apply_pool_filter` blendet Karten aus, hebt versteckte Teilnehmerauswahl auf und ordnet die sichtbaren Karten in der bestehenden Fachsortierung lückenlos an. Der Filter ist eine reine Ansichtseinstellung im offenen Fenster; er bleibt bei Aktionen/Neuladen erhalten, wird aber nicht im Wettkampf gespeichert. „Alle“ zeigt auch „Noch ohne Pool“, andere Filter ausschließlich die bezeichneten Pools. Reguläre Pools enthält Einzelpools; der Einzelpoolfilter schließt Freundschaftspools aus. Leere Freundschaftspools sind sichtbar. Sammel-PDF und Druckvorschau behalten alle belegten Pools, wie im Filter-Tooltip erklärt.

Prüffälle: `PlanningOverviewTests` in `tests/test_pool_display.py`, ergänzt durch bestehende Anzeige-, Freundschafts-, Status- und Bedienfälle. Prüfmuster: `planung-altersklassen.png`, `planung-einzelpool-organisiert.png`, `planung-freundschaftsverweis.png`, `planung-filter-freundschaft.png` und `planung-filter-einzelpools.png` unter `tmp/visuals/`.

Die Übersicht trennt die einklappbare Leiste „Noch ohne Pool“, reguläre Pools und
Freundschaftskämpfe. `Window.arrange_pool_cards` ordnet die gefilterten Karten in
zwei getrennten Rastern mit gleicher, aus der Viewportbreite berechneter
Spaltenzahl an; innerhalb jedes Bereichs bleibt `sorted_pools` maßgeblich.
Sammeldruck und Speicherung verwenden unverändert die gemeinsame Fachsortierung.
Die geschlossene Leiste leitet Drops an dieselbe `ParticipantList` wie die offene
Liste weiter. Ein neu hinzugekommenes erstes Kind öffnet die Leiste automatisch.

`ui/compact_participants.py` zeichnet Datenspalten mit einem Qt-Itemdelegate;
Teilnehmer-ID, zugänglicher Volltext, Auswahl und Drop-Vertrag der bestehenden
Listen bleiben erhalten. Name, Klasse und Zusatzhinweise umbrechen nach der
tatsächlichen Breite. Die Listen passen ihre Höhe nach dem Layoutwechsel
zeitversetzt an; `PoolCard` berücksichtigt zusätzlich die Höhe umgebrochener
Labels. Dadurch bleiben nach Fensterwechseln alle Zeilen innerhalb der Karten.
Das feste Kontextfeld im Kopf verwendet die vorhandenen Hilfetexte. Ein auf das
Hauptfenster begrenzter Ereignisfilter leitet Mausbewegungen und Tooltip-Ereignisse
dorthin, nachdem die Maus zwei Sekunden über demselben Element geblieben ist.
Elementwechsel startet die Wartezeit neu; Verlassen bricht sie ab. Eine bewusste
Auswahl zeigt den Kontext sofort und unterstützt auch die Tastaturbedienung. Dialoge behalten ihre
eigenen Hilfen. Das Feld bleibt gleich hoch, lange Inhalte sind scrollbar.

Zusätzliche Regressionen in `PlanningOverviewTests` prüfen Bereichstrennung,
Fensterwechsel, vollständige Zeilen, gerenderte Lesezeichen, geschlossene
Drop-Leiste und Kontextinformationen ohne Popup. Weitere Prüfmuster:
`planung-kompakt-breit.png`, `planung-kompakt-schmal.png`,
`planung-kompakt-freundschaft.png` und `planung-kompakt-ohne-pool.png`.

## Interne Lesezeichen

Teilnehmer und Pools speichern `bookmark`: `None` bedeutet unmarkiert, ein Text
(auch leer) bedeutet markiert. Pro Objekt gibt es eine Freitextnotiz. Violette
Lesezeichen sind von fachlichen Warnungen getrennt. Unmarkierte Objekte zeigen
keine Lesezeichensymbole. In der Übersicht öffnet Rechtsklick auf eine Kinderzeile
ein Kontextmenü mit „Lesezeichen setzen“ bzw. „Lesezeichen bearbeiten“. Rechtsklick
auf Poolkopf, Poolangaben, Kartenfläche oder leere Listenfläche betrifft den Pool.
Gesetzte Markierungen erscheinen als kleines violettes Symbol am Poolkopf bzw.
in der Kinderzeile, ohne flächige Hervorhebung und zusätzliche Schaltflächen.

Die Pooldetailseite enthält genau eine sichtbare Lesezeichenaktion oben rechts
für den Pool, im unmarkierten Zustand ohne Symbol und farbige Hervorhebung.
Teilnehmernotizen sind dort per Rechtsklick auf Teilnehmerzeilen, Namen in
Begegnungen, Auswertung oder die Teilnehmerauswahl erreichbar. Die Partnersuche
verwendet ebenfalls Rechtsklick auf Teilnehmerzeilen und Vorschläge; unmarkierte
Namen erhalten weder Symbole noch zusätzliche Verweise. Die Teilnehmerübersichten
nutzen `ParticipantSummary` mit einzelnen beschrifteten Zeilen, sodass Rechtsklick
auch bei umgebrochenen Namen das richtige Kind trifft.

„Nur mit Lesezeichen“ kombiniert sich mit dem Poolartfilter und zeigt Pools mit
eigener Markierung oder markierten Mitgliedern samt vollständiger Besetzung.
Bei Kindern ohne Pool zeigt der Filter nur markierte Kinder. Abbrechen verändert
nichts; bei Speicherfehlern bleibt der Editor mit der Eingabe offen. Lesezeichen
bleiben auch nach Poolstart bearbeitbar. Ungespeicherte Ergebniseingaben bleiben
beim Bearbeiten einer Notiz erhalten. Beim Neueinlesen der Teilnehmerdatei bleiben
Notizen anhand der Teilnehmer-ID erhalten. Gelöschte Teilnehmer und gelöschte
oder durch Neuverteilung ersetzte Pools verlieren ihre eigenen Lesezeichen.

Notizen werden weder in Teilnehmerdateien noch auf Poollisten ausgegeben und
ändern den Papierstand nicht. Migration, Speicherung, Dateirundlauf, Filter und
Bedienung werden in `test_bookmarks.py` geprüft.

### Gemeinsame Suche und Orga-Notizen

`ui/search_sidebar.py` ersetzt das bisherige Completer-Popup der Athletensuche.
Die Seitenleiste steht im horizontal verstellbaren `QSplitter` neben dem Poolraster.
„Suche & Orga-Notizen · N“ blendet die Leiste ein oder aus; aktive Ansicht und
Suchtext bleiben erhalten. Das Kreuz in der Leiste synchronisiert den Schaltzustand.
Eine gemeinsame Suche findet Kinder weiterhin mit
`search_participants` einschließlich Tippfehlern; Poolnamen und in der Notizenansicht
auch Notiztexte werden normalisiert durchsucht. Die Notizenliste ist unabhängig
von den Poolfiltern und enthält jedes markierte Objekt einmal, auch ohne Notiztext.
Navigation nutzt `show_participant` bzw. `show_pool`, ohne eine Poolseite zu öffnen.
Enter im Suchfeld springt zum ersten Treffer. Poolverweise nennen alle Teilnahmen.
Die Auswahl eines Kindes bleibt als durchgehende Zeilenfläche sichtbar, auch bei
Tastaturfokus. Der Delegate unterdrückt den zusätzlichen nativen Text-Fokusrahmen,
der sonst in den selbst gezeichneten Namen und das Lesezeichen hineinragt.

Inline-Entwürfe liegen je Objekttyp und ID im Fenster und bleiben beim Suchen,
Umschalten und Ausblenden erhalten. Explizites Speichern und Erledigen verwenden
unverändert `Window.change` und `TournamentSession`. Speicherfehler erhalten
Eingaben und bisherigen Zustand; inzwischen anderweitig bearbeitete Notizen
werden nicht still überschrieben. Vor Fensterende oder Arbeitsordnerwechsel
ungespeicherte Entwürfe gemeinsam speichern, verwerfen oder weiterbearbeiten.
„Erledigt“ setzt `bookmark` auf `None`; acht Sekunden lang lässt sich der letzte
Eintrag wiederherstellen. Rückgängig gilt ausschließlich im selben Arbeitsordner,
für ein noch existierendes und weiterhin unmarkiertes Objekt. Keine Historie und
keine Änderung am Datenformat, Ausdruck oder Papierstand.

`test_participant_search.py` prüft Suche, Navigation, Entwürfe, Speicherfehler,
Erledigen/Rückgängig und schmale Fenster; `test_bookmarks.py` prüft die bisherigen
Verbraucher. `sidebar_examples` in `devtools.verify_visuals` erzeugt gezielt
`orga-notizen-breit.png`, `orga-notizen-schmal.png`, `orga-notizen-bearbeiten.png`,
`orga-notizen-erledigt.png`, `orga-suche.png` und `orga-suche-kind-markiert.png`.

### Numerische Gewichte beim Tabellenimport

Der ODS-Import liest in Spalte F bei `office:value-type="float"` den Zahlenwert,
nicht den gerundeten Anzeigetext. `import_weight` gleicht nur Abweichungen bis
zu zwei `math.ulp` zum nächsten Zehntelkilogramm aus; XLSX-Zahlen durchlaufen
dieselbe Prüfung. So ist Calcs gespeichertes `20.399999999999999` als 20,4 kg
importierbar, während 20,41 kg oder abweichende Textwerte abgelehnt werden.
Andere ODS-Spalten und die exakte Fachprüfung `parse_weight` bleiben unverändert.
Die Importregressionen liegen in `test_tournament.py`.

## Abgleich zusätzlicher Meldelisten

`participant_import.compare_import` vergleicht die normalisierten Werte der fünf
Identitätsfelder ohne Gewicht. Exakte Textgleichheit; keine unscharfe Namenssuche.
Doppelte Schlüssel innerhalb der Meldeliste und mehrere vorhandene Treffer
brechen den Import vor jeder Speicherung ab. Unveränderte eindeutige Treffer
werden übersprungen. `ImportComparison` beschreibt neue Kinder und Gewichte,
`ImportResult` die tatsächlich übernommenen bzw. übersprungenen Meldungen.

`TournamentSession.prepare_import` liest und prüft die Meldeliste und merkt den
Ausgangsstand, dessen Revision und die bisherige gemeinsame Datei. `ImportMerge`
zeigt alle Gewichtsabweichungen in einem Dialog. Nur ungesperrte Gewichte lassen
sich zwischen bestehendem und neuem Wert auswählen, Standard ist bestehend.
Auch ausschließlich gesperrte Abweichungen werden vor der Übernahme angezeigt.
Bei Abbrechen wird nichts gespeichert; nach Speicherfehler bleibt die Auswahl
für einen erneuten Versuch erhalten. Bei verändertem Sitzungsstand oder Revision
ist eine neue Vorschau erforderlich; Änderungen an der gemeinsamen Datei schützt
weiter die bestehende Übernahmeprüfung. Die Bestätigung verwendet die in der
Vorschau eingelesenen Meldungen, nicht eine erneut gelesene Quelldatei.

`commit_import` führt den Abgleich und die Auswahlprüfung auf einer Kopie erneut
aus und nutzt die bestehende ODS-/SQLite-Übernahme. IDs und Metadaten bestehender
Teilnehmer bleiben erhalten. Gewichtsschutz wird aus sämtlichen gestarteten
Teilnahmen abgeleitet. Druckstände ändern sich nur bei tatsächlich geändertem
Druckinhalt. Der ID-basierte Neueinleseweg bleibt unverändert. Regressionen und
Bedienfälle: `test_import_merge.py`; visuelles Muster: `import-gewichtsabgleich.png`.
