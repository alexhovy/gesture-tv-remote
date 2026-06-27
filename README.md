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
```

Open `http://localhost`.
When mDNS is available on your network, the same UI is advertised as
`http://gesturetvremote.local`.

On first run, the app downloads Google's `hand_landmarker.task` model file into
`models/`. Pairing certificates are stored under `certs/`. Both are
ignored by git.

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Gestures](docs/gestures.md)
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
