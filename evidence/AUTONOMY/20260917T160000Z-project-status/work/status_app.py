"""Project status CLI. Reads one JSON file; does not walk the filesystem."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_projects(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("status file must be a JSON array")
    out = []
    for row in data:
        if not isinstance(row, dict) or "name" not in row or "status" not in row:
            raise ValueError("each item needs name and status")
        out.append({"name": str(row["name"]), "status": str(row["status"])})
    return out


def render(projects: list[dict]) -> str:
    lines = ["PROJECT STATUS", "=============="]
    for row in projects:
        lines.append(f"{row['name']}: {row['status']}")
    lines.append(f"count={len(projects)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write("usage: status_app.py <file.json>\n")
        return 2
    path = Path(args[0])
    try:
        text = render(load_projects(path))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"invalid status file: {exc}\n")
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
