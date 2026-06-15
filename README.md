# Gesture TV Remote

Minimal Python MVP for controlling a Google TV with webcam hand gestures.

## Setup

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

On first run, the app downloads Google's `hand_landmarker.task` model file
into the project directory. That file is ignored by git.

## Run

```bash
python main.py
```

Press `q` to quit the webcam window.

## Gestures

Open palm sends `HOME`.

Closed fist sends `SELECT` / `DPAD_CENTER`.

Thumbs up sends `VOLUME_UP`.

The TV IP address is currently hardcoded in `main.py`:

```python
TV_IP = "192.168.1.100"
```

## Architecture

OpenCV captures frames from the default webcam and displays the live feed.

MediaPipe detects one hand and provides hand landmarks.

Simple landmark rules classify the hand as open palm, fist, or thumbs up.

`androidtvremote2` sends the matching remote command to the Google TV.
