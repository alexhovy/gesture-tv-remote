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

Show one open palm first to activate gesture controls. That hand becomes the
primary hand. The other hand becomes the secondary hand.

Close the primary hand from open palm into a fist to send `SELECT` /
`DPAD_CENTER`.

Close the secondary hand from open palm into a fist to send `BACK`.

Close both hands from open palm into fists at about the same time to send
`HOME`.

Pinch with the secondary hand, then move it up to send `VOLUME_UP` or down to
send `VOLUME_DOWN`.

Point with the secondary hand's index finger and move it left, right, up, or
down to send the matching DPAD arrow.

Hold up two fingers with the secondary hand to start a short microphone capture
for TV voice input.

The TV IP address is currently hardcoded in `main.py`:

```python
TV_IP = "192.168.0.5"
```

## Architecture

OpenCV captures frames from the default webcam and displays the live feed.

MediaPipe detects up to two hands and provides hand landmarks.

Simple landmark rules classify static gestures, transitions, pointing, and
pinches.

`androidtvremote2` sends the matching remote command to the Google TV.
