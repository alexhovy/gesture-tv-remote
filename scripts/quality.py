"""Normalize repository text files and run the standard quality gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_SUFFIXES = {".py", ".md"}
TARGET_NAMES = {"pyproject.toml"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        path = ROOT / line
        if path.suffix in TARGET_SUFFIXES or path.name in TARGET_NAMES:
            paths.append(path)
    return paths


def normalize_line_breaks(paths: list[Path]) -> None:
    changed = 0
    for path in paths:
        original = path.read_bytes()
        normalized = original.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        normalized = normalized.rstrip(b"\n") + b"\n"
        if normalized != original:
            path.write_bytes(normalized)
            changed += 1
    print(f"Normalized line breaks in {changed} file(s).")


def run(command: list[str]) -> int:
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    normalize_line_breaks(tracked_files())
    commands = [
        ["uv", "run", "ruff", "check", "--fix", "."],
        ["uv", "run", "black", "."],
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "mypy"],
        ["uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"],
    ]
    failures: list[tuple[list[str], int]] = []
    for command in commands:
        returncode = run(command)
        if returncode != 0:
            failures.append((command, returncode))

    if failures:
        print("\nQuality gate failed:")
        for command, returncode in failures:
            print(f"  {returncode}: {' '.join(command)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
