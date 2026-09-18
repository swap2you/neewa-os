#!/usr/bin/env python3
"""NEEWA OS CLI for requested-vs-prohibited action semantics.

Reads an objective (or prompt) text file and emits a compact authorization
JSON decision using the shared parser in 12_SCRIPTS/neewa_action_semantics.py.
Missing or unreadable input exits non-zero with an error on stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEM_PATH = ROOT / "12_SCRIPTS" / "neewa_action_semantics.py"


def load_semantics():
    return SourceFileLoader("neewa_action_semantics_cli", str(SEM_PATH)).load_module()


def read_input(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Authorize NEEWA objectives with requested-vs-prohibited semantics"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the objective/prompt text file to authorize",
    )
    parser.add_argument(
        "--input",
        dest="input_opt",
        help="Alternate path to the objective/prompt text file",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Treat the prompt as a write job (A1 floor when otherwise A0)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Emit full analyze_objective JSON instead of authorize_text",
    )
    args = parser.parse_args(argv)
    path_arg = args.input_opt or args.input_file
    if not path_arg:
        print("error: missing input file; provide a path or --input", file=sys.stderr)
        return 1
    path = Path(path_arg)
    if not path.is_file():
        print(f"error: input file not found: {path}", file=sys.stderr)
        return 1
    try:
        text = read_input(path)
    except OSError as exc:
        print(f"error: input file unreadable: {path}: {exc}", file=sys.stderr)
        return 1
    sem = load_semantics()
    if args.analyze:
        payload = sem.analyze_objective(text)
    else:
        payload = sem.authorize_text(text, write=args.write)
    print(json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
