#!/usr/bin/env python3
"""Render JSON config into CLI args for pufferlib training entrypoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, List


def hyphenate(key: str) -> str:
    """Convert snake_case to kebab-case for CLI flags."""
    return key.replace("_", "-")


def emit_args(prefix: str, payload: Any, argv: List[str]) -> None:
    """Append CLI flags to argv for a nested config payload."""
    if isinstance(payload, dict):
        for subkey, value in payload.items():
            next_prefix = f"{prefix}.{hyphenate(subkey)}" if prefix else hyphenate(subkey)
            emit_args(next_prefix, value, argv)
        return

    flag = f"--{prefix}"
    if isinstance(payload, bool):
        if payload:
            argv.append(flag)
        return

    argv.append(flag)
    argv.append(str(payload))


def render(config_path: Path) -> Iterable[str]:
    data = json.loads(config_path.read_text())
    if not isinstance(data, dict):
        raise SystemExit("Config root must be a JSON object")

    argv: List[str] = []
    for section, payload in data.items():
        if not isinstance(payload, dict):
            emit_args(hyphenate(section), payload, argv)
            continue
        emit_args(hyphenate(section), payload, argv)
    return argv


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render_cli_args.py <config.json>")
    config_path = Path(sys.argv[1]).expanduser().resolve()
    if not config_path.exists():
        raise SystemExit(f"Missing config: {config_path}")

    for token in render(config_path):
        print(token)


if __name__ == "__main__":
    main()
