"""Bearbeitbare Vorschläge für die Stadtmeisterschaft, keine universelle Verbandsregel.

U9–U18: Bayerischer Judo-Verband, Alters- und Gewichtsklassen 2026 (Einzel).
Quellen und Abgrenzung: docs/referenzen/altersklassen_recherche_2026.md.
"""
from stadtmeisterschaft.domain import AgeClass, RuleError


AGE_RANGES = {"U9": (7, 8), "U11": (8, 10), "U13": (10, 12),
              "U15": (12, 14), "U18": (15, 17)}


def suggested_class(name: str, event_year: int) -> AgeClass | None:
    name = name.strip().upper().replace(" ", "")
    if name not in AGE_RANGES:
        return None
    minimum, maximum = AGE_RANGES[name]
    result = AgeClass(name, list(range(event_year - maximum, event_year - minimum + 1)))
    result.validate()
    return result


def suggested_classes(event_year: int) -> list[AgeClass]:
    if not 1917 <= event_year <= 2100:
        raise RuleError("Jahrgangsvorschläge sind für Veranstaltungsjahre 1917–2100 möglich.")
    return [suggested_class(name, event_year) for name in AGE_RANGES]
