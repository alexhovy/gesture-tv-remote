# Gesture State Machine

Gesture decisions are domain logic. They do not depend on OpenCV, MediaPipe,
audio, or TV adapter libraries.

## Data Flow

1. Infrastructure detects raw hands with landmarks and handedness.
2. `domain/gestures/gesture_preprocessing.py` collapses duplicate detections
   of the same physical hand, then normalizes raw detected hands into center,
   size, upright status, and original landmarks.
3. `domain/gestures/gesture_classification.py` classifies static hand poses.
4. `GestureSession` in `domain/session/` dispatches to inactive, lost, or
   active session evaluators.
5. `domain/gestures/activation_tracker.py` maintains active-hand activation and
   identity matching.
6. `domain/evaluators/` applies session phase rules and coordinates pointer or
   volume motion interactions.
7. `domain/commands/command_decision.py` decides fist select/home transitions,
   two-finger BACK, and emit debounce.
8. `domain/commands/commands.py` maps command gestures to TV commands.

## Activation

Two upright open palms activate the session. Once active, the selected hand is
matched by distance from its previous position. If that hand drops out while
another upright open palm remains visible, the session hands off to the visible
palm and clears pending command or motion state. If no continuation palm is
visible, brief full dropouts stay active for
`GESTURE_TV_ACTIVE_HAND_LOST_GRACE_SECONDS`. After that grace interval the
session deactivates and clears pending command state.

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

Active-hand `POINT` controls DPAD movement. The index fingertip becomes the
tracked point when available; otherwise the hand center is used.

Active-hand `PINCH` controls volume movement. The hand center Y coordinate is
the tracked point.

Pointer and volume gestures use joystick-style state:

- first point/pinch frame establishes an anchor
- the anchor stays fixed through unclassified frames and brief hand dropouts
  while the session remains active
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
| Open palm closes four non-thumb fingers to fist and opens before hold threshold | `OPEN_TO_FIST` |
| Four non-thumb fingers held closed through hold threshold | `HOME` |
| Two fingers held for several frames, then open palm | `BACK` |
| Pinch moves up/down | `VOLUME_UP` / `VOLUME_DOWN` |
| Point moves left/right/up/down | `POINT_LEFT` / `POINT_RIGHT` / `POINT_UP` / `POINT_DOWN` |

Fist select/HOME tolerates one or two unclassified active-hand frames inside the
open/fist/open sequence. Two-finger BACK tolerates one unclassified active-hand
frame while the BACK gesture is pending. This grace is command-specific and does
not relax activation, pointer motion, volume motion, or expired lost-hand
handling.

`domain/commands/commands.py` maps command gestures to adapter-neutral TV
commands.
