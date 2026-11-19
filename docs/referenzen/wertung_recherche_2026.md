# Judo-Wertung 2026: Recherche und Rechenbeispiel

Aktuelle Anforderungen stehen in [Fachregeln](../fachregeln.md), offene Fälle im [Backlog](../backlog.md). Diese Notiz erhält die Recherche und ihre damaligen Grenzen.

Stand: 15.11.2026. Arbeitsnotiz zur Anforderungsklärung, keine vollständig bestätigte Wettkampfregelkonfiguration.

## Rechercheergebnis und Grenzen

Die offiziellen DJB-Kampfregeln 2026, überarbeitet am 15.03.2026, nennen in Artikel 4 auf den gedruckten Seiten 10–11:

| Technische Wertung | Klassische Unterbewertung |
|---|---:|
| Ippon | 10 |
| Waza-ari | 7 |
| Yuko | 5 |
| Zwei Waza-ari, zusammen Ippon | 10, nicht 14 |

Quelle: [DJB-Kampfregeln 2026](https://www.judobund.de/fileadmin/user_upload/judobund.de/Downloads/Regeln_und_Ordnungen/2026_neue_Ordnungen/2026_03_DJB-Kampfregeln_ueberarbeitet.pdf). Die Werte und die Zusammenfassung zweier Waza-ari zu Ippon konnten anhand der von der Websuche erfassten PDF-Abschnitte geprüft werden. Die vollständige PDF ließ sich im Webleser wegen ihrer Größe nicht öffnen. Die aktuelle Publikation ist auch im [offiziellen DJB-Downloadcenter](https://www.judobund.de/service/download-center/regeln-und-ordnungen) gelistet.

Die Unterbewertung ist von der Anzeige der technischen Wertungen auf dem Scoreboard zu unterscheiden. Die Zahlen 10/7/5 sind keine frei addierbaren Aktionspunkte: Insbesondere ergibt der zweite Waza-ari Ippon und keine 14 Unterbewertungspunkte. Die Summe der Unterbewertungen über mehrere Begegnungen ist wiederum eine getrennte Größe.

Der Nutzer möchte als endgültiges Kampfergebnis den Sieger und zwei Unterbewertungen eintragen, eine für jedes Kind, keine vollständige chronologische Erfassung aller Aktionen. Er hat ausdrücklich klargestellt, dass auch Verlierer Unterbewertungspunkte erhalten. Das Datenmodell darf daher die Unterbewertung des Verlierers nicht automatisch auf null setzen.

Inzwischen geklärter Zahlenwiderspruch: Der Nutzer hat Waza-ari mit 7 und Yuko mit 5 präzisiert. Damit ergibt sein Beispiel Ben mit Ippon gegen Dennis mit Waza-ari im gewünschten Tool 10:7, Sieger Ben. Die vorherige Angabe 10:5 ist durch diese Präzisierung überholt.

## Festgelegte Turnierwertung nach erneuter Recherche und Nutzerpräzisierung

- Keine technische Wertung: UB 0.
- Ein oder mehrere Yuko ohne höhere Wertung: UB 5.
- Ein Waza-ari, auch mit zusätzlichen Yuko, ohne Ippon: UB 7.
- Ippon oder zwei Waza-ari: UB 10.
- Diese Umrechnung gilt für beide Kinder, auch den Verlierer. Erst über mehrere Begegnungen werden die UB-Werte summiert.
- Sieger wird separat eingegeben. Beispiel: Zwei Yuko gegen einen Yuko ergibt technisch einen Sieger, aber UB 5:5. Ein Waza-ari plus Yuko gegen ein Waza-ari ohne Yuko ergibt ebenfalls einen technischen Sieger bei UB 7:7. Der komprimierte UB-Wert kann den Sieger daher nicht immer bestimmen.

Die erneute Recherche bestätigt 7/5 und zwei Waza-ari als Ippon anhand der offiziellen DJB-Regeln 2026. Siehe dieselbe oben verlinkte Quelle, Artikel 4. Die Regel „höchste Kategorie für beide Kinder“ ist als explizite Nutzeranforderung festgehalten; sie wird nicht als vollständig verifizierte bayerische Kinder-Sonderregel ausgegeben.

Die mitgelieferte Bayernliga-Männer-Liste 2026 wurde visuell geprüft: Zeile 8 zeigt Waza-ari plus Yuko mit UB 7, Zeile 1 zwei Waza-ari mit UB 10. Die Verlierer erhalten in dieser Ligavorlage UB 0 trotz teilweise erzielter Wertungen. Das ist ein Unterschied zur ausdrücklichen Nutzeranforderung, Verlierer-Unterbewertungen im Kinderturnier zu berücksichtigen; diese wird beibehalten. Bildquelle: `C:/Users/wachter/AppData/Local/Temp/codex-clipboard-83a207a9-cee6-4612-a7e9-499a22eee4d1.png`.

Ergänzende offizielle Vergleichsquelle: [NWJV-Hinweise für Ligamannschaften und Kampfrichter ab 2026](https://www.nwjv.de/fileadmin/2026/dokumente/ligabereich/Hinweise_fuer_KR_und_Vereine.pdf) nennen 5/7/10 und ausdrücklich 0/0 für Verlierer in ihren Ligen. Diese fremde Ligaregel wird nicht als Kinderregel für Bayern übernommen.

### Bayerische Kinder-Sonderregeln nicht abschließend verifiziert

Die [BJV-Sportordnung](https://www.bayernjudo.de/verband/downloads-menue/ordnungen-und-regelwerke/ordnungen/sportordnung) ist mit dem Dateinamen `SpO_20260208.pdf` und Aktualisierung vom 13.02.2026 gelistet. Sowohl Download als auch Dokumentanzeige führten beim Recherchezugriff auf eine Anmeldeseite. Der aktuelle Inhalt wurde daher nicht gelesen und wird nicht als geprüft ausgegeben.

Der BJV beschreibt im [Jugendgesamtkonzept](https://www.bayernjudo.de/ressorts/jugend/jugendinfos/jugendgesamtkonzept) mehrere altersgerechte Turnierformen. Eine aktuelle, öffentlich lesbare Fassung mit eindeutigem Geltungsstand für 2026 ließ sich dort nicht verifizieren. Historische Kinder-Additionssysteme und Regeln anderer Landesverbände sind keine ausreichende Grundlage, um 10/7/5 für sämtliche bayerischen Kinderklassen verbindlich festzulegen. Auch die genaue Rangfolge der Pool-Platzierungskriterien und die Unterbewertung des Verlierers bleiben unbestätigt.

Die geprüfte [DJB-Wettkampfordnung, Stand Dezember 2025](https://www.judobund.de/fileadmin/user_upload/judobund.de/Downloads/Regeln_und_Ordnungen/2026_neue_Ordnungen/2025-DJB-WKO_final.pdf) und die über die offizielle Jugendregelseite verlinkte Übersicht [Jugendregelungen 2025-08](https://www.judobund.de/fileadmin/user_upload/judobund.de/Downloads/Regeln_und_Ordnungen/Jugendregelungen_2025-08_deu.pdf) schließen diese Verifikationslücke für die bayerische Kinder-Poolwertung nicht.

Folgerung für die Planung: Noch keine identische Wertung für U8 bis U18 festschreiben. Die endgültige Zuordnung der Wertungsregeln zu Altersklassen sowie die vollständigen Platzierungskriterien bleiben fachlich zu bestätigen. Die bestehenden expliziten Nutzerregeln, insbesondere die Zweierpool-Serie, werden nicht durch die Recherche überschrieben.

## Fiktives Beispiel: Viererpool U13

Pool `4er_1`, Kinder Alex, Ben, Chris und Deniz. Jeder kämpft einmal gegen jeden.

**Explizite Beispielannahmen:** Sieger erhält einen Siegpunkt und die ausgewiesene Unterbewertung, Verlierer jeweils 0/0. Die Verlierer haben in diesem Beispiel keine technischen Wertungen erzielt. Diese Nullwerte sind ausdrücklich keine allgemeine Regel für Niederlagen: Der Nutzer hat inzwischen bestätigt, dass Unterbewertungen beider Kinder erfasst werden müssen. Platzierung zunächst nach Anzahl der Siege, danach nach Summe der Unterbewertungen. Das ist eine Demonstration des gewünschten Bedienablaufs, keine Behauptung, dass damit alle aktuellen BJV-Poolregeln umgesetzt wären.

| Kampf | Begegnung | Sieger | Entscheidende Wertung | Unterbewertung Sieger |
|---|---|---|---|---:|
| 1 | Alex – Ben | Alex | Waza-ari | 7 |
| 2 | Chris – Deniz | Chris | Waza-ari | 7 |
| 3 | Alex – Chris | Alex | Yuko | 5 |
| 4 | Ben – Deniz | Ben | Ippon | 10 |
| 5 | Alex – Deniz | Alex | Zwei Waza-ari, zusammen Ippon | 10 |
| 6 | Ben – Chris | Ben | Ippon | 10 |

Die Eingabe je Begegnung soll so aussehen: Sieger auswählen und Unterbewertungen beider Kinder eingeben. Beispiel Kampf 1 unter den obigen Annahmen: `Sieger Alex; Unterbewertung Alex 7; Unterbewertung Ben 0`. Den Siegpunkt berechnet das Programm aus der Siegerauswahl. Eine automatische Erkennung oder Bewertung der technischen Aktionen ist dafür nicht erforderlich und nicht beauftragt.

### Poolmatrix

Zellen zeigen `Sieg / Unterbewertung` aus Sicht der Person in der Zeile. Die Diagonale ist gesperrt.

| Kind | Gegen Alex | Gegen Ben | Gegen Chris | Gegen Deniz | Siege | Summe Unterbewertung | Platz im Beispiel |
|---|---|---|---|---|---:|---:|---:|
| Alex | — | 1 / 7 | 1 / 5 | 1 / 10 | 3 | 22 | 1 |
| Ben | 0 / 0 | — | 1 / 10 | 1 / 10 | 2 | 20 | 2 |
| Chris | 0 / 0 | 0 / 0 | — | 1 / 7 | 1 | 7 | 3 |
| Deniz | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 | 0 | 4 |

Rechenkontrolle: sechs Begegnungen, insgesamt sechs Siege, Unterbewertungssumme 7+7+5+10+10+10 = 49; dieselbe Summe ergibt 22+20+7+0. Das Beispiel benötigt keinen Gleichstandsentscheid. Gleichstände, Wertungen beider Kinder, Nichtantritt, Disqualifikation und Aufgabe sind separat zu definieren.

## Nächste fachliche Klärung

Die beidseitige Unterbewertung und Werte 0/5/7/10 sind bestätigt. Vollständige Platzierungsregeln, technischer Gleichstand, Strafen und weitere Sonderfälle bleiben zu klären. Das obige historische Beispiel mit Verlierern ohne Wertungen ist durch die folgenden zusätzlichen Fälle zu ergänzen, nicht als allgemeine Verlierer-Nullregel zu lesen.

| Technische Wertung A | Technische Wertung B | Sieger | UB A:B im gewünschten Tool |
|---|---|---|---|
| Ippon | Ein Waza-ari | A | 10:7 |
| Ein Waza-ari und ein Yuko | Zwei Yuko | A | 7:5 |
| Zwei Yuko | Ein Yuko | A bei Zeitablauf | 5:5 |
| Ein Waza-ari und ein Yuko | Ein Waza-ari ohne Yuko | A bei Zeitablauf | 7:7 |

## Bezeichnungen auf Poollisten

Aus dem Technikvergleich übernommen, Recherche vom 16.11.2026: Die [DJB-Kampfregeln März 2026](https://www.judobund.de/fileadmin/user_upload/judobund.de/Downloads/Regeln_und_Ordnungen/2026_neue_Ordnungen/2026_03_DJB-Kampfregeln_ueberarbeitet.pdf) nennen Erstaufgerufener Weiß und Zweitaufgerufener Blau. Der [Judo-Verband Rheinland](https://www.judo-rheinland.de/index.php/aktuelles/menverband/453-hiweise-zu-den-judogi-regeln-anlaesslich-der-swdt-em-u15-u21) erläutert Zusatzgürtel bei zwei weißen Judogi für U15 bis U21. Das ist keine allgemeine Übernahme lokaler Nachwuchsvorgaben. Eine undatierte [BJV-FAQ](https://www.bayernjudo.de/?id=126&view=article) nennt abweichend Erstgenannter rot / Zweitgenannter weiß; ihre Aktualität wurde nicht belegt.

Für die App verwenden wir deshalb die verständlichen Bezeichnungen „Erstgenannte/r“ und „Zweitgenannte/r“. Reihenfolge und Ergebniseingabe bleiben damit auch im Schwarz-Weiß-Druck eindeutig, ohne eine lokale Gürtelfarbe festzuschreiben. Diese Bezeichnung trifft keine zusätzliche sportliche Wertungsentscheidung.
