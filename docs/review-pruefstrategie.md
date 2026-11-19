# Review-Prompt für Prüfstrategie und KI-Arbeitsregeln

Den folgenden Prompt in einem neuen Chat mit dem Elephant-Goldfish-Plugin
ausführen. Er fordert eine unabhängige Bestandsprüfung an, keine Implementierung.

```text
Führe einen unabhängigen Elephant-Goldfish-Review der Prüfstrategie und ihrer
Umsetzung in diesem Repository durch. Antworte auf Deutsch.

Konfiguration:
- TargetFile: AGENTS.md
- SemanticTarget: full file
- Reviewers: codebase_details und zoom_out
- Standards: Für beide Reviewer gelten die unten aufgeführten Prüfkriterien.
  Falls eine Standarddatei benötigt wird: docs/review-pruefstrategie.md.
- GoldfishContext: README.md, docs/entwicklung.md, pyproject.toml, uv.lock,
  .gitignore, tests/, devtools/helpers.py, devtools/verify_visuals.py,
  devtools/demo_data.py, src/stadtmeisterschaft/, Build-App.ps1,
  scripts/Environment.ps1, scripts/entrypoint.py, Start-App.ps1 und
  Start-Entwicklung.ps1.

Prüfkriterien:
1. Stimmen Dokumentation, KI-Anweisungen, Ruff-Konfiguration, Installation und
   tatsächliche Teststruktur überein? Prüfe Auswahlbefehle, dev-Gruppe,
   gesperrte Versionen, Dateisuche und Ausschlüsse. Behaupte keine ausgeführten
   Prüfungen allein aufgrund der Dokumentation.
2. Passt der Prüfumfang zum Risiko? Bewerte lokale Änderungen, mehrere
   Komponenten, zentrale Verträge, Datenmigration, globale Abhängigkeiten,
   reine Prosa und Formatierung. Suche sowohl unnötige Komplettprüfungen als
   auch Lücken durch zu enge Filter. Betrachte Verbraucher gemeinsamer Logik.
3. Sind Eskalation, Wiederverwendung erfolgreicher Ergebnisse, Null-Testläufe,
   übersprungene Tests und Folgeänderungen ausreichend geregelt?
4. Werden Ruff, freiwillige Formatierung, Verhaltenstests, visuelle Prüfung,
   Build und EXE-Smoke-Test sauber nach ihrem tatsächlichen Nachweis bewertet?
   Beachte, dass der PDF-Test keine gedruckten Platzierungen nachweist und
   verify_visuals keinen automatischen Bildvergleich enthält.
5. Reduzieren die Regeln voraussichtlich wiederholtes Lesen, unnötige Ausgaben
   und Review-Schleifen? Ist die ständig gelesene AGENTS.md selbst zu lang
   oder redundant? Trenne belegte Strukturprobleme von Vermutungen über
   frühere Laufzeiten und Tokenverbräuche. Erfinde keine Einsparquoten.
6. Sind Änderungen auf diesen Auftrag begrenzt? Prüfe insbesondere, ob die
   Ruff-Einführung bestehende Laufzeitpakete oder Anwendungsverhalten verändert
   und ob Importbereinigungen ausschließlich ungenutzte Imports entfernen.

Ablauf und Grenzen:
- Lies den aktuell installierten EGM-Workflow und die Reviewer-Personas.
  Ein einmaliger Review mit zwei frischen Goldfish-Kontexten ist gewünscht;
  keine automatische Folge- oder Reparaturschleife.
- Verwende fork_turns: none bzw. das entsprechende native Isolationselement.
  Übergib den Reviewern diesen Auftrag und die Quellen, keine bisherige
  Unterhaltung oder vorausgesetzten Schlussfolgerungen. Die zu prüfende
  AGENTS.md muss als Prüfgegenstand gelesen werden; ihre bloße Anwesenheit
  beweist keine vollständige Isolation von Host-Anweisungen.
- Prüfe zunächst git status und den aktuellen Diff; dieser kann nach einem
  Commit leer sein. Prüfe in jedem Fall die genannten aktuellen Dateien.
- Prüfe unabhängig mit frischen Quellen, nicht nur anhand dieses Prompts.
  codebase_details prüft Fakten und Ausführbarkeit; zoom_out hinterfragt
  Nutzen, Komplexität und mögliche übersehene Qualitätsrisiken.
- Keine Anwendungsdateien, Regeln oder Abhängigkeiten ändern. Kein Commit.
  Keine Builds, Kompletttests oder visuellen Generatoren aus Gewohnheit.
  Zusätzliche Prüfungen nur bei einer konkreten offenen Frage begründen.
- Warte auf die echten Berichte beider Reviewer. Fehlende oder fehlgeschlagene
  Reviewer als nicht durchgeführt kennzeichnen, nicht als mängelfrei.
- Liefere deduplizierte Befunde mit Schweregrad, Datei/Zeile, Beleg, Auswirkung
  und konkretem Änderungsvorschlag. Trenne notwendige Korrekturen von optionalen
  Verbesserungen. Nenne auch Gegenargumente gegen zusätzliche Regeln/Tools.
- Speichere den Bericht bei Bedarf unter tmp/reviews/pruefstrategie.md.
  Keine versionierten Dateien ändern. Gib abschließend eine kurze Bewertung
  der offenen Risiken und der tatsächlich durchgeführten Prüfungen aus.
```
