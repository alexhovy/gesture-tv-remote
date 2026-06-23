# Architecture

Gesture TV Remote uses a lightweight Clean Architecture / Ports and Adapters
layout. The codebase stays small, but the dependency direction is explicit:
domain rules are pure, application use cases depend on ports, infrastructure
implements those ports, and runtime wires concrete objects together.

## Layers

### Domain

`src/domain` contains pure gesture and command rules:

- landmark math and projection value objects
- raw-to-normalized hand preprocessing
- static hand-pose classification
- bounded motion and stability history
- activation tracking and gesture-session state transitions
- command mappings, command decisions, and debounce behavior

Domain code must not import OpenCV, MediaPipe, TV-control libraries, audio
libraries, SQLite/storage libraries, web modules, infrastructure modules, or
runtime composition code.

Gesture sessions are coordinated by `GestureSession`, with focused state
collaborators:

- `gesture_preprocessing.py` converts raw detected hands into normalized hand data.
- `gesture_classification.py` classifies static hand poses.
- `gesture_history.py` provides bounded history buffers for recent motion state.
- `activation_tracker.py` owns active-hand activation and identity matching.
- `motion_gesture.py` owns motion grace and pointer/volume joystick state.
- `command_decision.py` owns fist select/home decisions and emit debounce.
- `commands.py` keeps the gesture-to-TV-command mapping easy to inspect.

The session transition model remains:

1. An upright open palm activates the active hand.
2. The active hand is matched by position while brief dropouts stay active for
   the configured grace interval.
3. The active hand can produce select, HOME, BACK, pointer, or volume gestures.
4. Pointer and volume gestures arm from a fixed anchor, emit after leaving the
   neutral area, repeat while held, and re-arm after returning to neutral.
5. Loss of activation clears pending fist decisions and motion anchors.

### Application

`src/application` contains use cases, orchestration, pipelines, metrics, command
dispatch, and application ports. Application code may depend on domain code and
application ports. It must not import concrete infrastructure adapters or
third-party integration libraries such as OpenCV, MediaPipe, TV SDKs,
`sounddevice`, `sqlite3`, or `zeroconf`.

`GestureRemoteService` owns the gesture runtime lifecycle: connect, start frame
capture, run detection and gesture decisions, dispatch commands, reload live
config, and clean up. It receives all external collaborators through explicit
constructor injection.

Application ports live in `src/application/ports/` and describe real external
boundaries such as TV remotes, hand tracking, frame sources, frame processing,
display rendering, voice capture, config storage, logging, metrics, models, and
camera zoom state. The project intentionally uses Python `Protocol` and
structural typing instead of a dependency injection framework.

### Infrastructure

`src/infrastructure` contains concrete adapters for external systems:

- `tv`: TV remote pairing, command transport, and adapter command translation
- `hand_tracking`: MediaPipe hand tracking and model-file download
- `camera`: OpenCV frame capture, preprocessing, display rendering, zoom, and overlays
- `audio`: microphone capture and TV voice-stream forwarding
- `network`: local network discovery such as mDNS publishing for the config UI
- `repositories` and `data_access`: local config persistence and SQLite access

Infrastructure may depend on application ports and domain objects. It must not
import runtime or web modules.

TV control is adapter-based. Runtime creates the selected TV adapter and injects
it behind the TV remote port. Application command dispatch queues app-level TV
commands such as `HOME`, `BACK`, `DPAD_UP`, and `VOLUME_UP`; each TV adapter
translates those commands to protocol-specific names for Android TV, Samsung TV,
webOS, or Roku.

Camera preprocessing is split by responsibility: latest-frame capture lives in
`frame_source`, frame cropping lives in `video_preprocessing`, OpenCV frame
operations live in `frame_processor`, display rendering lives in `display`, and
auto-zoom state lives in `camera_zoom`. Pure crop geometry and landmark
projection live in domain where application code can use them without importing
OpenCV.

### Runtime

`src/runtime` is the composition root. The CLI selects whether to start the
gesture runtime, config UI, or both. `src/runtime/container.py` reads config,
creates concrete infrastructure implementations, wires application services,
and returns fully constructed runtime objects.

Runtime may import infrastructure, application, web, shared config, and logging
because its job is dependency wiring. It should still avoid gesture decisions,
HTTP request handling, and transport behavior.

The runtime uses explicit producer/consumer boundaries:

- webcam capture runs in a dedicated latest-frame thread
- MediaPipe live-stream detection returns the latest completed hand result
- TV commands are sent by one bounded async dispatcher task
- synchronous Samsung and Roku adapters use one thread-bound executor each
- voice capture uses a bounded audio queue and drops stale buffered chunks
- saved config reloads are throttled and read through `asyncio.to_thread`

See `docs/runtime-pipeline.md` for the runtime pipeline and metrics model.

### Web

`src/web` contains the lightweight config UI: HTTP routes, form parsing, static
assets, and HTML rendering. Web code depends on application-facing config ports
and typed config values. It should not construct infrastructure directly;
runtime passes the concrete config store into the web server factory.

### Shared

`src/shared` contains small cross-cutting primitives such as configuration and
logging. `AppConfig` is grouped into TV, gesture, camera, model, web, debug, and
performance sections while environment variables and saved config fields remain
named for the config UI. Keep this folder small; shared code should not become a
dumping ground for unrelated helpers.

## Design Rules

- Prefer domain functions for deterministic gesture rules.
- Keep I/O and third-party libraries behind infrastructure adapters.
- Add orchestration in application only when it represents a use case workflow.
- Wire dependencies explicitly in `src/runtime/container.py`.
- Use constructor injection and `Protocol` ports; do not add a DI framework.
- Keep `main.py` and `src/runtime` free of business logic.
- Add tests around domain behavior before changing gesture semantics.
- Add layer-boundary tests when changing dependency rules.
