# Architecture

Gesture TV Remote is organized around separate responsibilities instead of a
single script. The app is still small, but the boundaries make the gesture rules
testable and keep external libraries from leaking across the codebase.

## Layers

### Runtime

`src/runtime` contains runnable process composition. The CLI selects whether to
start the gesture runtime, config UI, or both. Runtime modules compose services,
repositories, mDNS publishing, and web servers while avoiding gesture business
logic or HTTP request handling.

### Web

`src/web` contains the lightweight config UI: HTTP routes, form parsing, and
HTML rendering. Web modules should depend on application-facing repositories and
typed config values, while process setup stays in `src/runtime`.

### Services

`src/services` contains use cases and orchestration. `GestureRemoteService`
owns application lifecycle and delegates runtime loop details to
`src/services/pipelines/` modules for frame capture, detection, gesture
decision, command dispatch, and display. `VoiceCaptureService` handles the
voice-input use case when the selected TV adapter supports it.

### Domain

`src/domain` contains the business rules for gestures and commands:

- landmark math
- raw-to-normalized hand preprocessing
- static hand-pose classification
- bounded motion and stability history
- activation tracking and gesture-session state transitions
- command mappings, command decisions, and debounce behavior

Domain code should not import OpenCV, MediaPipe, TV-control libraries, or audio
libraries.

Gesture sessions are coordinated by `GestureSession`, with focused state
collaborators:

- `gesture_preprocessing.py` converts raw detected hands into normalized hand data.
- `gesture_classification.py` classifies static hand poses.
- `gesture_history.py` provides bounded history buffers for recent motion state.
- `activation_tracker.py` owns primary-hand activation and identity matching.
- `motion_gesture.py` owns secondary motion grace and pointer/volume joystick state.
- `command_decision.py` owns close-chord decisions and emit debounce.
- `commands.py` keeps the gesture-to-TV-command mapping easy to inspect.

`GestureSession` does not expose collaborator state as a public compatibility
surface. Primary activation state, secondary motion grace, command chord
timing, emit debounce, and pointer/volume joystick state each have one owner.

The session transition model remains:

1. An upright open palm activates the primary hand.
2. The primary hand is matched by position and primary-like gestures while
   brief primary dropouts stay active for the configured grace interval.
3. A valid secondary hand can produce BACK, HOME chord, pointer, volume, or
   microphone gestures.
4. Pointer and volume gestures arm from a fixed anchor, emit after leaving the
   neutral area, repeat while held, and re-arm after returning to neutral.
5. Loss of activation clears pending chords and motion anchors.

### Infrastructure

`src/infrastructure` contains adapters for external systems:

- `tv`: TV remote pairing, command transport, and adapter command translation
- `hand_tracking`: MediaPipe hand tracking and model-file download
- `camera`: OpenCV frame preprocessing, crop geometry, projection, zoom, and overlays
- `network`: local network discovery such as mDNS publishing for the config UI

Infrastructure modules may depend on third-party libraries, but domain modules
should not depend on infrastructure.

Repositories for durable local storage live under `src/infrastructure/repositories`.
They expose app-facing persistence APIs and own table shape and mapping.
Reusable stores under `src/infrastructure/data_access` own source mechanics such
as SQLite connection handling. This keeps data sources replaceable while typed
configuration remains represented as `AppConfig`.

TV control is adapter-based. `GestureRemoteService` asks the TV remote factory
for a client selected by configuration, then queues app-level TV commands such as
`HOME`, `BACK`, `DPAD_UP`, and `VOLUME_UP` through a bounded service command
dispatcher.
Each adapter translates those
commands to the protocol-specific command names for Android TV, Samsung TV,
webOS, or Roku. Each adapter also exposes explicit capability metadata so
common commands can stay shared while platform gaps remain visible. Voice
capture is currently available only when the Android TV adapter returns a voice
stream.
Adapters backed by synchronous TV libraries own their own single-worker
executor so connection objects are opened, used, reconnected, and closed on one
thread without blocking the gesture loop.

Camera preprocessing is split by responsibility inside `infrastructure/camera`:
latest-frame capture lives in `frame_source`, frame cropping lives in
`video_preprocessing`, coordinate projection lives in `landmark_projection`, and
auto-zoom state lives in `camera_zoom`. Before a secondary hand is active,
MediaPipe detection uses a wider acquisition crop than the preview so the second
hand can enter without being forced into the primary-hand crop. After the
secondary hand is detected for several consecutive frames, detection uses the
precise preview crop for stable distance and motion math. If the secondary hand
drops out, detection returns to acquisition for reacquisition. Landmarks are
projected back to original frame space before gesture rules run. Camera capture
keeps only the newest frame so slow processing cannot build a stale frame
backlog.

Hand tracking uses MediaPipe live-stream mode. The service submits frames and
consumes the latest completed result, allowing MediaPipe to skip frames while it
is busy instead of blocking the display and gesture loop.

The runtime uses explicit producer/consumer boundaries:

- webcam capture runs in a dedicated latest-frame thread
- MediaPipe live-stream detection returns the latest completed hand result
- TV commands are sent by one bounded async dispatcher task
- synchronous Samsung and Roku adapters use one thread-bound executor each
- voice capture uses a bounded audio queue and drops stale buffered chunks
- saved config reloads are throttled and read through `asyncio.to_thread`

See `docs/runtime-pipeline.md` for the runtime pipeline and metrics model.

### Shared

`src/shared` contains cross-cutting primitives such as configuration. `AppConfig`
is grouped into TV, gesture, camera, model, web, debug, and performance sections
while environment variables and saved config fields remain named for the config
UI. Keep this folder small; shared code should not become a dumping ground for
unrelated helpers.

## Design Rules

- Prefer domain functions for deterministic gesture rules.
- Keep I/O and third-party libraries behind infrastructure adapters.
- Add orchestration in services only when it represents an application workflow.
- Keep `main.py` and `src/runtime` free of business logic.
- Add tests around domain behavior before changing gesture semantics.
