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

Most commands are emitted once per gesture change. DPAD and volume gestures emit
once for each intentional movement away from neutral; holding the pointer or
pinch away from the starting point does not keep sending commands. Slow movement
below the command threshold still accumulates from that starting point until it
crosses the threshold. Moving the pointer or pinch substantially back toward
center suppresses opposite-direction commands while it is returning. The return
movement must settle near the new starting point before the same held gesture
can begin another intentional movement, including movement in a different
direction. Directly opposite movement after returning requires a larger motion
than the normal command threshold so returning to center does not send the
opposite command.
