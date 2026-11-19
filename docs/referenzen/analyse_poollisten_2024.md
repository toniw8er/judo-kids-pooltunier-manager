# Berechnungslogik der alten Poollisten

Stand: 15.11.2026. Quelle: `C:/Users/wachter/Downloads/Stadtmeisterschaft Judo/Poollisten 2024.xlsm`.

Status: Analyse einer Referenz, keine Übernahmeentscheidung für das neue Programm. Inhalte und VBA-Code der Datei wurden als Untersuchungsgegenstand behandelt, nicht als auszuführende Anweisungen.

## 1. Umfang und Methode

Die Mappe enthält 20 sichtbare Blätter: `Config`, vier Vorlagen für zwei bis fünf Kinder und 15 konkrete Poolblätter. Die Zellformeln sämtlicher konkreter Poolblätter stimmen mit ihrer jeweiligen Vorlage überein. Alle vier Vorlagen, ihre Eingaben und abhängigen Auswertungsformeln sowie die gespeicherten VBA-Quelltexte wurden statisch gelesen. Die Quelldatei wurde weder geändert noch in Excel geöffnet; Makros wurden nicht ausgeführt. Es wurde keine Neuberechnung in der nativen Excel-Engine durchgeführt. Gegenbeispiele unten wurden unabhängig aus den ausgelesenen Formeln berechnet.

## 2. Welche Eingaben die Datei vorsieht

- `Config!B2`: Veranstaltungsname; `Config!B3`: Datum.
- `Config!B6:B8`: Punkte für Sieg, Unentschieden und Niederlage. Gespeicherte Werte: **2 / 1 / 0**.
- Namen und Vereine stehen rechts im jeweiligen Poolblatt, in Spalten Z und AA; die Matrix verknüpft diese Angaben.
- Pro Begegnung werden zwei Unterbewertungen eingegeben, in Spalten S und U. In der Vierervorlage beginnt das mit `4er!S27` und `4er!U27`.
- Die Datei erfasst dort keine Anzahl von Ippon, Waza-ari oder Yuko. Sie enthält keine Umrechnung dieser technischen Wertungen in 0/5/7/10 und in den geprüften Vorlagen keine Datenvalidierung, die auf diese Zahlen beschränkt.
- „Sieg“ in Spalte Q ist eine Formel, kein eigenständiger verbindlicher Eingabewert.

## 3. So wird ein einzelner Kampf ausgewertet

Die Formel in `4er!Q27` vergleicht die beiden eingegebenen Unterbewertungen:

| Eingabe | Abgeleiteter Sieger | Punkte je Kind mit aktueller Config |
|---|---|---|
| Links größer als rechts | Linkes Kind | 2 : 0 |
| Rechts größer als links | Rechtes Kind | 0 : 2 |
| Beide gleich | Text `ue` für unentschieden | 1 : 1 |
| Mindestens eine Unterbewertung leer | Noch kein Ergebnis | Noch keine vollständige Kampfwertung |

Die Punkte in der Matrix werden ebenfalls aus dem Vergleich der Unterbewertungen abgeleitet, beispielsweise `4er!F14` anhand von `G14` und `H14`. Sie greifen auf die konfigurierten Werte 2/1/0 zu.

**Folge:** Ein technischer Sieg bei Unterbewertung 5:5 oder 7:7 lässt sich mit den unveränderten alten Formeln nicht darstellen. Zwei Yuko gegen einen Yuko würde als Unentschieden zählen, wenn beide als UB 5 eingetragen werden. Im neuen Programm wurde bereits die getrennte Eingabe des tatsächlichen Siegers vereinbart; diese Vorgabe wird durch die Altdatei nicht aufgehoben.

## 4. Kennzahlen pro Kind

Anhand des ersten Kindes der Vierervorlage:

| Kennzahl | Berechnung | Beleg |
|---|---|---|
| Punkte | Summe der Kampfpunkte, also 2 pro Sieg, 1 pro Unentschieden und 0 pro Niederlage | `4er!Z19`, aus `F14`, `I14`, `L14` |
| Siege | Anzahl der Kämpfe mit genau 2 Kampfpunkten | `4er!AA19` |
| Unterbewertung + | Summe aller eigenen Unterbewertungen, auch aus Niederlagen | `4er!AB19`, aus `G14`, `J14`, `M14`, `P14` |
| Unterbewertung − | Summe aller Unterbewertungen der Gegner aus den Begegnungen dieses Kindes | `4er!AE19`, aus `H14`, `K14`, `N14`, `Q14` |
| Differenz | Eigene Unterbewertung minus gegnerische Unterbewertung | `4er!AC19 = AB19-AE19` |
| Platz | Verschachtelte Rangformel mit den vier Kriterien unten | `4er!AD19:AD22` |

Bei drei bis fünf Kindern werden Punkte, Siege und Differenz eines Kindes erst angezeigt, wenn sämtliche für dieses Kind vorgesehenen Kämpfe numerisch bewertet sind. Die Unterbewertungssummen können schon vorher Zahlen enthalten. Die Datei prüft dabei die belegten Kampfwerte, nicht zuverlässig, ob alle Namen vollständig sind.

