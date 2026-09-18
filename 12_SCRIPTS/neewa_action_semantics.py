"""Separate requested operations from prohibitions for NEEWA classification.

Keyword presence is not authorization. A prohibition, exclusion, example,
quoted span, documentation mention, or verification / inspection / readiness /
status / version-check of an already released version / release state must not
become an executable A2/A3 objective. Explicit rollout, promotion, or
release-to-production requests still require their gates.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

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

# Explicit inspection / status / readiness / version-check wording around
# release or past-tense publish/deploy (these requests stay A0).
INSPECT_CONTEXT = re.compile(
    r"\b(?:"
    r"read-?only|verif(?:y|ies|ied|ying|ication)|inspect(?:s|ed|ing|ion)?|"
    r"confirm(?:s|ed|ing)?|check(?:s|ed|ing)?|report(?:s|ed|ing)?|"
    r"summar(?:y|ize|ise)|status(?:\s+of)?|show(?:s|ing)?(?:\s+me)?|what is|"
    r"compare|matches?|readiness|version[- ]?check"
    r")\b",
    re.I,
)

RELEASE_STATE_PHRASE = re.compile(
    r"\b(?:"
    r"release[- ]?state|already[- ]released|released version|"
    r"deployed (?:sha|build|version|release|state|package)|"
    r"published (?:version|package|release|build|sha|notes)"
    r")\b",
    re.I,
)

STATUS_FORM = re.compile(
    r"^(?:deployed|published|released|deployment|publication)$",
    re.I,
)

STATUS_CONSTRUCTION = re.compile(
    r"\b(?:was|were|been|is|are|currently|already|previously|recently)\s+"
    r"(?:deployed|published|released)\b|"
    r"\b(?:deployed|published|released)\s+"
    r"(?:sha|build|version|release|state|package|last|yesterday|notes|tag)\b",
    re.I,
)

FAMILIES = {
    "publish": {
        "level": "A2",
        "pattern": r"\b(?:publish(?:es|ed|ing)?|publication)\b",
        "inspect_exempt": True,
    },
    "deploy": {
        "level": "A2",
        "pattern": (
            r"\b(?:deploy(?:s|ed|ing|ment)?|roll(?:s|ed|ing)? (?:this )?out|"
            r"rollouts?|production rollout|rollout to production|"
            r"promot(?:e|es|ed|ing)\s+to\s+(?:production|prod)|"
            r"promotion\s+to\s+(?:production|prod)|"
            r"promote (?:this|the) (?:release|build|version|app|package))\b"
        ),
        "doc_exempt": True,
        "inspect_exempt": True,
    },
    "release": {
        "level": "A2",
        "pattern": (
            r"\b(?:cut (?:a |the )?release|create (?:a |the )?(?:github )?release|"
            r"make (?:a |the )?release|ship (?:a |the )?release|"
            r"release (?:this|the) (?:version|package|build|app|cli)|"
            r"release to (?:production|npm|pypi|users)|"
            r"release[- ]to[- ]production)\b"
        ),
        "inspect_exempt": True,
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

A3_HINTS = ("live trade", "place order", "wire transfer", "bank transfer", "send money")

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
_LIST_PREFIX_RE = re.compile(r"^[\s>*\-•]+")


def strip_quoted(text: str) -> tuple[str, list[str]]:
    quoted: list[str] = []

    def _keep(match: re.Match[str]) -> str:
        quoted.append(match.group(0)[1:-1])
        return " "

    return _QUOTE_RE.sub(_keep, text or ""), quoted


def split_clauses(text: str) -> list[str]:
    return [part.strip() for part in _CLAUSE_RE.split(text or "") if part and part.strip()]


def normalize_clause(clause: str) -> str:
    return _LIST_PREFIX_RE.sub("", (clause or "").strip())


def clause_is_prohibition(clause: str) -> bool:
    return bool(_LEADER_RE.search(normalize_clause(clause)))


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


def match_is_inspection_or_status(clause: str, matched: str) -> bool:
    """True when a family keyword is inspection/status, not a consequential request.

    Verification, inspection, readiness, status, and version-check requests are
    A0. Explicit rollout, promotion, or release-to-production requests remain
    A2. Past-tense or adjectival deployed/published/released status is not an
    affirmative deploy/publish/release request.
    """
    blob = (matched or "").strip()
    if not blob:
        return False
    text = clause or ""
    if RELEASE_STATE_PHRASE.search(text) and (
        INSPECT_CONTEXT.search(text) or STATUS_FORM.fullmatch(blob)
    ):
        return True
    if INSPECT_CONTEXT.search(text) and STATUS_FORM.fullmatch(blob):
        return True
    if STATUS_CONSTRUCTION.search(text) and STATUS_FORM.fullmatch(blob):
        return True

    inspect = INSPECT_CONTEXT.search(text)
    if not inspect:
        return False

    # "verify then rollout / promote / release to production" stays consequential.
    match_pos = text.lower().find(blob.lower())
    if match_pos >= inspect.end():
        between = text[inspect.end() : match_pos]
        if re.search(r"\b(?:and then|then|and please)\b", between, re.I):
            return False

    # Leading imperative action ("rollout this…", "promote to…") is not inspection.
    norm = normalize_clause(text)
    if re.match(rf"^(?:please\s+)?{re.escape(blob)}\b", norm, re.I):
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
            inspect_exempt = bool(spec.get("inspect_exempt")) and match_is_inspection_or_status(
                clause, match.group(0)
            )
            if negated:
                if name not in prohibited_families:
                    prohibited_families.append(name)
                continue
            if doc_exempt or inspect_exempt:
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


def _fragment_in_text(fragment: str, text: str) -> bool:
    blob = (fragment or "").strip().lower()
    hay = (text or "").lower()
    if not blob or not hay:
        return False
    if re.search(r"[\s:/\-]", blob):
        return blob in hay
    return bool(re.search(rf"\b{re.escape(blob)}\b", hay))


def _family_for_fragment(fragment: str) -> str | None:
    blob = (fragment or "").strip()
    if not blob:
        return None
    for name, spec in FAMILIES.items():
        if re.search(spec["pattern"], blob, re.I):
            return name
    return None


def blocked_fragment_is_requested(text: str, fragment: str) -> bool:
    """True when a worker blocked-intent fragment is an actual requested action.

    Multi-word and secret-like fragments match as exact phrases in requested
    text only. Single-word family fragments follow requested-family semantics.
    Last-token stemming is intentionally not used: KEY must not match keys.
    """
    blob = (fragment or "").strip().lower()
    if not blob:
        return False
    analysis = analyze_objective(text)
    operative = analysis["requested_text"] or ""
    if not operative:
        return False
    family = _family_for_fragment(blob)
    if family:
        return family in analysis["requested_families"]
    return _fragment_in_text(blob, operative)


def _requested_action_label(analysis: dict, write: bool) -> str:
    families = analysis.get("requested_families") or []
    if families:
        return ",".join(families)
    return "local_write" if write else "read"


def public_authorization(decision: dict | None) -> dict:
    """Auditable authorization fields without prompt text or credentials."""
    src = decision or {}
    allowed_keys = (
        "allowed",
        "needed",
        "reason",
        "detail",
        "matched_rule",
        "requested_action",
        "requested_families",
        "prohibited_actions",
        "effective_approval",
    )
    out = {key: src.get(key) for key in allowed_keys if src.get(key) is not None}
    if "allowed" in src:
        out["allowed"] = bool(src.get("allowed"))
    return out


def authorize_text(
    text: str,
    *,
    blocked_fragments: list[str] | None = None,
    write: bool = False,
) -> dict:
    """Shared controller/worker authorization decision for a prompt or objective."""
    analysis = analyze_objective(text)
    needed = analysis.get("needed") or "A0"
    if write and needed == "A0":
        needed = "A1"
    matched_rule = None
    for frag in blocked_fragments or []:
        if frag and blocked_fragment_is_requested(text, frag):
            matched_rule = frag
            mapped = "A3" if any(h in frag.lower() for h in A3_HINTS) else "A2"
            if needed in {"A0", "A1"} or (mapped == "A3" and needed != "A3"):
                needed = mapped
            break
    allowed = needed in {"A0", "A1"}
    if allowed:
        reason = "ALLOW"
    elif matched_rule:
        reason = "BLOCKED_INTENT"
    else:
        reason = f"{needed}_OWNER_GATE"
    return public_authorization(
        {
            "allowed": allowed,
            "needed": needed,
            "reason": reason,
            "detail": matched_rule,
            "matched_rule": matched_rule,
            "requested_action": _requested_action_label(analysis, write),
            "requested_families": analysis.get("requested_families") or [],
            "prohibited_actions": analysis.get("prohibited_actions") or [],
            "effective_approval": needed,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NEEWA requested-vs-prohibited authorization")
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--text")
    parser.add_argument("--text-file")
    parser.add_argument("--fragments-json")
    parser.add_argument("--fragments-file")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize:
        parser.error("--authorize is required")
    if args.text is None and not args.text_file:
        parser.error("provide --text or --text-file")
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    else:
        text = args.text
    fragments: list[str] = []
    if args.fragments_json:
        loaded = json.loads(args.fragments_json)
        fragments = loaded if isinstance(loaded, list) else [loaded]
    elif args.fragments_file:
        loaded = json.loads(Path(args.fragments_file).read_text(encoding="utf-8"))
        fragments = loaded if isinstance(loaded, list) else [loaded]
    print(json.dumps(authorize_text(text, blocked_fragments=fragments, write=args.write)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
