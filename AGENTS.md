# Gesture TV Remote Agent Guide
Agents must read this file before making changes within this directory scope.

## Scope
This file applies to the entire repository at the root level.

## Repository Purpose
This repository contains a Python MVP for controlling a Google TV with webcam hand gestures.

The application combines webcam input, MediaPipe hand tracking, gesture-session rules, Android TV command dispatch, and optional voice capture. Keep the code organized around those responsibilities instead of collapsing behavior into scripts.

## Agent Operating Procedure
Before making changes, agents must:

1. Understand context: read applicable `AGENTS.md` files, `README.md`, and relevant docs.
2. Identify scope: determine whether the change affects app composition, services, domain rules, infrastructure adapters, docs, tests, or configuration.
3. Search for existing patterns before introducing new structure.
4. Define a plan before implementation for meaningful behavior, architecture, or documentation changes.
5. Respect layer boundaries and keep changes minimal.
6. Validate correctness with relevant tests and, when appropriate, manual runtime checks.
7. Update docs when behavior, configuration, setup, gesture semantics, or architecture boundaries change.

## Repository Structure
- `main.py`: Thin executable entry point.
- `src/runtime/`: Runnable process composition and CLI runtime selection.
- `src/web/`: Lightweight config UI request handling, forms, and rendering.
- `src/services/`: Use cases and orchestration.
- `src/domain/`: Gesture rules, command mappings, landmark math, and session state.
- `src/infrastructure/`: External integrations such as OpenCV, MediaPipe, Android TV remote, camera preprocessing, model download, and overlays.
- `src/shared/`: Small cross-cutting primitives such as configuration and logging.
- `docs/`: Durable project documentation for architecture, configuration, development, and gesture behavior.
- `tests/`: `unittest` test suite.
- `models/`: Runtime model files; do not commit generated downloads.
- `certs/`: Runtime pairing certificates; do not commit credentials or generated certificates.

## Working Principles
- Follow the existing architecture documented in `docs/architecture.md`.
- Prefer deterministic domain functions for gesture semantics.
- Keep I/O, hardware, network, MediaPipe, OpenCV, Android TV, and audio dependencies behind infrastructure or service boundaries.
- Keep `main.py` and `src/runtime/` free of business logic.
- Keep shared code small and purposeful; do not turn `src/shared/` into a general utility bucket.
- Avoid new dependencies unless they are clearly necessary and fit the project size.
- Prefer small, reviewable changes over broad rewrites.

## Documentation Standards
- Keep `README.md` as the concise project entry point.
- Use `docs/` for architecture, configuration, development workflow, gesture behavior, and operational notes.
- Do not duplicate implementation details that are obvious from code.
- Update documentation in the same change when user-visible behavior, configuration, setup, or gesture semantics change.

## Testing Standards
- Use the existing `unittest` style unless the test framework is intentionally changed.
- Run relevant tests before concluding work:

```bash
python -m unittest discover -s tests
```

- Add or update tests when changing gesture rules, session behavior, configuration parsing, crop/zoom math, or service orchestration.
- Avoid tests that require a real webcam, TV, microphone, network, certificates, or downloaded model unless the test is explicitly integration-focused.

## Safety and Quality
- Do not commit secrets, generated certificates, downloaded model files, virtual environments, caches, or runtime artifacts.
- Preserve hardware-dependent behavior behind adapters so pure logic remains testable.
- Keep defaults predictable and document environment variable changes.
- Validate behavior with tests and targeted manual checks when touching webcam, display, TV remote, or voice capture flows.

## Instruction Precedence
When multiple `AGENTS.md` files apply, the most specific scope takes precedence over broader scopes.
