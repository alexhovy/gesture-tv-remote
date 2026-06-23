#!/usr/bin/env python3
import argparse
import re
from collections import Counter
from pathlib import Path

COMMAND_RE = re.compile(r"sending command_gesture=(?P<gesture>\S+)")
STATE_RE = re.compile(r"(?P<kind>pointer|volume)_state=(?P<state>\S+)")


def analyze_log(path: Path, near_miss_min_ratio: float) -> str:
    commands: Counter[str] = Counter()
    blocked: Counter[tuple[str, str]] = Counter()
    candidates: Counter[tuple[str, str]] = Counter()
    neutral: Counter[str] = Counter()
    phases: Counter[tuple[str, str]] = Counter()
    near_misses: list[tuple[int, str, float, float, float, str]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        command_match = COMMAND_RE.search(line)
        if command_match:
            commands[command_match.group("gesture")] += 1

        for state_match in STATE_RE.finditer(line):
            kind = state_match.group("kind")
            fields = _parse_state_fields(state_match.group("state"))
            candidate = fields.get("candidate", "none")
            blocked_reason = fields.get("blocked", "none")
            magnitude = _float(fields.get("magnitude"))
            activation = _float(fields.get("activation"))
            ratio = _float(fields.get("threshold_ratio"))
            in_neutral = fields.get("in_neutral") == "True"
            phase = fields.get("phase", "none")

            candidates[(kind, candidate)] += 1
            blocked[(kind, blocked_reason)] += 1
            phases[(kind, phase)] += 1
            if in_neutral:
                neutral[kind] += 1
            if candidate == "none" and in_neutral and ratio >= near_miss_min_ratio:
                near_misses.append(
                    (line_number, kind, magnitude, activation, ratio, blocked_reason)
                )

    lines = [f"log={path}", ""]
    lines.extend(_format_counter("commands", commands))
    lines.extend(_format_counter("candidates", candidates))
    lines.extend(_format_counter("blocked", blocked))
    lines.extend(_format_counter("phases", phases))
    lines.extend(_format_counter("neutral", neutral))
    lines.append("")
    lines.append(f"near_misses ratio>={near_miss_min_ratio:.2f}: {len(near_misses)}")
    for line_number, kind, magnitude, activation, ratio, reason in near_misses[:25]:
        lines.append(
            f"  line={line_number} kind={kind} magnitude={magnitude:.3f} "
            f"activation={activation:.3f} ratio={ratio:.2f} reason={reason}"
        )
    if len(near_misses) > 25:
        lines.append(f"  ... {len(near_misses) - 25} more")

    return "\n".join(lines)


def _format_counter(name: str, counter: Counter[object]) -> list[str]:
    lines = [f"{name}:"]
    if not counter:
        lines.append("  none")
        return lines

    for key, count in counter.most_common():
        if isinstance(key, tuple):
            label = " ".join(str(part) for part in key)
        else:
            label = str(key)
        lines.append(f"  {label}: {count}")
    return lines


def _parse_state_fields(state: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in state.split(":"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        fields[name] = value
    return fields


def _float(value: str | None) -> float:
    if value is None:
        return 0.0

    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize gesture debug logs.")
    parser.add_argument(
        "log_file",
        nargs="?",
        default="logs/logs.txt",
        type=Path,
        help="Path to the gesture log file.",
    )
    parser.add_argument(
        "--near-miss-min-ratio",
        type=float,
        default=0.85,
        help="Minimum threshold ratio to count as a near miss.",
    )
    args = parser.parse_args()

    print(analyze_log(args.log_file, args.near_miss_min_ratio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
