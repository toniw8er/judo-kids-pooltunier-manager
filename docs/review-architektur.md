# EGM: Architektur, Codequalität und Dokumentationsabgleich

Den ersten Prompt im Projekt mit dem EGM-Plugin ausführen. Nach dem Review den
zweiten Prompt im selben Chat verwenden. Die Analyse verändert keinen
Anwendungscode; die Umsetzung baut auf den geprüften Befunden auf.

## 1. Review-Prompt

```text
Führe einen unabhängigen Elephant-Goldfish-Review dieses bestehenden Projekts
durch. Antworte und schreibe Berichte auf Deutsch. Prüfe den tatsächlichen Code
und seine Verbraucher, nicht nur die Beschreibung der Architektur.

Ziel:
Bewerte Projektaufbau, Architektur, Clean Code, fachliche Konsistenz,
Datenintegrität, Tests, Betriebsfähigkeit und Übereinstimmung von Dokumentation
und Implementierung. Erstelle einen belegten, priorisierten Verbesserungsplan.
Unterstelle weder gute Qualität noch einen notwendigen Architekturumbau.

EGM artifact directory: tmp/reviews/architektur

Workflow und Konfiguration:
- Lies die aktuell installierte EGM-Codex-Integration und egm-review-loop.
- Verwende egm-review-loop als konfigurierten Bestandsreview, nicht die
  fünfstufige Prüfung einer neuen Featurespezifikation.
- TargetFile: docs/entwicklung.md
- SemanticTarget: full file
- Reviewers: codebase_details, structural, zoom_out
- Standards: Für alle drei Reviewer gelten die Prüfkriterien dieses Auftrags.
  Als Standarddatei verwende docs/review-architektur.md, Abschnitt
  „1. Review-Prompt“. Prüfe sie als Maßstab, nicht als Anwendungsspezifikation.
- GoldfishContext: AGENTS.md, README.md, docs/entwicklung.md,
  docs/fachregeln.md, docs/backlog.md, pyproject.toml, uv.lock,
  .python-version, .gitignore, src/stadtmeisterschaft/, tests/, devtools/,
  scripts/, Start-App.ps1, Start-Entwicklung.ps1 und Build-App.ps1.
  Fachliche Referenzen unter docs/referenzen/ bei konkretem Klärungsbedarf lesen.
- TargetFile ist der Einstieg in die Architekturbeschreibung. Prüfgegenstand
  sind ausdrücklich auch Quellcode, Tests, Skripte und weitere Dokumente.
  Befunde dürfen und sollen dort verortet werden.
- Diese Konfiguration ist beauftragt; keine zusätzliche Konfigurationsfreigabe.
- Genau eine Review-Runde mit drei frischen Goldfish-Kontexten ist beauftragt.
  Das überschreibt automatische Konvergenz- und Reparaturschleifen. Behaupte
  nach einer Runde keine nach EGM nachgewiesene Konvergenz.
- Verwende fork_turns: none beziehungsweise das entsprechende native Mittel.
  Jeder Reviewer liest seine installierte Persona und diesen Prüfauftrag.
  Übergib keine bisherigen Schlussfolgerungen oder Gesprächshistorie.
  Beachte, dass frische Gesprächskontexte keine vollständige Isolation von
  Host-Anweisungen und gemeinsamem Dateisystem garantieren.
- Starte die Reviewer direkt, ohne zusätzliche Synthesizer-Agenten. Warte auf
  ihre tatsächlichen Berichte. Behandle fehlgeschlagene Reviewer nach den
  EGM-Regeln; fehlende Ergebnisse sind keine mängelfreie Prüfung.

Projektkontext:
Lokale Windows-Desktop-App für ein Judo-Kinderturnier. Python 3.14, uv,
unittest, PySide6, SQLite und OR-Tools. Die Anwendung soll verständlich und
zuverlässig weiterentwickelbar bleiben. Beurteile die Architektur anhand dieser
Aufgabe; setze keine verteilten Dienste oder zusätzlichen Frameworks voraus.
AGENTS.md und die dortige risikobasierte Prüfstrategie gelten.

Vorgehen und Arbeitsteilung:
1. Lies git status und den aktuellen Diff. Bestehende Änderungen gehören zum
   geprüften Ist-Stand; überschreibe sie nicht. Dokumentiere die Ausgangsrevision
   und relevante lokale Änderungen. Auch bei leerem Diff den Bestand prüfen.
2. Erstelle eine knappe Karte der Module, Verantwortlichkeiten und Abhängigkeiten.
   Unterscheide dokumentierte Sollstruktur von tatsächlich gelesenen Aufrufen.
3. Jeder Reviewer verschafft sich anhand der grundlegenden Dokumente und einer
   Dateiliste Orientierung. Danach gezielt lesen statt das gesamte Repository
   mehrfach vollständig einzulesen. Verwandte Implementierungen, Aufrufer und
   Tests gemeinsam untersuchen.
4. Verteile die Schwerpunkte:
   - codebase_details: fachliches Verhalten, Speicher-/Importverträge,
     Fehlerpfade, Testnachweise sowie sachlicher Doku-Code-Abgleich.
   - structural: Modulgrenzen, Abhängigkeitsrichtung, Zuständigkeiten,
     Kopplung, Kohäsion, Zustandsänderungen und konkrete Clean-Code-Probleme.
   - zoom_out: Angemessenheit der Gesamtarchitektur, Änderbarkeit,
     Dokumentationsnutzbarkeit, Betrieb, Auslieferung und übersehene Risiken.
5. Verfolge mindestens diese Abläufe durch die beteiligten Komponenten:
   - Meldelistenimport und gemeinsame Teilnehmerdatei: Vorschau, Übernahme,
     externe Änderungen, Speicherung und Wiederherstellung.
   - Ergebniseingabe: Validierung, Wertung, Poolabschluss, Wiederöffnung und
     übereinstimmende Anzeige in Oberfläche und Druck.
   - Rückzug/Disqualifikation: alle betroffenen Teilnahmen, automatische
     Ergebnisse, Bearbeitungssperren und Platzierungen.
   - Automatische Einteilung: Randbedingungen, Reproduzierbarkeit,
     Solverabbruch und unveränderter Stand bei Fehlern.
6. Erfasse, welche weiteren Bereiche untersucht wurden und wo nur Stichproben
   vorliegen. Kennzeichne verbleibende Lücken und Unsicherheiten.

Prüfkriterien:
A. Projektaufbau und Architektur
- Sind Verantwortlichkeiten und Abhängigkeitsrichtungen klar und eingehalten?
- Bleibt der Fachkern unabhängig von Qt? Enthält die UI Fachentscheidungen,
  die auch andere Verbraucher benötigen? Gibt es konkurrierende Berechnungen?
- Werden zentrale Speicher- und Übernahmeverträge durchgängig verwendet?
- Gibt es Zyklen, unklare Schnittstellen, Zugriffe auf fremde interne Methoden
  oder unnötige gegenseitige Kenntnis? Belege die konkrete Auswirkung.
- Können typische Änderungen an Wertung, Import oder Darstellung lokal und
  nachvollziehbar erfolgen? Wo müssen mehrere Stellen synchron geändert werden?

B. Clean Code und Wartbarkeit
- Verständliche Namen, klare Einheiten und Typen an relevanten Schnittstellen.
- Zusammenhängende Verantwortlichkeiten, verständliche Kontrollflüsse,
  sichtbare Nebenwirkungen und eindeutige Fehlerbehandlung.
- Keine duplizierten Regeln, widersprüchlichen Wahrheitsquellen, stillen
  Fehlerbehandlungen oder überraschenden Zustandsänderungen.
- Kommentare erklären Gründe, Verträge oder überraschende Randfälle.
- Große Dateien, lange Methoden und fehlende Typannotationen sind Hinweise,
  keine eigenständigen Beweise schlechter Qualität. Keine starren Grenzwerte.
- Prüfe auch unnötige Abstraktionen und Überengineering. Empfiehl neue Klassen,
  Schichten oder Werkzeuge nur für ein belegtes Problem mit konkretem Nutzen.

C. Fachmodell und Datenintegrität
- Sind Invarianten und erlaubte Zustandsübergänge zentral abgesichert,
  einschließlich Aufrufen außerhalb der Oberfläche?
- Bleiben bei Fehlern letzter bestätigter Stand und relevante Eingaben erhalten?
- Prüfe Revisionen, Sperren, Migrationen und den Übergang zwischen SQLite und
  Teilnehmerdatei, einschließlich Unterbrechung und externer Änderungen.
- Keine Änderung der Fachregeln als vermeintliche Codebereinigung vorschlagen.

D. Tests und technische Nachweise
- Decken Tests fachliche Erwartungen, Grenzen, Fehler und Verbraucher ab?
- Prüfen sie Verhalten oder bilden sie nur die Implementierung nach?
- Sind Eingaben reproduzierbar und Tests ausreichend unabhängig voneinander?
- Welche konkreten Risiken sind nicht abgedeckt? Unterscheide fehlende
  Abdeckung von lediglich nicht ausgeführten vorhandenen Tests.
- Grüne Tests und Ruff allein beweisen weder Clean Code noch gute Architektur.
  Beurteile Werkzeuge anhand ihrer tatsächlich konfigurierten Regeln.

E. Dokumentationsabgleich in beide Richtungen
- Doku -> Code -> Test: Wo wird eine beschriebene Regel umgesetzt und belegt?
- Code -> Doku: Welche wirksamen Einschränkungen, Sonderfälle oder
  Architekturentscheidungen fehlen in der Dokumentation?
- Trenne bestätigte Fachregel, technische Beschreibung, offene Anforderung
  und historische Referenz. Nicht jede Abweichung bedeutet einen Codefehler.
- Stimmen Modulbeschreibungen, Datenformate, Befehle und Betriebsabläufe?
- Sind README, Fachregeln, Entwicklung und Backlog klar abgegrenzt,
  auffindbar und ohne problematische Mehrfachpflege verständlich?
- Erstelle eine kompakte Abgleichmatrix für die untersuchten Kernabläufe:
  dokumentierte Aussage | Codefundstelle | Testnachweis | Abweichung/Status.

F. Betrieb, Bedienbarkeit und Daten
- Reproduzierbare Umgebung und Auslieferung, native Abhängigkeiten,
  Offlinebetrieb sowie angemessene Sicherungs- und Wiederherstellungsabläufe.
- Verständliche Fehlermeldungen, nachvollziehbare Diagnose und Erhalt von
  Eingaben, insbesondere unter Zeitdruck im Turnierbetrieb.
- Umgang mit personenbezogenen Daten in Testdaten, Logs und Ausgaben.
- Plausible Leistungsrisiken bei realistischen Größen und blockierende
  UI-Arbeit. Vermutungen als solche kennzeichnen; Messwerte nicht erfinden.

Beleg- und Bewertungsregeln:
- Jeder Befund erhält eine stabile ID, Reviewer, EGM-Schweregrad
  Blocker/Major/Nit, Datei mit aktueller Zeile und Symbol, konkreten Beleg,
  Auswirkung, Änderungsvorschlag und passende Validierung.
- Schweregrade begründen. Aufwand und Umsetzungsreihenfolge separat bewerten.
- Bestätigte Fehler, Wartbarkeitsrisiken, optionale Verbesserungen und offene
  Hypothesen unterscheiden. Unsichere Vermutungen sind keine bestätigten Fehler.
- Für Strukturänderungen Nutzen, Kosten und stärkstes Gegenargument nennen.
- Suche Gegenbelege, bevor du einen Befund bestätigst. Keine Befundquote und
  keine Kritik nur um Kritik zu liefern. Bewährte Bereiche ebenfalls belegen.

Prüfungen und Grenzen:
- Keine Anwendungsdateien, Tests, Abhängigkeiten oder bestehenden Dokumente
  ändern. Nur Review-Artefakte im genannten Verzeichnis schreiben. Kein Commit.
- Erkenntnisse aus Lesen und tatsächlich ausgeführten Prüfungen getrennt nennen.
- Zusätzliche Befehle nur zur Klärung konkreter Fragen ausführen, nach AGENTS.md.
  Keine Builds, visuellen Generatoren oder Kompletttests aus Gewohnheit.
  Niemals produktive Wettkampfdaten für Prüfungen verändern.
- Bei notwendigen Tests uv und unittest verwenden; keine neue Testinfrastruktur.
  Berichte Befehl, Ergebnis, Testanzahl, Auslassungen und Umgebungsfehler.

Ergebnis:
Speichere die Einzelberichte und einen deduplizierten Gesamtbericht unter dem
Artefaktverzeichnis. Der Gesamtbericht heißt reviewbericht.md und enthält:
1. Belastbares Gesamturteil mit Grenzen: Welche Bereiche sind gut wartbar,
   welche problematisch, welche nicht ausreichend geprüft?
2. Tatsächliche Architektur und wesentliche Abhängigkeiten.
3. Priorisierte Befunde mit den geforderten Belegen.
4. Dokumentationsabgleichmatrix.
5. Kleine, sinnvoll geordnete Umsetzungspakete mit Befund-IDs, betroffenen
   Verbrauchern, Akzeptanzkriterien und geplanter Validierung.
6. Bewusst nicht empfohlene Umbauten samt Begründung.
7. Reviewerstatus, Prüfumfang, ausgeführte Befehle und verbleibende Lücken.

Prüfe als Elephant die Befunde gegen die Quellen und ordne sie nach EGM als
PROPOSE FIX, CONTEST, ESCALATE oder DECLINE ein. Halte die ursprünglichen
Reviewer-Schweregrade fest; begründe Widerspruch separat. Verwirf Dubletten
ohne ihre Herkunft zu verlieren. Gib keine pauschale Freigabe „Clean Code“.
Beende den Auftrag nach Bericht und Umsetzungsplan. Keine automatische Reparatur.
Verlinke im Chat den Bericht und nenne kurz die wichtigsten Befunde.
```

