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

Keep one hand open to activate gesture controls. The other hand performs the
command gesture.

With the activation hand open, close the other hand from open palm into a fist,
then release without moving far to send `SELECT` / `DPAD_CENTER`.

Repeat the select gesture twice in a row to send `HOME`.

With the activation hand open, make a fist with the other hand and drag it
left, right, up, or down to send the matching DPAD arrow.

With the activation hand open, show an open palm with the other hand and push it
away from the camera to send `BACK`.

With the activation hand open, show an open palm with the other hand, then move
it up to send `VOLUME_UP` or down to send `VOLUME_DOWN`.

With the activation hand open, hold up two fingers to send `PLAY_PAUSE`.

The TV IP address is currently hardcoded in `main.py`:

```python
TV_IP = "192.168.0.5"
```

## Architecture

OpenCV captures frames from the default webcam and displays the live feed.

MediaPipe detects one hand and provides hand landmarks.

Simple landmark rules classify static gestures, transitions, and swipes.

`androidtvremote2` sends the matching remote command to the Google TV.
