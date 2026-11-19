"""Zentrale, reproduzierbare Entwicklungsdaten; keine automatische Poolempfehlung."""
from uuid import NAMESPACE_URL, uuid5

from stadtmeisterschaft.domain import Participant, Pool, Tournament


def demo(count: int = 40, event_year: int = 2026) -> Tournament:
    if count not in (10, 40, 100):
        raise ValueError("Testdaten sind für 10, 40 oder 100 Kinder verfügbar.")
    names = [("Mia", "Müller"), ("Ben", "Öztürk"), ("Lena", "Großmann"),
             ("Noah", "Schäfer"), ("Emma", "Wagner"), ("Paul", "Fischer"),
             ("Lea", "Bauer"), ("Finn", "Weiß"), ("Ella", "Hoffmann"), ("Max", "König")]
    # Unterschiedliche Altersgruppen mit nahen Gewichten sowie bewussten Randfällen.
    # Das sind feste Testgruppen, keine automatische fachliche Pooleinteilung.
    groups = [(6, 17500), (8, 23000), (10, 30000), (12, 39000),
              (14, 51000), (16, 65000), (7, 21000), (11, 35500)]
    year = event_year
    people = [Participant(str(uuid5(NAMESPACE_URL, f"stadtmeisterschaft/demo/{count}/{event_year}/{i}")), names[i % 10][0],
                          names[i % 10][1] + (f" {i + 1}" if count > 10 else ""),
                          "Judoclub Beispielstadt – Abteilung Kinder und Jugend",
                          year - groups[(i // 5) % len(groups)][0] - [-1, 0, 0, 1, 0][i % 5],
                          "M" if i % 2 else "F",
                          groups[(i // 5) % len(groups)][1] + [0, 400, 900, 1400, 2200][i % 5]
                          + (i // 40) * 100)
              for i in range(count)]
    # Fünf Kinder bleiben in größeren Testständen ohne Pool zum Zuordnen übrig.
    sizes = [3, 5, 2] if count == 10 else [5] * (max(0, count - 5) // 5)
    pools, offset = [], 0
    for i, size in enumerate(sizes):
        pools.append(Pool(f"Pool {i + 1:02}", [p.id for p in people[offset:offset + size]]))
        offset += size
    return Tournament(people, pools, name="Stadtmeisterschaft · Entwicklung",
                      event_date=f"{event_year}-11-18", next_pool_number=len(pools) + 1, is_demo=True)
