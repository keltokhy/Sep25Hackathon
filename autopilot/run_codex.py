#!/usr/bin/env python3
"""Utility to call Codex and run the training shell script via external prompt."""

import subprocess
from pathlib import Path

PROMPT_PATH = Path(__file__).with_name("codex_prompt.txt")


def main() -> None:
    prompt = PROMPT_PATH.read_text().strip()
    cmd = [
        "codex",
        "exec",
        prompt,
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
