# Gesture TV Remote

A modular gesture-controlled smart TV remote built around MediaPipe hand
tracking, configurable gesture recognition, multi-platform TV adapters, local
configuration, and a lightweight ports-and-adapters architecture.

Supported TV adapters:

- Android TV / Google TV through `androidtvremote2`
- Samsung TV through `samsungtvws`
- LG webOS TV through `aiowebostv`
- Roku through `rokuecp`

## Quick Start

Install `uv` first if it is not already available:

```powershell
python -m pip install uv
```

Restart the terminal after installation so PowerShell can pick up the updated
`PATH`.

```bash
uv sync
uv run python main.py
```

If PowerShell still cannot find `uv` after installing it with Python, run it as
a Python module:

```powershell
python -m uv sync
python -m uv run python main.py
```

Press `q` to quit the webcam window.

`main.py` starts the gesture runtime and config UI by default. To run only one
runtime:

```bash
uv run python main.py gesture
uv run python main.py config
uv run python main.py web-control
```

Open `http://localhost`.
When mDNS is available on your network, the same UI is advertised as
`http://gesturetvremote.local`.

`web-control` starts a unified web runtime: settings are available at `/` and
browser capture is available at `/control`. The browser provides camera and
microphone access over WebRTC while the Python backend still performs MediaPipe
hand tracking, gesture decisions, voice handling, and TV command dispatch.
Browser camera/microphone access requires a secure browser context; `web-control`
generates a local HTTPS certificate and uses `https://gesturetvremote.local/control`
by default. The generated certificate must be trusted by the capture device.

On first run, the app downloads Google's `hand_landmarker.task` model file into
`models/`. Pairing certificates are stored under `certs/`. Both are
ignored by git.

## Documentation

- [Architecture](docs/architecture.md)
- [Runtime Pipeline](docs/runtime-pipeline.md)
- [Configuration](docs/configuration.md)
- [Gestures](docs/gestures.md)
- [TV Adapter Capabilities](docs/tv-adapter-capabilities.md)
- [Development](docs/development.md)

## Architecture

The code is organized into domain rules, application use cases and ports,
infrastructure adapters, runtime composition, shared configuration, and the web
configuration UI. Concrete integrations such as OpenCV, MediaPipe, TV SDKs,
SQLite, mDNS, and audio stay behind infrastructure adapters wired in
`src/runtime/builders/` modules and composed in `src/runtime/container.py`.

## Configuration

The TV adapter defaults to `samsung` and the host defaults to `192.168.8.7`.
Runtime settings can be overridden with environment variables; see
[Configuration](docs/configuration.md).
