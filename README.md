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

Hold an open palm for 1 second to send `HOME`.

Close an open palm into a fist to send `SELECT` / `DPAD_CENTER`.

Swipe left, right, up, or down to send the matching DPAD arrow.

Thumbs up sends `VOLUME_UP`.

Thumbs down sends `VOLUME_DOWN`.

Point with one finger to send `BACK`.

Hold up two fingers to send `PLAY_PAUSE`.

The TV IP address is currently hardcoded in `main.py`:

```python
TV_IP = "192.168.0.5"
```

## Architecture

OpenCV captures frames from the default webcam and displays the live feed.

MediaPipe detects one hand and provides hand landmarks.

Simple landmark rules classify static gestures, transitions, and swipes.

`androidtvremote2` sends the matching remote command to the Google TV.
