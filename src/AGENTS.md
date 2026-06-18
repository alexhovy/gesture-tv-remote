# Source Agent Guide
Agents must read this file before making changes within this directory scope.

## Scope
This file applies to all production code under `src/`.

The root `AGENTS.md` still applies. This guide adds source-specific rules.

## Layer Boundaries
- `src/api/`: Compose and run the application. Keep it thin.
- `src/services/`: Coordinate workflows across domain and infrastructure.
- `src/domain/`: Own gesture semantics, command mappings, landmark math, and session state.
- `src/infrastructure/`: Own external libraries, hardware integration, model download, image processing, and transport adapters.
- `src/shared/`: Own small cross-cutting primitives such as configuration and logging.

## Core Rules
- Domain modules must not import OpenCV, MediaPipe, `androidtvremote2`, `sounddevice`, or other hardware/integration libraries.
- Infrastructure modules may depend on third-party libraries, but should not own gesture business rules.
- Services may orchestrate workflows, but should not hide deterministic gesture rules that belong in domain code.
- API composition and `main.py` must remain free of gesture decisions and transport details.
- Configuration changes belong in `src/shared/config.py` and must stay documented.

## Development Guidelines
- Prefer pure functions for gesture detection, motion detection, landmark math, and crop calculations.
- Keep adapters explicit and narrow around external systems.
- Keep async task lifecycle handling clear when changing voice capture or remote command flows.
- Avoid adding generic helpers unless multiple current call sites need the abstraction.
- Preserve readable names for gestures, commands, timing thresholds, and geometry values.

## Decision Making
When unsure:

- Gesture classification or state transition -> `src/domain/`.
- Command orchestration or use-case workflow -> `src/services/`.
- Camera, MediaPipe, Android TV, OpenCV, audio, model files, or drawing -> `src/infrastructure/`.
- Runtime settings, environment variables, or logging primitives -> `src/shared/`.
- Startup composition -> `src/api/` or `main.py`.

## Validation
- Add or update tests for behavior changes in domain, configuration, geometry, session state, or service orchestration.
- Prefer tests that use deterministic inputs and avoid hardware dependencies.
- Run:

```bash
python -m unittest discover -s tests
```
