# Development

## Setup

Install `uv` first if it is not already available.

```powershell
python -m pip install uv
```

Restart the terminal after installation so PowerShell can pick up the updated
`PATH`.

```bash
uv sync
```

If PowerShell still cannot find `uv` after installing it with Python, run it as
a Python module:

```powershell
python -m uv sync
```

## Run

```bash
uv run python main.py
```

`main.py` starts both the gesture runtime and config UI by default. Press `q` to
quit the webcam window.

Run only one runtime with:

```bash
uv run python main.py gesture
uv run python main.py config
```

## Config UI

```bash
uv run python main.py config
```

Open `http://localhost`. When mDNS is available on the local network, the
UI is also advertised as `http://gesturetvremote.local`. Saved settings are
written to the local config database. Gesture, timing, voice-duration, and zoom
tuning changes are reloaded by the running gesture process; integration and
hardware settings still require restarting it.

## Test

Run the standard quality gate before finishing a change:

```bash
uv run python scripts/quality.py
```

The quality gate normalizes tracked and unignored `.py`, `.md`, and
`pyproject.toml` files to LF line breaks, runs Ruff with fixes, formats with
Black, reruns Ruff, runs mypy, and then runs the full unittest suite.

When iterating on tests only, run:

```bash
uv run python -m unittest discover -s tests
```

The current tests focus on pure domain behavior and adapter selection or command
translation. Hardware-dependent TV behavior should be covered through adapters
or integration tests when test doubles are available.

Test files are grouped by the layer or feature they validate:

- `tests/domain/`: pure gesture, session, evaluator, command, and motion behavior
- `tests/application/`: use-case orchestration, pipelines, ports, and dispatch flow
- `tests/infrastructure/`: adapter and integration-boundary behavior
- `tests/runtime/`: CLI, composition, and runtime runner behavior
- `tests/web/`: config UI request handling and rendering
- `tests/shared/`: configuration, logging, and shared primitives
- `tests/architecture/`: layer-boundary import checks
- `tests/fakes/`: reusable test doubles
- `tests/helpers/`: shared test data builders and helper functions

## Architecture Workflow

Use `docs/architecture.md` as the canonical layer guide. The short version:

- gesture rules and state transitions belong in `src/domain`
- use-case orchestration and ports belong in `src/application`
- OpenCV, MediaPipe, TV SDKs, SQLite, mDNS, and audio belong in `src/infrastructure`
- concrete wiring belongs in focused `src/runtime/builders/` modules, with
  final service composition in `src/runtime/container.py`
- config UI request handling belongs in `src/web`

Application code should depend on domain and application ports. Infrastructure
implements those ports. Runtime wires concrete implementations into application
services with explicit constructor injection.

## Adding a TV Platform

1. Add the adapter implementation under `src/infrastructure/tv/`.
2. Make the adapter satisfy `TVRemotePort` from `src/application/ports/tv_remote.py`.
3. Add adapter-neutral command translations in
   `src/infrastructure/tv/tv_command_translation.py`.
4. Register the adapter in `src/infrastructure/tv/tv_remote_factory.py` and the
   supported config values.
5. Add tests for factory selection, command translation, capability metadata,
   and adapter behavior using fakes.
6. Update `docs/configuration.md` and `docs/tv-adapter-capabilities.md`.

Do not put protocol-specific TV behavior in application or domain code.

## Adding Gesture Logic

Put deterministic gesture semantics in `src/domain`. Use the domain subpackage
that matches the responsibility:

- session lifecycle, state, result types, or debug snapshots -> `src/domain/session/`
- session phase or motion evaluators -> `src/domain/evaluators/`
- classification, activation tracking, preprocessing, history, or motion state -> `src/domain/gestures/`
- camera crop, landmark, or projection math -> `src/domain/geometry/`
- command mappings or command-transition rules -> `src/domain/commands/`

Only update `src/application` when orchestration changes are required, such as
new pipeline behavior or command dispatch flow. Infrastructure should not own
gesture decisions.

Add tests with synthetic landmarks or explicit timestamps. Normal tests must
not require a real webcam, TV, microphone, network, certificates, downloaded
model, or MediaPipe runtime.

## Adding Infrastructure

1. Check whether an application port already describes the boundary.
2. Define or update a port in `src/application/ports/` only when the application
   needs a real replaceable external boundary.
3. Implement the adapter under `src/infrastructure/`.
4. Wire the adapter in the relevant `src/runtime/builders/` module.
5. Add fakes or stubs for application tests and adapter-focused tests for the
   concrete integration.
6. Update architecture, configuration, or operational docs when behavior or
   setup changes.

Prefer Python `Protocol` ports and structural typing. Do not add a dependency
injection framework.

## Gesture Log Analysis

Gesture debug logs can be summarized with:

```bash
uv run python scripts/analyze_gesture_log.py logs/logs.txt
```

The analyzer reports command counts, candidate classifications, blocked reasons,
neutral frames, neutral zones, and threshold misses. Use it when tuning pointer
or volume motion behavior so threshold changes are based on measured log
patterns.