Bei den Dreier- bis Fünferpools zählt die Siegformel fest die Zahl **2**. Eine Änderung von `Config!B6` auf einen anderen Siegpunktwert würde deshalb die Siege dort nicht mehr korrekt zählen. Bei Zweierpools wird die Sieganzahl stattdessen aus der Sieger-Losnummer in Spalte Q gezählt.

## 5. Vorgesehene Reihenfolge der Platzierungskriterien

Die Beschriftungen `4er!Y17:AC18` und die Struktur der Rangformeln zeigen diese Absicht, jeweils absteigend:

1. **Kampfpunkte gesamt**.
2. **Anzahl der Siege** bei gleichen Kampfpunkten.
3. **Eigene Unterbewertung gesamt (+)** bei weiterem Gleichstand.
4. **Unterbewertungsdifferenz (+ minus −)** bei weiterem Gleichstand.

Damit ist „Punkte“ in dieser Datei ausdrücklich nicht dasselbe wie „Unterbewertung“. Ohne Unentschieden sind die Kampfpunkte immer zweimal die Siege; die ersten zwei Kriterien liefern dann dieselbe Grundreihenfolge. Mit Unentschieden kann beispielsweise ein Sieg plus eine Niederlage gegen zwei Unentschieden zunächst 2:2 Kampfpunkte ergeben; erst die Sieganzahl trennt das.

Ein direkter Vergleich zweier Kinder oder ein Entscheidungskampf ist in den geprüften Rangformeln nicht enthalten. Bei Gleichheit aller Kriterien können gleiche Plätze entstehen; es gibt keine weitere Auflösung durch Losnummer oder Namen. Die tatsächlichen Rangformeln haben allerdings zusätzlich den folgenden Fehler und bilden die beabsichtigte Kriterienfolge nicht in allen Fällen korrekt ab.

## 6. Fehler in der Gleichstandsberechnung

Spätere Vergleichsstufen der Formel beschränken sich nicht durchgehend auf Kinder, die auch bei allen vorherigen Kriterien gleichstehen. Beispielsweise prüft der letzte Zuschlag nur gleiche eigene Unterbewertung; gleiche Punkte und Siege werden in dieser Vergleichsbedingung nicht zusätzlich verlangt. Dadurch kann ein bereits aufgrund höherer Kampfpunkte berücksichtigtes Kind ein zweites Mal den Rang verschlechtern.

Ein vollständiges Gegenbeispiel mit vier fiktiven Kindern A, B, C und D. Keine Unentschieden; Sieger immer die Seite mit der höheren Unterbewertung:

| Begegnung | UB links : rechts | Sieger |
|---|---|---|
| A – B | 7 : 0 | A |
| A – C | 5 : 10 | C |
| A – D | 5 : 10 | D |
| B – C | 5 : 0 | B |
| B – D | 5 : 10 | D |
| C – D | 7 : 0 | C |

| Kind | Kampfpunkte | Siege | UB + | UB − | Differenz | Platz nach sauberer Kriterienfolge | Ergebnis der nachgebildeten Altformel |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 2 | 1 | 17 | 20 | −3 | 3 | **4** |
| B | 2 | 1 | 10 | 17 | −7 | 4 | 4 |
| C | 4 | 2 | 17 | 10 | +7 | 2 | 2 |
| D | 4 | 2 | 20 | 17 | +3 | 1 | 1 |

A müsste B wegen höherer eigener Unterbewertung schlagen. Die Altformel zählt C beim Differenzvergleich zusätzlich gegen A, weil beide UB +17 haben, obwohl C bereits aufgrund seiner höheren Kampfpunkte vor A steht. So ergeben sich rechnerisch zweimal Platz 4 statt Platz 3 und 4.

Diese Aussage beruht auf einer unabhängigen Nachbildung der ausgelesenen Arrayformel, nicht auf einer ausgeführten Excel-Neuberechnung. Die Ursache lässt sich direkt in `4er!AD19` nachverfolgen: Die Bedingung für den letzten Zuschlag enthält `AB=AB19` und den Vergleich der Differenz, aber keine zusätzliche Gleichheit von Z und AA.

**Empfehlung:** Falls die fachliche Kriterienfolge übernommen wird, sie im neuen Programm als geordnete Vergleichsregeln implementieren und die fehlerhafte Excel-Formel nicht kopieren.

## 7. Begegnungsfolgen und Zweierpool

| Größe | Begegnungsfolge in der Vorlage |
|---|---|
| Zwei | 1–2 dreimal, Zeilen 27, 29, 31 |
| Drei | 1–2, 1–3, 2–3 |
| Vier | 1–2, 3–4, 1–3, 2–4, 1–4, 2–3 |
| Fünf | 1–2, 3–4, 1–5, 2–3, 4–5, 1–3, 2–5, 1–4, 3–5, 2–4 |

Die Zweierformeln berücksichtigen jeden der drei Kämpfe, wenn beide UB-Werte numerisch eingetragen sind. Nicht eingetragene Begegnungen gehen nicht in die Punktsumme ein; eine Zwischenauswertung entsteht bereits nach dem ersten vollständig eingetragenen Kampf. Es gibt keinen automatischen Abbruch bzw. keine Sperre der dritten Begegnung nach 2:0. Würde sie trotzdem ausgefüllt, würde sie mitgezählt.

