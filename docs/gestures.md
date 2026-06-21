# Gestures

Show one open palm first to activate gesture controls. That hand becomes the
primary hand. The other detected hand becomes the secondary hand.

## Commands

| Gesture | Command |
| --- | --- |
| Primary hand closes from open palm to fist | SELECT / DPAD_CENTER |
| Secondary hand closes from open palm to fist | BACK |
| Both hands close from open palm to fists within the chord window | HOME |
| Secondary pinch moves up | VOLUME_UP |
| Secondary pinch moves down | VOLUME_DOWN |
| Secondary pointing hand moves left | DPAD_LEFT |
| Secondary pointing hand moves right | DPAD_RIGHT |
| Secondary pointing hand moves up | DPAD_UP |
| Secondary pointing hand moves down | DPAD_DOWN |
| Secondary two-finger gesture | TV voice input |

## Gesture Ownership

The primary hand is used for activation, select, and the HOME chord. The
secondary hand is used for navigation, back, volume, and voice input.

Both primary and secondary gestures require upright hands when
`GESTURE_TV_REQUIRE_UPRIGHT_HANDS` is enabled. The primary hand must be an
upright open palm to activate controls.

## Debounce

Most commands are emitted once per gesture change. DPAD and volume gestures use
a joystick-style anchor. When the secondary hand first points or pinches, its
current position becomes the anchor. A small neutral zone around that anchor
recenters the anchor when the hand settles near rest.

Point navigation tracks the secondary index fingertip so left/right intent does
not depend on moving the whole hand. Moving outside the activation distance
emits the dominant direction. Holding the same direction does not repeat
commands. Returning inside the release zone for a short stable settle period
re-arms motion even when the fingertip does not land exactly in the smaller
neutral zone. Pointer gestures re-arm after two release frames by default.
Moving to a different direction before that release return is ignored so return
strokes do not become accidental opposite commands.

Display auto-zoom first makes a bounded adjustment if the secondary hand is
near or outside the visible crop, then freezes while the secondary hand is
present, including brief classification flicker during pointing or pinching.
This keeps both hands framed before stabilizing the preview for navigation or
volume changes; auto-zoom resumes when the secondary motion gesture is released.
