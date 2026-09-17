"""Separate requested operations from prohibitions for NEEWA classification.

Keyword presence is not authorization. A prohibition, exclusion, example,
quoted span, or documentation mention must not become an executable A2/A3
objective. Affirmative consequential requests still require their gates.
"""
from __future__ import annotations

import re

NEGATION_LEADERS = (
    "do not",
    "does not",
    "don't",
    "dont",
    "must not",
    "cannot",
    "can't",
    "never",
    "without",
    "no",
    "not to",
    "avoid",
    "refrain from",
    "not for",
    "instead of",
)

DOC_CONTEXT = re.compile(
    r"\b(?:instructions?|guides?|documentation|documents?|readme|notes?|"
    r"plans?|how to|write-?up|runbook|playbook)\b",
    re.I,
)

FAMILIES = {
    "publish": {
        "level": "A2",
        "pattern": r"\b(?:publish(?:es|ed|ing)?|publication)\b",
    },
    "deploy": {
        "level": "A2",
        "pattern": r"\b(?:deploy(?:s|ed|ing|ment)?|roll(?:s|ed|ing)? (?:this )?out)\b",
        "doc_exempt": True,
    },
    "purchase": {
        "level": "A2",
        "pattern": r"\b(?:purchase[sd]?|purchasing|buy(?:s|ing)?|subscribe[sd]?|subscribing)\b",
    },
    "send_message": {
        "level": "A2",
        "pattern": r"\b(?:e-?mails?|external messages?|message(?:s|d|ing)? the client|"
        r"email the client|send (?:the )?(?:client )?(?:an )?e-?mail)\b",
    },
    "make_public": {
        "level": "A2",
        "pattern": r"\b(?:make public|change visibility|post publicly|public internet)\b",
    },
    "credential": {
        "level": "A2",
        "pattern": r"\b(?:rotate credential|disable (?:antivirus|defender|security))\b",
    },
    "destructive": {
        "level": "A2",
        "pattern": r"\b(?:delete everything|delete all files|delete files|"
        r"drop database|format c:|rm -rf|destructive actions?)\b",
    },
    "financial": {
        "level": "A3",
        "pattern": r"\b(?:live trade|place order|wire transfer|bank transfer|send money)\b",
    },
}

_LEADER_RE = re.compile(
    r"^(?:please\s+)?(?:"
    + "|".join(re.escape(x) for x in sorted(NEGATION_LEADERS, key=len, reverse=True))
    + r")\b",
    re.I,
)
_INLINE_NEG_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(x) for x in sorted(NEGATION_LEADERS, key=len, reverse=True))
    + r")\b",
    re.I,
)
_QUOTE_RE = re.compile(r"\"[^\"]*\"|'[^']*'|`[^`]*`")
_CLAUSE_RE = re.compile(r"(?<=[.!?;])\s+|\s+\bbut\b\s+|\s+\bhowever\b\s+|\s+\bexcept that\b\s+", re.I)


def strip_quoted(text: str) -> tuple[str, list[str]]:
    quoted: list[str] = []

    def _keep(match: re.Match[str]) -> str:
        quoted.append(match.group(0)[1:-1])
        return " "

    return _QUOTE_RE.sub(_keep, text or ""), quoted


def split_clauses(text: str) -> list[str]:
    return [part.strip() for part in _CLAUSE_RE.split(text or "") if part and part.strip()]


def clause_is_prohibition(clause: str) -> bool:
    return bool(_LEADER_RE.search((clause or "").strip()))


def _clause_bounds(text: str, index: int) -> tuple[int, int]:
    start = 0
    for match in re.finditer(r"[.!?;]", text[:index]):
        start = match.end()
    end = len(text)
    tail = re.search(r"[.!?;]", text[index:])
    if tail:
        end = index + tail.start() + 1
    return start, end


def _preceded_by_inline_negation(clause: str, match_start: int) -> bool:
    prefix = clause[:match_start]
    hit = None
    for found in _INLINE_NEG_RE.finditer(prefix):
        hit = found
    if not hit:
        return False
    between = prefix[hit.end() :]
    if re.search(r"\b(?:and then|then|please)\b", between, re.I):
        return False
    return True


def analyze_objective(text: str) -> dict:
    raw = text or ""
    unquoted, quoted = strip_quoted(raw)
    clauses = split_clauses(unquoted)
    prohibited_clauses = [c for c in clauses if clause_is_prohibition(c)]
    requested_clauses = [c for c in clauses if not clause_is_prohibition(c)]
    requested_text = " ".join(requested_clauses).strip()
    prohibited_text = " ".join(prohibited_clauses).strip()

    requested_families: list[str] = []
    prohibited_families: list[str] = []
    for name, spec in FAMILIES.items():
        pattern = re.compile(spec["pattern"], re.I)
        for match in pattern.finditer(unquoted):
            start, end = _clause_bounds(unquoted, match.start())
            clause = unquoted[start:end]
            negated = clause_is_prohibition(clause) or _preceded_by_inline_negation(
                clause, match.start() - start
            )
            doc_exempt = bool(spec.get("doc_exempt")) and bool(DOC_CONTEXT.search(clause))
            if negated:
                if name not in prohibited_families:
                    prohibited_families.append(name)
                continue
            if doc_exempt:
                continue
            if name not in requested_families:
                requested_families.append(name)

    levels = [FAMILIES[name]["level"] for name in requested_families]
    needed = "A0"
    if "A3" in levels:
        needed = "A3"
    elif "A2" in levels:
        needed = "A2"

    return {
        "requested_text": requested_text,
        "prohibited_text": prohibited_text,
        "quoted": quoted,
        "requested_families": requested_families,
        "prohibited_actions": prohibited_families,
        "needed": needed,
        "clauses": {
            "requested": requested_clauses,
            "prohibited": prohibited_clauses,
        },
    }


def operative_text(text: str) -> str:
    return analyze_objective(text)["requested_text"]


def family_is_requested(text: str, family: str) -> bool:
    return family in analyze_objective(text)["requested_families"]


def blocked_fragment_is_requested(text: str, fragment: str) -> bool:
    """True when a worker blocked-intent fragment is an actual requested action."""
    blob = (fragment or "").strip().lower()
    if not blob:
        return False
    analysis = analyze_objective(text)
    operative = (analysis["requested_text"] or "").lower()
    if not operative:
        return False
    token = blob.split()[-1]
    stem = re.escape(re.sub(r"(?:es|s|ed|ing)$", "", token) or token)
    present = blob in operative or bool(re.search(rf"\b{stem}[a-z]*\b", operative, re.I))
    if not present:
        return False
    for name, spec in FAMILIES.items():
        if re.search(spec["pattern"], blob, re.I):
            return name in analysis["requested_families"]
    return True