## 2. Folgeprompt zur Behebung

```text
Behebe auf Grundlage von tmp/reviews/architektur/reviewbericht.md die bestätigten
Probleme dieses Projekts. Lies den Bericht, die Befundentscheidungen und den
aktuellen git status/Diff. Prüfe, ob die Befunde zum aktuellen Code noch passen.

Umfang und Autorisierung:
- Setze die als PROPOSE FIX bestätigten notwendigen Fehlerkorrekturen und
  begründeten Wartbarkeitsverbesserungen in der vorgeschlagenen Reihenfolge um.
- Optionale Stilpräferenzen, CONTEST, DECLINE und ungeklärte ESCALATE-Befunde
  gehören nicht zum automatischen Umsetzungsumfang.
- Routinemäßige, reversible Code-, Test- und Dokumentationsänderungen sind
  damit beauftragt. Keine erneute Freigabe pro Datei oder Umsetzungspaket.
- Fachlich offene Entscheidungen gezielt klären; unabhängige Arbeit fortsetzen.
  Bestehende Fachregeln gelten. Keine neuen Produktfunktionen, kein Commit.

Arbeitsweise:
1. Nenne vor jedem Umsetzungspaket kurz Befund-IDs, Änderungsbereich,
   betroffene Verbraucher und geplante Prüfungen gemäß AGENTS.md.
2. Lies relevante Implementierung, Aufrufer und Tests. Wähle die kleinste
   zusammenhängende Änderung, die das belegte Problem tatsächlich löst.
3. Bei Fehlerkorrekturen vorhandene Regressionstests nutzen oder einen
   passenden Verhaltenstest ergänzen. Keine Tests, die nur Code nachbilden.
4. Halte Code und zugehörige Dokumentation synchron. Bei einem Widerspruch
   anhand verbindlicher Fachregeln entscheiden, welche Seite zu ändern ist.
5. Führe die risikogerecht erforderlichen Prüfungen aus. Beachte Ruff,
   Testauswahl, Inhalts-/Sichtprüfung und gegebenenfalls EXE-Prüfung gemäß
   AGENTS.md. Erfolgreiche unveränderte Prüfungen nicht unnötig wiederholen.
6. Untersuche Fehler und behebe ihre Ursache. Markiere blockierte oder nicht
   verifizierbare Punkte offen; ein gestarteter Test ist kein erfolgreicher Test.
7. Führe tmp/reviews/architektur/umsetzungsstand.md mit Befund-ID, Entscheidung,
   Änderung, Validierung und Restpunkten. Markiere einen Befund erst als behoben,
   wenn seine Akzeptanzkriterien belegt sind.

Bewahre fremde Änderungen. Keine projektweite Umformatierung, keine neuen
Frameworks oder großflächigen Umbauten ohne belegten Bedarf. Nutze uv,
pyproject.toml, uv.lock und die bestehende unittest-Infrastruktur.

Arbeite alle beauftragten Umsetzungspakete ab. Keine zusätzliche vollständige
EGM-Runde oder Review-Schleife ohne ausdrücklichen Auftrag. Berichte abschließend
kurz Änderungen, Prüfungen mit Testanzahl, begründet ausgelassene Prüfungen sowie
offene Befunde und Unsicherheiten. Verlinke den Umsetzungsstand.
```