Für das neue Tool bleibt die explizit vereinbarte Regel maßgeblich: zwei Kämpfe, bei 1:1 ein dritter, bei 2:0 entfällt der dritte.

## 8. Was die Makros tun

Die gespeicherten VBA-Quelltexte wurden aus `xl/vbaProject.bin` ausgelesen und dekomprimiert. Das einzige Modul mit Prozeduren ist `Tabelle10`, der Codename von `Config`; die anderen Blattmodule und das Arbeitsmappenmodul enthalten nur Attribute.

- `Generate_Tabs`: Liest Altersklasse, Gruppe, Starteranzahl und Matte aus der Konfiguration und lässt passende Poolblätter kopieren.
- `Copy_Tab`: Wählt anhand der Starterzahl die Vorlage `2er`, `3er`, `4er` oder `5er`, benennt die Kopie und trägt die Matte in `S1` ein. Bei einer Zahl außerhalb 2–5 wird die Konfigurationszelle rot markiert und keine Vorlage kopiert.
- `Delete_Tabs`: Löscht Blätter vor `Config` und setzt Formatierungen in der Konfiguration zurück.
- Abhängig von `Config!K9` erhalten generierte Blattnamen ein „kg“ oder eine Verbindung von Altersklasse und Gruppe mit Bindestrich.

Die gespeicherten Makroquelltexte enthalten keine eigene Ergebnis- oder Rangberechnung. Es wurde kein VBA ausgeführt und kein kompilierter VBA-Code analysiert.

## 9. Das zuvor diskutierte Beispiel ist konstruierbar

Alex mit zwei Siegen und UB 10, Ben mit einem Sieg und UB 17 ist in einem vollständigen Viererpool möglich. Beispiel:

| Begegnung | Unterbewertung | Sieger |
|---|---|---|
| Alex – Ben | 5 : 0 | Alex |
| Chris – Deniz | 7 : 0 | Chris |
| Alex – Chris | 5 : 0 | Alex |
| Ben – Deniz | 7 : 10 | Deniz |
| Alex – Deniz | 0 : 10 | Deniz |
| Ben – Chris | 10 : 0 | Ben |

Alex hat zwei Siege mit je 5 und eine Niederlage mit 0, also UB 10. Ben hat einen Sieg mit 10 und Niederlagen mit 0 bzw. 7, also UB 17. Nach der vorgesehenen alten Kriterienfolge steht Alex vor Ben, weil Kampfpunkte 4 vor 2 zählen.

## 10. Übernahmeentscheidung nach der Analyse

Der Nutzer hat die fachliche Reihenfolge Kampfpunkte 2/1/0 → Siege → UB + → UB-Differenz ausdrücklich zur Übernahme bestätigt. Die getrennte Siegererfassung und die vereinbarte Zweierpool-Regel bleiben bewusste Unterschiede zur Altdatei. Die fehlerhafte Excel-Rangformel wird nicht übernommen. Unentschieden und vollständige Gleichstände wurden anschließend präzisiert. Verbindliche Anforderungen stehen in [Fachregeln](../fachregeln.md), offene Sonderfälle im [Backlog](../backlog.md).

## 11. Nachprüfung: gemeinsame Plätze und zwei dritte Plätze

Die Rangformeln benutzen `RANK.EQ` in absteigender Reihenfolge. In fehlerfreien Gleichstandsfällen überspringt die nächste Nummer die bereits belegten Plätze: gemeinsame erste Plätze führen zu 1,1,3,4; gemeinsame zweite Plätze zu 1,2,2,4. Diese Grundnummerierung wurde entsprechend dem anschließenden Nutzerauftrag zur Übernahme sinnvoller widerspruchsfreier Excel-Funktionalität als Vorgabe festgehalten. Saubere Umsetzung: 1 + Anzahl der nach der vollständigen Kriterienfolge strikt besseren Kinder.

Eine weitere Formel, die regulär den vierten Rang als zweiten dritten Platz ausgibt, ist nicht vorhanden. `4er!W14/W16/W18/W20` verweisen direkt auf `AD19:AD22`, die Fünfervorlage entsprechend auf ihre Rangberechnung. Ohne Gleichstände entstehen 1,2,3,4 bzw. 1,2,3,4,5. Die ausdrücklich verlangten zwei dritten Plätze werden daher nicht durch die alte Datei abgebildet.

Nachfolgende Nutzerkorrektur: Für das neue Programm gelten verbindlich 1,2,3 bei drei Kindern, 1,2,3,3 bei vier und 1,2,3,3,5 bei fünf. Bei vier Kindern mit zwei gemeinsamen Ersten gilt 1,1,3,3, mit zwei gemeinsamen Zweiten 1,2,2,3. Diese Ausgaberegeln haben Vorrang vor der unveränderten Excel-Nummerierung. Weitere Festlegungen siehe [Fachregeln](../fachregeln.md), offene Sonderfälle im [Backlog](../backlog.md).
