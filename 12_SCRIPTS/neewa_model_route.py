"""Task routing for ChatGPT sign-in review. Paid API routes are excluded."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "16_WINDOWS_CLIENT" / "worker" / "chatgpt_review_routes.json"
PAID_MARKERS = ("openai-api", "api.openai.com", "sk-")


def load_routes(path: Path | None = None) -> dict:
    target = path or ROUTES
    return json.loads(target.read_text(encoding="utf-8"))


def select_task(task: str, routes: dict | None = None) -> dict:
    data = routes if routes is not None else load_routes()
    if data.get("api_key_fallback") or data.get("paid_api"):
        raise ValueError("paid API fallback is disabled for this review workflow")
    spec = (data.get("tasks") or {}).get(task)
    if not spec:
        raise KeyError(task)
    probed = data.get("probed") or {}
    model = spec.get("model")
    effort = spec.get("effort") or "high"
    substituted = False
    reason = "configured"
    availability = probed.get(model) or {}
    if probed and not availability.get("available"):
        fallback = spec.get("fallback_model")
        fallback_ok = bool((probed.get(fallback) or {}).get("available")) if fallback else False
        if fallback and fallback_ok:
            model = fallback
            substituted = True
            reason = f"{spec.get('model')} unavailable; using {fallback}"
        elif not availability.get("available"):
            reason = availability.get("reason") or f"{model} not confirmed on ChatGPT sign-in"
    return {
        "task": task,
        "context": spec.get("context"),
        "model": model,
        "effort": effort,
        "authentication": data.get("authentication"),
        "api_key_fallback": False,
        "paid_api": False,
        "substituted": substituted,
        "reason": reason,
        "probe": availability or None,
    }


def assert_no_paid_route(text: str) -> None:
    lowered = (text or "").lower()
    for marker in PAID_MARKERS:
        if marker in lowered:
            raise ValueError("paid API route is excluded")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a ChatGPT sign-in review model")
    parser.add_argument("--task", required=True)
    args = parser.parse_args()
    print(json.dumps(select_task(args.task), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
