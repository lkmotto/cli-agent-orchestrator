"""Simple Factory REPL wrapper for CAO custom_cli provider."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys


def _run_factory(prompt: str) -> tuple[int, str]:
    base = os.environ.get(
        "CAO_FACTORY_EXEC_CMD",
        "droid exec --auto medium --output-format text",
    ).strip()
    command = shlex.split(base) + [prompt]
    proc = subprocess.run(command, capture_output=True, text=True, check=False, timeout=900)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if out:
        return proc.returncode, out
    return proc.returncode, err


def main() -> int:
    print("Factory REPL bridge ready. Type /help or /exit.")
    while True:
        try:
            user_input = input("factory> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0

        if not user_input:
            continue
        lowered = user_input.lower()
        if lowered in {"/exit", "exit", "quit"}:
            return 0
        if lowered in {"/help", "help"}:
            print("Assistant: Enter any task prompt to run through `droid exec`.")
            continue

        try:
            code, text = _run_factory(user_input)
        except Exception as e:
            print(f"Error: failed to execute Factory command: {e}")
            continue

        if code == 0:
            print("Assistant:")
            print(text or "(no output)")
        else:
            print(f"Error: Factory command failed with exit code {code}")
            if text:
                print(text)


if __name__ == "__main__":
    raise SystemExit(main())
