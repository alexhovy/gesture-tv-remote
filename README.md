# Gesture TV Remote

Python MVP for controlling a Google TV with webcam hand gestures.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Press `q` to quit the webcam window.

On first run, the app downloads Google's `hand_landmarker.task` model file into
`models/`. Pairing certificates are stored under `certs/`. Both are
ignored by git.

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Gestures](docs/gestures.md)
- [Development](docs/development.md)

## Configuration

The TV IP address defaults to `192.168.0.5`. Runtime settings can be overridden
with environment variables; see [Configuration](docs/configuration.md).
