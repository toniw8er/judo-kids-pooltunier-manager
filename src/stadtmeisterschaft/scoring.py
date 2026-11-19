"""Gemeinsame Wertung für Oberfläche und Druck; nur gespeicherte Ergebnisse."""
from dataclasses import dataclass

from .domain import Pool


@dataclass
class Standing:
    participant_id: str
    points: int = 0
    wins: int = 0
    ub_for: int = 0
    ub_against: int = 0
    place: int | None = None

    @property
    def difference(self) -> int:
        return self.ub_for - self.ub_against

    @property
    def rank_key(self) -> tuple[int, ...]:
        return self.points, self.wins, self.ub_for, self.difference


def assign_places(rows: list[Standing]) -> None:
    for row in rows:
        place = 1 + sum(other.rank_key > row.rank_key for other in rows)
        row.place = 3 if place == 4 else place


def evaluate_pool(pool: Pool, *, disqualified: set[str] = frozenset()) -> tuple[list[Standing], dict[tuple[str, str], tuple[int, int]]]:
    rows = {pid: Standing(pid) for pid in pool.members}
    matrix = {}
    for number, (a, b) in enumerate(pool.fight_order, 1):
        result = pool.results.get(str(number))
        if result is None:
            continue
        first, second = pool.members[a - 1], pool.members[b - 1]
        for pid, opponent, ub, against, won in [
            (first, second, result.first, result.second, result.outcome == "1:0"),
            (second, first, result.second, result.first, result.outcome == "0:1"),
        ]:
            points = 0 if result.zero_points else 2 if won else int(result.outcome == "0:0")
            row = rows[pid]
            row.points += points
            row.wins += int(won)
            row.ub_for += ub
            row.ub_against += against
            previous = matrix.get((pid, opponent), (0, 0))
            matrix[pid, opponent] = previous[0] + points, previous[1] + ub
    result_rows = list(rows.values())
    if pool.ready_to_complete:
        assign_places([row for row in result_rows if row.participant_id not in disqualified])
    return result_rows, matrix
