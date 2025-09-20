#!/usr/bin/env python3
"""Utility to call Codex with a configurable prompt."""

import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AUTOPILOT_DIR = SCRIPT_DIR.parent
PROMPT_PATH = AUTOPILOT_DIR / "prompts" / "codex_prompt.txt"
DEFAULT_SCRIPT = str(AUTOPILOT_DIR / "scripts" / "run_training.sh")
DEFAULT_NOTES = str(AUTOPILOT_DIR / "codex_notes.txt")


def main(script: str = DEFAULT_SCRIPT, notes_path: str = DEFAULT_NOTES) -> None:
    template = PROMPT_PATH.read_text().strip()
    prompt = template.format(script=script, notes_path=notes_path)
    cmd = [
        "codex",
        "exec",
        prompt,
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
