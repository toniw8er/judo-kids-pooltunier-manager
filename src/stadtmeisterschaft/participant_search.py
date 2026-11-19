"""Namenssuche für die Navigation; verändert keine Teilnehmerdaten."""
import re
import unicodedata
from difflib import SequenceMatcher

from .domain import Participant


def name_words(text: str) -> list[str]:
    text = text.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+", text)


def search_participants(participants: list[Participant], query: str) -> list[Participant]:
    """Genaue Namen vor Teilnamen und ähnlichen Schreibweisen, unabhängig von der Reihenfolge."""
    words = name_words(query)
    if not words:
        return []
    matches = []
    for person in participants:
        available = name_words(person.name)
        exact_name = sorted(words) == sorted(available)
        scores = []
        # Lange Suchteile zuerst zuordnen, damit kurze Teile keinen Nachnamen belegen.
        for word in sorted(words, key=len, reverse=True):
            options = []
            for index, candidate in enumerate(available):
                if word == candidate:
                    score = 1.0
                elif candidate.startswith(word):
                    score = 0.95
                elif word in candidate:
                    score = 0.9
                elif len(word) >= 3 and len(candidate) >= 3:
                    similarity = SequenceMatcher(None, word, candidate).ratio()
                    score = similarity * 0.85 if similarity >= (2 / 3 if len(word) == 3 else 0.74) else 0
                else:
                    score = 0
                options.append((score, index))
            score, index = max(options, default=(0, 0))
            if not score:
                break
            scores.append(score)
            available.pop(index)
        if len(scores) == len(words):
            matches.append((not exact_name, -min(scores), -sum(scores), person.name.casefold(), person.id, person))
    return [entry[-1] for entry in sorted(matches, key=lambda entry: entry[:-1])]
