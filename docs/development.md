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

`main.py` starts the unified web app by default.

Run only one runtime with:

```bash
uv run python main.py app
uv run python main.py local-gesture
uv run python main.py settings
```

The app runtime serves settings at `/settings`, browser gesture capture at
`/gesture`, and the direct remote at `/remote`. All web runtimes generate a
local HTTPS certificate when missing. When the web port is still the default,
they listen on HTTPS port `443`. Trust the generated certificate on web devices
so browser media permissions are available.

`local-gesture` uses the local webcam and microphone attached to the machine
running Python. Press `q` to quit its OpenCV preview window.

## Config UI

```bash
uv run python main.py settings
```

Open `https://localhost`. When mDNS is available on the local network, the
UI is also advertised as `https://gesturetvremote.local`. Saved settings are
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
- `tests/web/`: web UI request handling, rendering, shared navigation, and assets
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
- web UI request handling, Jinja templates, and static assets belong in `src/web`

Application code should depend on domain and application ports. Infrastructure
implements those ports. Runtime wires concrete implementations into application
services with explicit constructor injection.

## Golden Path: Add a Gesture

1. Decide whether the gesture is a classification, session transition, motion
   interaction, or command mapping.
2. Put deterministic recognition or state rules in the matching domain package:
   `src/domain/gestures/`, `src/domain/evaluators/`, or `src/domain/session/`.
3. Add a gesture name or TV command constant in `src/domain/constants.py` when
   the new behavior needs a stable public name.
4. If the gesture emits a TV command, map it in
   `src/domain/commands/commands.py`. Keep the command adapter-neutral.
5. Update application code only when the runtime workflow changes, such as a new
   dispatch branch in `src/application/pipelines/command_dispatch.py`.
6. Add focused domain tests under `tests/domain/` with synthetic landmarks,
   explicit timestamps, and no hardware dependencies. Add application tests only
   when orchestration changes.
7. Update `docs/gestures.md` when user-visible gesture semantics or command
   behavior changes.

## Golden Path: Add a TV Adapter

1. Add the adapter implementation under `src/infrastructure/tv/`.
2. Make the adapter satisfy `TVRemotePort` from `src/application/ports/tv_remote.py`.
3. Expose accurate `TvAdapterCapabilities`, including
   `supported_commands`, connection type, pairing, voice, and known limitations.
4. Add adapter-neutral command translations in
   `src/infrastructure/tv/tv_command_translation.py`.
5. Register the adapter in `src/infrastructure/tv/tv_remote_factory.py`,
   `src/shared/config.py`, and the settings UI adapter list in
   `src/web/settings/view.py`.
6. Add tests for factory selection, command translation, capability metadata,
   and adapter behavior using fakes.
7. Update `docs/configuration.md` and `docs/tv-adapter-capabilities.md`.

Do not put protocol-specific TV behavior in application or domain code.

## Gesture Logic Placement Reference

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
