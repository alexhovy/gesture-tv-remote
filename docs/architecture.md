# Architecture

Gesture TV Remote is organized around separate responsibilities instead of a
single script. The app is still small, but the boundaries make the gesture rules
testable and keep external libraries from leaking across the codebase.

## Layers

### API

`src/api` contains the runnable application entry point. It should stay thin and
only compose application services.

### Services

`src/services` contains use cases and orchestration. `GestureRemoteService`
coordinates webcam frames, hand tracking, gesture decisions, command dispatch,
debug logging, and cleanup. `VoiceCaptureService` handles the voice-input use
case when the selected TV adapter supports it.

### Domain

`src/domain` contains the business rules for gestures and commands:

- landmark math
- static gesture detection
- gesture-session state transitions
- shared gesture-session value types and motion filtering
- command mappings and debounce behavior

Domain code should not import OpenCV, MediaPipe, TV-control libraries, or audio
libraries.

### Infrastructure

`src/infrastructure` contains adapters for external systems:

- `tv`: TV remote pairing, command transport, and adapter command translation
- `hand_tracking`: MediaPipe hand tracking and model-file download
- `camera`: OpenCV frame preprocessing, crop geometry, projection, zoom, and overlays

Infrastructure modules may depend on third-party libraries, but domain modules
should not depend on infrastructure.

Repositories for durable local storage live under `src/infrastructure/repositories`.
They expose app-facing persistence APIs and own table shape and mapping.
Reusable stores under `src/infrastructure/data_access` own source mechanics such
as SQLite connection handling. This keeps data sources replaceable while typed
configuration remains represented as `AppConfig`.

TV control is adapter-based. `GestureRemoteService` asks the TV remote factory
for a client selected by configuration, then queues app-level TV commands such as
`HOME`, `BACK`, `DPAD_UP`, and `VOLUME_UP` through a service command dispatcher.
Each adapter translates those
commands to the protocol-specific command names for Android TV, Samsung TV,
webOS, or Roku. Voice capture is an adapter capability; currently only the
Android TV adapter exposes the voice stream used by `VoiceCaptureService`.
Adapters backed by synchronous TV libraries own their own single-worker
executor so connection objects are opened, used, reconnected, and closed on one
thread without blocking the gesture loop.

Camera preprocessing is split by responsibility inside `infrastructure/camera`:
latest-frame capture lives in `frame_source`, frame cropping lives in
`video_preprocessing`, coordinate projection lives in `landmark_projection`, and
auto-zoom state lives in `camera_zoom`. Camera capture keeps only the newest
frame so slow processing cannot build a stale frame backlog.

Hand tracking uses MediaPipe live-stream mode. The service submits frames and
consumes the latest completed result, allowing MediaPipe to skip frames while it
is busy instead of blocking the display and gesture loop.

### Shared

`src/shared` contains cross-cutting primitives such as configuration. Keep this
folder small; shared code should not become a dumping ground for unrelated
helpers.

## Design Rules

- Prefer domain functions for deterministic gesture rules.
- Keep I/O and third-party libraries behind infrastructure adapters.
- Add orchestration in services only when it represents an application workflow.
- Keep `main.py` and `src/api` free of business logic.
- Add tests around domain behavior before changing gesture semantics.
