# Backlog

Stand: 19.11.2026. Wir arbeiten direkt an der App. Dieses Dokument enthält den aktuellen Arbeitsvorrat; erledigte Zwischenstände und Reviews liegen in Git. Die [Fachregeln](fachregeln.md) beschreiben das gewünschte Verhalten.

## Bereits vorhanden

- Weitere Freundschaftsteilnahmen und wiederholte Paarungen bleiben erlaubt. Der Freundschaftsfinder nennt direkt bei Vorschlägen und Gruppenmitgliedern die anderen Freundschaftspools. Übersicht und Poolseite warnen bei Mehrfachteilnahmen; Entfernen und Löschen aktualisieren die Hinweise. O-25 ist entschieden.
- Planungsübersicht mit Filtern „Alle“, „Reguläre Pools“, „Einzelpools“ und „Freundschaftspools“ bei unveränderter Sortierung und Druckauswahl. Klassen/Jahrgänge beim Kind, vollständige Altersangaben im Wettkampfjahr auf der Poolseite und konkrete Alterskonflikte. Einzelpools zeigen aktuelle, anklickbare Freundschaftsverweise mit Unterscheidung zwischen angelegtem Pool und organisiertem Kampf; Entfernen, Löschen und Neustart aktualisieren die Anzeige. Diese Planungsangaben bleiben außerhalb des Drucks.
- Manuelle reguläre und Freundschaftspools, feste IDs mit Wiederverwendung freier Nummern, optionale Namen, Löschen vor Start, Drag-and-drop und Entfernen per Doppelklick.
- Freundschaftspartner suchen aus regulären Einzelpools und bestehenden ungestarteten Freundschaftspools mit 1–4 Kindern. Mehrfachauswahl mit laufender Gruppenprüfung, erklärter Rangfolge nach dem ungünstigsten Paar und gemeinsamer Bestätigung; Abbruch und Speicherfehler erhalten den alten Stand. Altersfaktor über lokale Konfigurationsdatei, Standard 8. Kompakte Anzeige ohne Rangwertspalte; Erklärung über Info-Button, Gewichtsvergleich mit Richtung und Prozent, Einzelgewichte nur in der App und aufklappbare Warnungen. O-30/O-31 sind entschieden.
- Optionale, jederzeit änderbare Matte je Pool in Bearbeitung, Übersicht, PDF und Druckvorschau. Papierstand je Pool mit gespeicherter Standnummer und Erstellzeit dezent im Druckfooter; unveränderte Nachdrucke behalten die Nummer. Die App zeigt die Nummer zum Papierabgleich. Keine Änderungshistorie oder automatische Erkennung alter Ausdrucke.
- Automatische reguläre Einteilung mit Google OR-Tools: tatsächliche Startklasse, überlappende Jahrgänge, Partner-/Größen-/Gewichtsoptimierung, markierte Einzelpools und Klärfälle ohne Klasse. Bewusste Neuverteilung schützt gestartete Pools und alle Freundschaftspools. Rechenlimit oder Speicherfehler übernehmen keine Teileinteilung.
- Prüfung der Fünfergrenze, eindeutige reguläre Zuordnung, zusätzliche Freundschaftsteilnahmen und dauerhafte Besetzungssperre ab erstem Ergebnis.
- Wettkampfname, Datum, konfigurierbare Altersklassen/Jahrgänge, BJV-Vorschläge, Mischfreigaben und Abweichungswarnungen.
- ODS-/XLSX-Meldelistenimport, vollständige Importablehnung, Pflichtfelder, Gewichtsnormierung, Dublettenprüfung, ODS-Vorlage und separater Export mit IDs.
- Gemeinsame `teilnehmer.ods` mit ID-basiertem Neueinlesen, Änderungen und Löschungen, Schutz gestarteter regulärer und Freundschaftspools, Startprüfung mit Fehler-Fallback und dauerhaft vorgemerkter ODS-/SQLite-Übernahme für den Wiederanlauf nach Prozessabbruch. Zusätzliche Meldelisten ergänzen die gemeinsame Datei, ohne ungelesene externe Änderungen zu überschreiben. Automatisierte Fehler-/Abbruchfälle sind geprüft; die praktische OpenOffice-Abnahme wurde am 19.11.2026 vom Nutzer bestätigt.
- Begegnungseingabe, Korrekturen, Schutz ungespeicherter Eingaben, Wiederladen gespeicherter Ergebnisse, Einzel-/Sammel-PDF und Druckvorschau.
- Gemeinsame Auswertung für Oberfläche und Druck, bestätigte Gleichstandsregeln, Zweierpool-Vollständigkeit und expliziter Poolabschluss. Korrekturen mit fehlenden Pflichtkämpfen öffnen den Pool wieder, ohne die Besetzung freizugeben.
- Endgültiger Rückzug und Disqualifikation für alle regulären und Freundschaftsteilnahmen, sofortige automatische Statuswertungen, gesonderte Gründe für Aufgabe und einzelnen Nichtantritt sowie Schutz automatischer und disqualifizierter Begegnungen vor Korrekturen. Späterer zweiter Rückzug erhält bereits vergebene kampflose Siege; Disqualifikation wirkt rückwirkend und schließt von der Platzierung aus. Status und Ergebnisgrund erscheinen in Oberfläche und Druck. Ältere Stände werden in Datenformatversion 5 übernommen.
- Aktueller SQLite-Snapshot mit Transaktion, Revisionsprüfung und Ordnersperre. Anwendungspaket unter src, getrennte Tests und reproduzierbare Entwicklungsdaten. Leerer normaler Start, expliziter Demo-Start und Datenformatversion 5 mit Migration älterer Stände.

