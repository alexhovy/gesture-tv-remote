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

Secondary command poses are only commandable once the detected hand is large
enough to classify reliably. Very small secondary point, pinch, fist, and
two-finger detections still keep the secondary hand present for zoom tracking,
but they do not emit commands. Small point and pinch frames preserve any
existing motion anchor instead of redefining the joystick center. Discrete
secondary command poses such as fist and two fingers must also remain stable for
a few frames before BACK, HOME, or voice input can trigger.

## Debounce

Most commands are emitted once per gesture change. DPAD and volume gestures use
a joystick-style anchor. When the secondary hand first points or pinches, its
current position becomes the anchor for measuring motion.

Point navigation tracks the secondary index fingertip so left/right intent does
not depend on moving the whole hand. The first point frame captures a fixed
center and draws a crop-relative neutral circle around it, keeping the visible
circle size stable while auto-zoom changes. Moving outside that circle emits the
dominant direction only after crossing a small activation margin. Returning
inside the circle re-arms pointer navigation without moving the center. Holding
the same direction repeats after the command debounce interval, while changing
direction requires returning to neutral first. Volume gestures use the same
fixed-center idea as a vertical neutral band around the first pinch position.

The camera preview draws pointer diagnostics while point navigation is active:
the fixed joystick center, neutral area, directional boundaries, current
fingertip, and the active or blocked state. Use that overlay to verify whether
the finger entered the center return area before attempting the next direction.

Auto-zoom has acquisition and stabilizing detection modes. When only the primary
hand is active, MediaPipe uses a wider detection crop than the preview so the
secondary hand can be lifted naturally beside the primary. Once the secondary
hand first appears, detection stays wide while the secondary hand remains active
or in grace. The preview can still show the tighter zoom crop, but MediaPipe
detection does not switch to that tight crop during two-hand tracking. This
keeps both hands easy to acquire and prevents the preview crop from making
far-away hands flicker in and out of detection.
