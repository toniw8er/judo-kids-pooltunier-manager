# Jahrgangsvorschläge für die Wettkampfkonfiguration

Aktuelle Anforderungen stehen in [Fachregeln](../fachregeln.md), der technische Aufbau in [Entwicklung](../entwicklung.md).

Stand: 18.11.2026. Nutzerauftrag: wiederkehrende Altersklassen/Jahrgänge vorausfüllen, weiterhin bearbeitbar halten.

## Quellen und Berechnung

Die [DJB-Wettkampfordnung, Stand Dezember 2025](https://www.judobund.de/fileadmin/user_upload/judobund.de/Downloads/Regeln_und_Ordnungen/2026_neue_Ordnungen/2025-DJB-WKO_final.pdf), Abschnitte 3.1.1 und 3.1.2, beschreibt Altersklassen und den jahresbezogenen Stichtag. Entscheidend ist das im Kalenderjahr erreichte Alter, nicht das Alter am Veranstaltungstag.

Maßgeblich ist auf ausdrücklichen Nutzerwunsch die [BJV-Übersicht „Alters- und Gewichtsklassen 2026“](https://www.bayernjudo.de/fuer-vereine/jahrespost/jahrespost-2026/alters-und-gewichtsklassen-2026) des **Bayerischen Judo-Verbandes**. Das über „Anzeigen“ öffentlich zugängliche Original-PDF wurde am 18.11.2026 geprüft; Dokumenttitel „Alters- und Gewichtsklassen im BJV und DJB 2026“, interner Stand 08.12.2025. Nicht mit dem ebenfalls BJV abgekürzten Brandenburgischen Judo-Verband verwechseln.

Für Einzelwettkämpfe stimmen U11–U18 mit der bisher verwendeten NWJV-Vorlage überein. Die jüngste BJV-Klasse ist jedoch **U9 mit 7–8 Jahren**, 2026 also 2018–2019. Die frühere örtliche U8-Vorlage (6–7 Jahre, 2019–2020) ist keine BJV-Standardklasse und wird nicht mehr vorgeschlagen. Bereits gespeicherte U8-Konfigurationen werden nicht automatisch umbenannt oder geändert.

Die BJV-Übersicht erlaubt gemischte Begegnungen in U9/U11/U13 bei ausdrücklicher Freigabe in der Ausschreibung. Die Software setzt weiterhin kein Häkchen automatisch. Die frei bearbeitbare Geschlechterkonfiguration und die bisherige Warnlogik werden mit dieser Quellenumstellung nicht zu einer vollständigen Durchsetzung aller BJV-Regeln erweitert.

Für Veranstaltungsjahr Y und Alter von a bis b gilt: Jahrgänge Y−b bis Y−a, jeweils einschließlich. Überlappungen sind beabsichtigt.

| Klasse | Alter in der Vorlage | Jahrgänge 2026 |
|---|---|---|
| U9 | 7–8 | 2018–2019 |
| U11 | 8–10 | 2016–2018 |
| U13 | 10–12 | 2014–2016 |
| U15 | 12–14 | 2012–2014 |
| U18 | 15–17 | 2009–2011 |

## Verhalten in der App

„Altersklassen und Jahrgänge vorschlagen“ ergänzt die fehlenden BJV-Klassen U9/U11/U13/U15/U18 und leere Jahrgangsfelder anhand des Veranstaltungsdatums. Ein bekannter Klassenname, etwa U13, füllt ein leeres Jahrgangsfeld auch beim manuellen Anlegen aus. Bestehende Jahrgänge und Freigaben für gemischte Gruppen werden nicht überschrieben. Vorschläge setzen für neue Klassen keine Freigabe für gemischte Gruppen voraus; das entscheidet der Organisator.

Unveränderte, in der geöffneten Maske erzeugte Vorschläge folgen einer Änderung des Veranstaltungsjahres. Manuell bearbeitete und zuvor gespeicherte Werte bleiben erhalten. Änderungen werden erst mit „Speichern“ übernommen. Es erfolgt keine Online-Abfrage im laufenden Programm und keine automatische Neuverteilung von Pools. Die Konstanten liegen getrennt von der Oberfläche in `src/stadtmeisterschaft/age_class_defaults.py`.

Die Vorlage erspart Tipparbeit; sie ersetzt die jeweilige Ausschreibung nicht. Abweichende Klassen und Jahrgänge bleiben frei eintragbar.

Die Umstellung ändert ausschließlich die Standardvorschläge. Bei einem gespeicherten Wettkampf mit örtlicher U8 legt die Vorschlagsaktion zusätzlich die fehlende U9 an; eine nicht benötigte Klasse muss der Organisator bewusst entfernen. Vorhandene Jahrgänge werden weiterhin nicht überschrieben.
