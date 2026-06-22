# Gesture State Machine

Gesture decisions are domain logic. They do not depend on OpenCV, MediaPipe,
audio, or TV adapter libraries.

## Data Flow

1. Infrastructure detects raw hands with landmarks and handedness.
2. `gesture_preprocessing.py` normalizes raw detected hands into center, size,
   upright status, and original landmarks.
3. `gesture_classification.py` classifies static hand poses.
4. `GestureSession` selects primary and secondary hands.
5. `activation_tracker.py` maintains primary activation and identity matching.
6. `motion_gesture.py` applies secondary motion grace and joystick state.
7. `command_decision.py` decides close chords and emit debounce.
8. `commands.py` maps command gestures to TV commands.

## Activation

An upright open palm activates the primary hand. Once active, the primary hand
is matched by distance from its previous position, upright status, and
primary-like gestures. Brief primary-hand dropouts stay active for
`GESTURE_TV_PRIMARY_LOST_GRACE_SECONDS`; after that grace interval the session
deactivates and clears pending command state.

## Static Poses

Static pose classification recognizes:

- `OPEN_PALM`
- `FIST`
- `PINCH`
- `POINT`
- `TWO_FINGERS`

Upright-hand validation applies when `GESTURE_TV_REQUIRE_UPRIGHT_HANDS` is
enabled.

## Motion Gestures

Secondary `POINT` controls DPAD movement. The index fingertip becomes the
tracked point when available; otherwise the hand center is used.

Secondary `PINCH` controls volume movement. The hand center Y coordinate is the
tracked point.

Pointer and volume gestures use joystick-style state:

- first point/pinch frame establishes an anchor
- the anchor stays fixed through unclassified secondary frames and brief hand
  dropouts while the primary session remains active
- pointer radius is measured against the displayed crop size
- motion must cross the activation margin outside the neutral circle or band
- the dominant direction emits immediately after leaving neutral
- holding the same direction repeats after the debounce interval
- changing direction requires returning inside neutral first

Recent motion data is stored in bounded histories so unstable input cannot grow
memory over time.

## Command Gestures

| Gesture event | Command gesture |
| --- | --- |
| Primary open palm closes to fist after chord window | `OPEN_TO_FIST` |
| Secondary open palm closes to fist after chord window | `BACK` |
| Primary and secondary close within chord window | `HOME` |
| Secondary pinch moves up/down | `VOLUME_UP` / `VOLUME_DOWN` |
| Secondary point moves left/right/up/down | `POINT_LEFT` / `POINT_RIGHT` / `POINT_UP` / `POINT_DOWN` |
| Secondary two fingers | `MIC` |

`commands.py` maps command gestures to adapter-neutral TV commands. `MIC` is
handled by voice capture instead of the key-command map.
