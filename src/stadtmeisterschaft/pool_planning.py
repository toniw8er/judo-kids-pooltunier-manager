"""Reguläre Pools als Constraint-Modell für Google OR-Tools CP-SAT."""
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .domain import AgeClass, Participant, RuleError


@dataclass(frozen=True)
class PlannedPool:
    members: tuple[str, ...]
    age_class: str


def plan_pools(people: list[Participant], classes: list[AgeClass], *,
               time_limit: float = 15) -> tuple[list[PlannedPool], list[str]]:
    """Jeder Pool wird durch sein leichtestes Kind repräsentiert.

    Keine Aufzählung aller Fünfergruppen. Die ersten drei Ziele sind ganzzahlig
    exakt; relative Gewichtsspannen sind das abschließende Fließkommaziel.
    Nur nachgewiesene Optima übernehmen; Eingaben werden niemals verändert.
    """
    classes = sorted(classes, key=lambda c: (c.name.casefold(), c.name))
    ordered = sorted(people, key=lambda p: (p.weight_grams, p.id))
    missing = [p.id for p in ordered if not any(p.birth_year in c.years for c in classes)]
    missing_set = set(missing)
    people = [p for p in ordered if p.id not in missing_set]
    if not people:
        return [], missing
    # Unabhängige Partnergruppen getrennt an denselben Solver übergeben.
    neighbours = [{j for j, q in enumerate(people)
                   if max(p.weight_grams, q.weight_grams) * 10 <= min(p.weight_grams, q.weight_grams) * 11
                   and any(p.birth_year in c.years and q.birth_year in c.years
                           and (c.mixed or p.gender == q.gender) for c in classes)}
                  for p in people]
    remaining, components = set(range(len(people))), []
    while remaining:
        component, pending = set(), {min(remaining)}
        while pending:
            component.update(pending)
            pending = set.union(*(neighbours[i] for i in pending)) - component
        remaining.difference_update(component)
        components.append(sorted(component))
    if len(components) > 1:
        result = []
        for component in components:
            groups, _ = plan_pools([people[i] for i in component], classes, time_limit=time_limit)
            result.extend(groups)
        return result, missing
    common_class = any(all(p.birth_year in c.years for p in people)
                       and (c.mixed or len({p.gender for p in people}) == 1) for c in classes)
    model = cp_model.CpModel()
    assignments = {}
    singles, active, squares, spans = [], [], [], []
    for i, first in enumerate(people):
        used = model.new_bool_var(f"pool_{i}")
        active.append(used)
        choices = {}
        for k, c in enumerate(classes):
            if first.birth_year in c.years:
                choices[k] = model.new_bool_var(f"class_{i}_{k}")
        model.add(sum(choices.values()) == used)
        members, weighted = [], []
        for j in range(i, len(people)):
            child = people[j]
            if child.weight_grams * 10 > first.weight_grams * 11:
                break
            allowed = [choice for k, choice in choices.items()
                       if child.birth_year in classes[k].years
                       and (classes[k].mixed or child.gender == first.gender)]
            if not allowed:
                continue
            member = used if j == i else model.new_bool_var(f"member_{i}_{j}")
            assignments[i, j] = member
            model.add(member <= sum(allowed))
            # Ohne Klassenkonflikte lassen sich überkreuzte Gruppen ohne
            # schlechtere Größen/Gewichtsspannen zu Intervallen entflechten.
            if common_class and j > i:
                model.add(member <= assignments[i, j - 1])
            members.append(member)
            weighted.append(child.weight_grams * member)
        size = model.new_int_var(0, 5, f"size_{i}")
        model.add(size == sum(members))
        model.add(size <= 5 * used)
        single = model.new_bool_var(f"single_{i}")
        model.add(size == 1).only_enforce_if(single)
        model.add(size != 1).only_enforce_if(single.Not())
        singles.append(single)
        square = model.new_int_var(0, 25, f"square_{i}")
        model.add_element(size, [0, 1, 4, 9, 16, 25], square)
        squares.append(square)
        maximum = model.new_int_var(0, first.weight_grams * 11 // 10, f"max_{i}")
        model.add_max_equality(maximum, weighted)
        spans.append((maximum - first.weight_grams * used) * (1_000_000 / first.weight_grams))
    for j in range(len(people)):
        model.add_exactly_one(member for (i, child), member in assignments.items() if child == j)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_deterministic_time = time_limit
    # Vorherige Optima festschreiben: kein nachrangiger Vorteil wiegt sie auf.
    for stage, objective in enumerate([sum(singles), sum(active), sum(squares), sum(spans)]):
        model.minimize(objective)
        status = solver.solve(model)
        if status != cp_model.OPTIMAL:
            raise RuleError("Die automatische Einteilung konnte innerhalb des Rechenlimits nicht "
                            "vollständig optimiert werden. Bitte die betroffenen Gruppen manuell "
                            "einteilen oder die Altersklassen enger festlegen. Es wurde nichts neu verteilt.")
        if stage < 3:
            model.add(objective == solver.value(objective))
            model.clear_hints()
            for index in range(len(model.proto.variables)):
                variable = model.get_int_var_from_proto_index(index)
                model.add_hint(variable, solver.value(variable))
    result = []
    for i, used in enumerate(active):
        if solver.boolean_value(used):
            members = [people[j] for (pool, j), member in assignments.items()
                       if pool == i and solver.boolean_value(member)]
            name = next(c.name for c in classes if all(p.birth_year in c.years for p in members)
                        and (c.mixed or len({p.gender for p in members}) == 1))
            result.append(PlannedPool(tuple(p.id for p in members), name))
    return result, missing
