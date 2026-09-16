"""Apply NEEWA pronunciation aliases to a Hermes 0.21.3 sherpa engine.

Idempotent. Maps wake_word.aliases onto the active profile (not extra profiles).
Does not change capture mode, surface, or security settings.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

MARKER = "NEEWA_WAKE_ALIASES"
ANCHOR = "phrase_map: Dict[str, str] = {phrase: ww._active_profile_name()}"
REPLACEMENT = '''active_profile = ww._active_profile_name()
        phrase_map: Dict[str, str] = {phrase: active_profile}
        # NEEWA_WAKE_ALIASES: extra pronunciations stay on THIS profile.
        _aliases = cfg.get("aliases") or []
        if isinstance(_aliases, str):
            _aliases = [_aliases]
        if isinstance(_aliases, (list, tuple)):
            for _alias in _aliases:
                _name = str(_alias or "").strip()
                if _name:
                    phrase_map.setdefault(_name, active_profile)'''

ALIAS_BLOCK = """  aliases:
    - hey niva
    - hey neeva
    - hey neva
    - he neva
"""


def patch_engine(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already_patched"
    if ANCHOR not in text:
        raise SystemExit(f"unexpected Hermes engine (missing phrase_map init): {path}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_suffix(path.suffix + f".bak-neewa-aliases-{stamp}")
    shutil.copy2(path, backup)
    path.write_text(text.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    return f"patched backup={backup.name}"


def ensure_aliases_config(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "aliases:" in text and "hey niva" in text:
        return "aliases_present"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_suffix(path.suffix + f".bak-neewa-aliases-{stamp}")
    shutil.copy2(path, backup)
    if "phrase: hey neewa" in text:
        text = text.replace("phrase: hey neewa", "phrase: hey neewa\n" + ALIAS_BLOCK.rstrip(), 1)
    elif "phrase: \"hey neewa\"" in text:
        text = text.replace("phrase: \"hey neewa\"", "phrase: \"hey neewa\"\n" + ALIAS_BLOCK.rstrip(), 1)
    else:
        raise SystemExit(f"wake_word.phrase hey neewa not found in {path}")
    path.write_text(text, encoding="utf-8")
    return f"config_updated backup={backup.name}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-home", default=str(Path.home() / ".hermes"))
    args = parser.parse_args()
    home = Path(args.hermes_home)
    engine = home / "hermes-agent" / "tools" / "wake_word_engines.py"
    config = home / "config.yaml"
    if not engine.is_file():
        raise SystemExit(f"missing {engine}")
    if not config.is_file():
        raise SystemExit(f"missing {config}")
    print(patch_engine(engine))
    print(ensure_aliases_config(config))


if __name__ == "__main__":
    main()
