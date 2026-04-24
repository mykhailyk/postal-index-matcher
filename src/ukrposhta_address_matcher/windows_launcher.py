from __future__ import annotations

from pathlib import Path
import os
import sys

from ukrposhta_address_matcher.cli import review_ui_main


def _resolve_env_file(base_dir: Path) -> Path | None:
    candidates = [
        base_dir / ".env",
        base_dir.parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parents[2]
    os.chdir(base_dir)
    argv: list[str] = []
    env_file = _resolve_env_file(base_dir)
    if env_file is not None:
        argv.extend(["--env-file", str(env_file)])
    return review_ui_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
