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
case.

### Domain

`src/domain` contains the business rules for gestures and commands:

- landmark math
- static gesture detection
- gesture-session state transitions
- command mappings and debounce behavior

Domain code should not import OpenCV, MediaPipe, `androidtvremote2`, or audio
libraries.

### Infrastructure

`src/infrastructure` contains adapters for external systems:

- Android TV remote pairing and command transport
- MediaPipe hand tracking
- model-file download
- OpenCV landmark drawing

Infrastructure modules may depend on third-party libraries, but domain modules
should not depend on infrastructure.

Camera preprocessing is split by responsibility: frame cropping lives in
`video_preprocessing`, coordinate projection lives in `landmark_projection`, and
auto-zoom state lives in `camera_zoom`.

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
