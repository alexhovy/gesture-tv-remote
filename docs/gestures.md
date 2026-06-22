# Gestures

Show one upright open palm to activate gesture controls. That same active hand
then performs every command gesture. An open palm is neutral.

## Commands

| Gesture | Command |
| --- | --- |
| Open palm closes to fist, then opens again | SELECT / DPAD_CENTER |
| Fist held past the hold threshold | HOME |
| Two fingers held briefly, then open palm | BACK |
| Pinch moves up | VOLUME_UP |
| Pinch moves down | VOLUME_DOWN |
| Pointing hand moves left | DPAD_LEFT |
| Pointing hand moves right | DPAD_RIGHT |
| Pointing hand moves up | DPAD_UP |
| Pointing hand moves down | DPAD_DOWN |

## Gesture Ownership

The active hand is selected by the first upright open palm. While the session is
active, that hand is matched by position and must remain upright when
`GESTURE_TV_REQUIRE_UPRIGHT_HANDS` is enabled. Extra detected hands are ignored
for command decisions and auto-zoom framing.

Point and pinch gestures are only commandable once the active hand is large
enough relative to the active camera crop to classify reliably. Small point and
pinch frames preserve any existing motion anchor instead of redefining the
joystick center.

## Debounce

Most commands are emitted once per gesture change. DPAD and volume gestures use
a joystick-style anchor. When the active hand first points or pinches, its
current position becomes the anchor for measuring motion.

Select emits when the active hand closes from open palm to fist and opens again
before the HOME hold threshold. Holding the fist through
`GESTURE_TV_FIST_HOLD_HOME_SECONDS` emits HOME once, then waits for the hand to
open before another fist command can occur.

BACK emits when the active hand holds two fingers up for several consecutive
frames and then returns to an open palm. A single two-finger misread does not
emit BACK, and point, pinch, fist, unknown, or missing-hand frames reset the
pending BACK gesture.

Point navigation tracks the active hand's index fingertip so left/right intent
does not depend on moving the whole hand. The first point frame captures a fixed
center and draws a crop-relative neutral circle around it, keeping the visible
circle size stable while auto-zoom changes. Moving outside that circle emits the
dominant direction only after crossing a small activation margin. Returning
inside the circle re-arms pointer navigation without moving the center. Holding
the same direction repeats after the command debounce interval, while changing
direction requires returning to neutral first. Volume gestures use the same
fixed-center idea as a vertical neutral band around the first pinch position.

The camera preview draws joystick diagnostics while point navigation or pinch
volume is active: the fixed joystick center, neutral area, directional
boundaries, current hand position, and the active or blocked state. Use that
overlay to verify whether the hand entered the center return area before
attempting the next direction.
While a pointer or volume anchor exists, the preview crop is locked so the
neutral center does not move on screen during motion or grace.

Auto-zoom uses separate crops for MediaPipe detection and display. The display
crop follows the active hand, while the detection crop stays wider and catches
up only when the hand is safely inside view. Brief dropouts and unclassified
active-hand frames keep existing pointer or volume anchors during motion grace.
A clear pose outside that active motion, such as an open palm or fist, clears
the motion anchor immediately because the user has stopped pointer or volume
control. Switching between point and pinch also clears the previous motion
anchor and starts the new motion mode.