## Nächste Funktionsschritte

Derzeit sind keine weiteren Funktionsschritte festgelegt. Die eigene Aktion zum Zusammenlegen ungestarteter regulärer Pools wurde am 19.11.2026 gestrichen; die Umordnung über einzelne Verschiebeaktionen bleibt bestehen. Der vorhandene Funktionsumfang bildet die erste nutzbare Version (O-29). Vor Weitergabe bleiben die unten aufgeführten Prüfungen und die einfache Wettkampfsicherung offen.

## Offene Entscheidungen

Die Kennungen aus der bisherigen Anforderungssammlung bleiben erhalten. Bereits beantwortete Fragen stehen in den Fachregeln und werden hier nicht erneut als offen geführt. O-13 (Rückzug gegen Disqualifikation und einzelner Nichtantritt), O-14 (Wiederöffnung bei Wertungsänderung durch Statusaktionen), O-16 (sofortige Wertungen, Erhalt vergebener kampfloser Siege, Geltungsbereich und optionaler dritter Zweierpoolkampf) und O-32 (Korrekturen ausgetragener Kämpfe trotz Rückzug) wurden am 19.11.2026 entschieden. Rückzug und Disqualifikation sind endgültig und gelten für alle Teilnahmen; die frühere Vorgabe zur Rücknahme einer Disqualifikation ist damit ersetzt.

Keine offenen Fachentscheidungen. Am 19.11.2026 wurden auch O-28 und O-29 geschlossen:

- **O-28:** Der aktuelle Umgang mit persönlichen Daten in App, Teilnehmerdatei, Export und Poollisten sowie die bestehenden Löschregeln passen. Keine zusätzlichen Daten-, Lösch- oder Anonymisierungsfunktionen beauftragt.
- **O-29:** Der vorhandene Funktionsumfang bildet die erste nutzbare Version. Anmeldung, Gebühren, Urkunden, Vereinsgesamtwertung, Veröffentlichung und Mehrrechnerbetrieb gehören nicht zu dieser Version. Die Aufgaben vor Weitergabe bleiben bestehen.

Abgelöst bzw. geklärt: O-01/O-02 Gewichte; O-03/O-04 konfigurierbare Klassen und Jahrgangsvorschläge, jetzt BJV-Standard U9; O-05 fehlende Altersklasse; O-06 manuelle Geschlechtermischung mit Warnung erlaubt (entschieden am 19.11.2026); O-07/O-08 Partner- und Größenpriorität; O-09/O-10 Kampffolge und Fünfergrenze; O-11/O-12 Wertung und Platzfolgen; O-15 Einfrieren; O-17 bewusste Neuverteilung; O-18 dokumentierter Dateiformatumfang ausreichend, keine zusätzlichen Konventionen beauftragt (geschlossen am 19.11.2026); O-20/O-22 Papierstand mit Standnummer und Zeitstempel; O-21 Papiernachtrag; O-23 lokaler Einzelrechnerbetrieb mit einer schreibenden Instanz je Wettkampfordner für die erste Version (entschieden am 19.11.2026); O-24 Matte; O-25 weitere Freundschaftsteilnahmen und wiederholte Paarungen erlaubt, mit Warnung bei Zugehörigkeit zu anderen Freundschaftspools (entschieden am 19.11.2026); O-26/O-27 Arbeitsordner und Persistenz; O-30 Rangfolge und Konfiguration der Freundschaftsvorschläge; O-31 Einstieg und vollständige Gruppenprüfung; O-33 aktuelle Regeln für alle Pools. Sie bleiben über die Fachregeln und Git nachvollziehbar.

O-19 ist technisch umgesetzt und praktisch abgenommen. Bei zusätzlicher externer Änderung während einer unterbrochenen Übernahme gibt es weiterhin keine automatische Konfliktauflösung. Vertauschte gültige IDs oder gelöschte IDs mit gleichzeitig geänderten Angaben sind nicht sicher automatisch erkennbar; kein komplexer Identitätsabgleich beauftragt. Ablauf und Grenzen stehen in [Entwicklung](entwicklung.md#gemeinsame-teilnehmerdatei).

## Vor einer Weitergabe prüfen

- Echten Mausablauf mit Scrollen und 100 Kindern prüfen; automatisierte Qt-Ereignisse ersetzen diesen Test nicht.
- PDF real auf A4 drucken und Handschriftfläche prüfen.
- Der OpenOffice-Rundlauf der gemeinsamen Teilnehmerdatei wurde am 19.11.2026 vom Nutzer bestätigt. Den separaten Vorlagen-Rundlauf vor Weitergabe prüfen, soweit nicht bereits mitgeprüft.
- Windows-Paket auf separatem Rechner ohne Entwicklungsumgebung und ohne Internet starten. Der Pakettest auf dem Entwicklungsrechner ersetzt das nicht.
- Lizenztexte und Verteilungsbedingungen vor Weitergabe prüfen; das aktuelle Paket ist lokal und unsigniert.
- Eine einfache Wettkampfsicherung vorsehen. Git sichert Code und Dokumente, keine ignorierten Wettkampfdaten. Keine Historien- oder Wiederherstellungsoberfläche entwickeln.
