# Architecture

Gesture TV Remote uses a lightweight Clean Architecture / Ports and Adapters
layout. The codebase stays small, but the dependency direction is explicit:
domain rules are pure, application use cases depend on ports, infrastructure
implements those ports, and runtime wires concrete objects together.

```text
runtime/web
    -> application
        -> domain

infrastructure
    -> application ports
        -> domain
```

Runtime and web are entry points. Application owns use cases and ports. Domain
owns gesture rules. Infrastructure owns concrete libraries, devices, network
protocols, and storage.

## Repository Structure

```text
src/
├── domain/
├── application/
│   ├── ports/
│   ├── pipelines/
│   └── services/
├── infrastructure/
├── runtime/
├── shared/
└── web/
```

### `src/domain`

Responsibility:

- gesture state and activation
- gesture classification
- gesture decisions and command mapping
- motion filtering and joystick-style motion state
- pure camera geometry and landmark projection values

Allowed dependencies:

- Python standard library
- other domain modules
- small shared configuration value objects when needed by existing domain rules

Do not put here:

- OpenCV, MediaPipe, TV SDK, audio, storage, network, runtime, or web imports
- process orchestration
- adapter selection
- persistence or configuration loading

### `src/application`

Responsibility:

- use cases and orchestration
- application services
- runtime pipelines
- ports that describe external boundaries
- application-level command dispatch and metrics

Allowed dependencies:

- `src/domain`
- `src/application/ports`
- small shared value objects such as `AppConfig`

Do not put here:

- OpenCV, MediaPipe, TV SDK, audio, SQLite, mDNS, or web framework imports
- construction of concrete infrastructure adapters
- gesture business rules that can be deterministic domain logic

### `src/infrastructure`

Responsibility:

- MediaPipe hand tracking and model storage
- OpenCV frame capture, preprocessing, display rendering, and overlays
- TV adapters and protocol-specific command translation
- SQLite-backed config persistence
- mDNS publishing
- microphone and voice-stream integration

Allowed dependencies:

- `src/application/ports`
- `src/domain`
- concrete third-party libraries and hardware/network integrations
- `src/shared` value objects and logging

Do not put here:

- runtime process composition
- HTTP route handling
- gesture decisions or activation rules

### `src/runtime`

Responsibility:

- CLI runtime selection
- configuration bootstrap
- dependency wiring in `src/runtime/container.py`
- construction of concrete infrastructure adapters
- returning fully constructed application/runtime objects

Allowed dependencies:

- application, infrastructure, web, shared config, and logging

Do not put here:

- gesture decisions
- adapter protocol behavior
- HTTP request handling
- reusable business logic

### `src/web`

Responsibility:

- lightweight configuration UI
- HTTP endpoints
- form parsing
- HTML/static rendering

Allowed dependencies:

- application-facing config ports
- shared config values
- web-local rendering and form helpers

Do not put here:

- direct infrastructure construction
- gesture logic
- runtime process orchestration

### `src/shared`

Responsibility:

- small cross-cutting primitives such as configuration and logging

Do not put here:

- broad utility collections
- business rules
- infrastructure adapters

## Architecture Principles

### Domain

Domain code must remain framework-independent. It contains gesture state,
classification, activation, motion filtering, gesture decisions, and command
mapping. It must not import infrastructure or runtime code.

### Application

Application code contains use cases, orchestration, pipelines, ports, and
application services. It depends on domain and application ports. It does not
construct infrastructure directly; concrete collaborators are passed through
constructors.

### Infrastructure

Infrastructure implements application ports with concrete integrations:
MediaPipe, OpenCV, TV adapters, SQLite storage, mDNS, and audio. Infrastructure
may translate between third-party APIs and application/domain types, but it must
not own gesture business rules.

### Runtime

Runtime is the composition root. It reads configuration, creates concrete
infrastructure implementations, prepares required runtime resources, and wires
application services explicitly in `src/runtime/container.py`.

### Web

Web is an external adapter for user interaction. It provides the local
configuration UI and HTTP endpoints, using application-facing ports for saved
configuration.

## Ports and Adapters

Ports isolate application logic from concrete infrastructure. They live in
`src/application/ports/` and are defined with `typing.Protocol` so adapters can
use structural typing instead of inheriting from heavy abstract base classes.

Current examples include:

- `TVRemotePort`
- `HandTrackerPort`
- `FrameSourcePort`
- `FrameProcessorPort`
- `DisplayPort`
- `VoiceCapturePort`
- `ConfigProviderPort`
- `ConfigStorePort`

Infrastructure adapters satisfy these contracts structurally. For example,
MediaPipe tracking implements `HandTrackerPort`, OpenCV frame capture implements
`FrameSourcePort`, TV clients implement `TVRemotePort`, and the SQLite config
repository implements `ConfigStorePort`.

Use a port when application code needs a replaceable external boundary. Do not
create interfaces for small pure-domain helpers or objects that are not
meaningful external boundaries.

## Runtime Flow

The CLI in `src/runtime/cli.py` selects the gesture runtime, config UI, or both.
`src/runtime/container.py` builds the concrete object graph:

1. load environment and saved configuration
2. create config repositories and providers
3. prepare the MediaPipe model file before constructing the hand tracker
4. create TV, camera, display, hand-tracking, audio, metrics, and command
   dispatcher adapters
5. inject those collaborators into `GestureRemoteService`

`GestureRemoteService` then owns the gesture runtime lifecycle: connect, start
frame capture, evaluate gestures, dispatch commands, reload live config, and
clean up.

See `docs/runtime-pipeline.md` for runtime pipeline and concurrency details.

## Boundary Enforcement

Architecture tests in `tests/architecture/test_layer_boundaries.py` scan imports
and fail when forbidden layer dependencies are introduced. They also reject
dynamic import escape hatches in domain and application code.

## Design Rules

- Prefer domain functions for deterministic gesture rules.
- Keep I/O and third-party libraries behind infrastructure adapters.
- Add orchestration in application only when it represents a use case workflow.
- Wire dependencies explicitly in `src/runtime/container.py`.
- Use constructor injection and `Protocol` ports; do not add a DI framework.
- Keep `main.py` and `src/runtime` free of business logic.
- Add tests around domain behavior before changing gesture semantics.
- Add or update layer-boundary tests when changing dependency rules.
