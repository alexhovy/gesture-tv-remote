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
| Secondary index point moves left | DPAD_LEFT |
| Secondary index point moves right | DPAD_RIGHT |
| Secondary index point moves up | DPAD_UP |
| Secondary index point moves down | DPAD_DOWN |
| Secondary two-finger gesture | TV voice input |

## Gesture Ownership

The primary hand is used for activation, select, and the HOME chord. The
secondary hand is used for navigation, back, volume, and voice input.

Both primary and secondary gestures require upright hands when
`GESTURE_TV_REQUIRE_UPRIGHT_HANDS` is enabled. The primary hand must be an
upright open palm to activate controls.

## Debounce

Most commands are emitted once per gesture change. DPAD and volume commands may
repeat after the configured debounce interval while the gesture is held away
from its starting point. Slow movement below the command threshold still
accumulates from that starting point until it crosses the threshold. Small hold
jitter still repeats. Moving the pointer or pinch substantially back toward
center suppresses further repeats until the gesture reaches neutral, which
resets the starting point for the next intentional movement.
