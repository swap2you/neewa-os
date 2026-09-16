"""NEEWA wake-phrase policy: canonical name plus pronunciation aliases.

Sherpa-onnx KeywordSpotter accepts multiple keyword lines in one file.
Hermes 0.21.3 only enrolled ``wake_word.phrase`` plus other profiles.
Aliases must map to the SAME profile as the canonical phrase so Desktop
does not switch gateways. STT cannot compensate: it starts after wake.
"""

from __future__ import annotations

CANONICAL_PHRASE = "hey neewa"
PRONUNCIATION_ALIASES = (
    "hey niva",
    "hey neeva",
    "hey neva",
)
NEGATIVE_EXAMPLES = (
    "hey nina",
    "hey nio",
    "okay neewa",
    "hey there",
)

# Detector cooldown in Hermes tools/wake_word.py (_FIRE_COOLDOWN_SECONDS).
FIRE_COOLDOWN_SECONDS = 2.0


def normalize_phrase(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def enrolled_phrases(canonical: str = CANONICAL_PHRASE, aliases: tuple[str, ...] | list[str] = PRONUNCIATION_ALIASES) -> list[str]:
    """Canonical first, then unique aliases. Negatives are never enrolled."""
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (canonical, *aliases):
        phrase = normalize_phrase(raw)
        if not phrase or phrase in seen or phrase in {normalize_phrase(n) for n in NEGATIVE_EXAMPLES}:
            continue
        seen.add(phrase)
        ordered.append(phrase)
    return ordered


def phrase_profile_map(canonical: str = CANONICAL_PHRASE, aliases: tuple[str, ...] | list[str] = PRONUNCIATION_ALIASES, profile: str = "default") -> dict[str, str]:
    """Every pronunciation variant routes to the live NEEWA profile."""
    return {phrase: profile for phrase in enrolled_phrases(canonical, aliases)}


def sherpa_keyword_lines(phrases: list[str] | None = None) -> list[str]:
    """Display names Sherpa accepts (@NAME with underscores, no spaces)."""
    phrases = phrases if phrases is not None else enrolled_phrases()
    lines = []
    for phrase in phrases:
        display = phrase.upper().replace(" ", "_")
        lines.append(f"@{display}")
    return lines


def is_negative_example(phrase: str) -> bool:
    return normalize_phrase(phrase) in {normalize_phrase(n) for n in NEGATIVE_EXAMPLES}


def fires_once(detections: list[tuple[float, str]], cooldown: float = FIRE_COOLDOWN_SECONDS) -> bool:
    """True when no two detections of the same phrase occur inside the cooldown window."""
    last: dict[str, float] = {}
    for ts, phrase in detections:
        key = normalize_phrase(phrase)
        prev = last.get(key)
        if prev is not None and (ts - prev) < cooldown:
            return False
        last[key] = ts
    return True
