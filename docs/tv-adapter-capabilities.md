# TV Adapter Capabilities

The app keeps common commands adapter-neutral, but each TV platform has
different protocol support. Capability metadata is exposed through the
application TV remote port and implemented by the concrete TV adapters.
`TvAdapterCapabilities.supported_commands` is the runtime command contract:
`RemoteCommandDispatcher` drops and logs any adapter-neutral command that is not
advertised there instead of assuming every remote behaves the same.
Capability status is explicit:

- `implemented`: available through the current adapter code.
- `not_implemented`: the platform or library is expected to support this class
  of capability, but the app does not implement it yet.
- `unsupported`: not supported by the current protocol path or intentionally not
  available through this adapter.

| Adapter | Connection | Power | Volume | Navigation | Media Controls | Text Input | Text Focus Detection | Source Selection | Wake-on-LAN | Pairing | Remote Mic Stream | Native Voice UI | App Voice Input |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Android TV / Google TV | `androidtvremote2` TLS remote protocol | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` | `unsupported` | `unsupported` | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` |
| Samsung TV | `samsungtvws` websocket | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` | `not_implemented` | `implemented` | `implemented` | `unsupported` | `implemented` | `unsupported` |
| LG webOS | `aiowebostv` websocket | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `implemented` | `not_implemented` | `not_implemented` | `implemented` | `implemented` | `unsupported` | `unsupported` | `unsupported` |
| Roku | Roku ECP HTTP | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` | `unsupported` | `not_implemented` | `implemented` | `unsupported` | `unsupported` | `implemented` | `unsupported` |
| Apple TV | `pyatv` Media Remote Protocol | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` | `implemented` | `unsupported` | `implemented` | `implemented` | `unsupported` | `unsupported` | `unsupported` |

## Common Commands

All current adapters implement translations for:

- `HOME`
- `BACK`
- `DPAD_CENTER`
- `DPAD_LEFT`
- `DPAD_RIGHT`
- `DPAD_UP`
- `DPAD_DOWN`
- `VOLUME_UP`
- `VOLUME_DOWN`

The gesture layer emits these common commands through the dispatcher. Each
adapter advertises its supported adapter-neutral commands from the same mapping
used for protocol translation. Adapter translations live in
`src/infrastructure/tv/tv_command_translation.py`.

The direct remote UI can expose additional adapter-neutral commands when the
selected adapter advertises them:

- `POWER_TOGGLE`: Android TV / Google TV and Samsung.
- `POWER_ON`: Apple TV.
- `POWER_OFF`: Roku TV devices and Apple TV.
- `MUTE`: Android TV / Google TV, Samsung, and Roku TV devices.
- `PLAY_PAUSE`, `REWIND`, `FAST_FORWARD`: Android TV / Google TV, Samsung,
  Roku, and Apple TV.

Direct remote button presses preserve repeated commands, such as rapid DPAD or
volume taps, instead of using the gesture queue's repeat coalescing.

## Text Input

The browser remote and gesture pages use a visible overlay input when the
selected adapter can send text. Some adapters can also report when a TV text
field is focused; when that happens the browser attempts to focus the overlay
input so the device keyboard can open and the typed value stays visible on the
browser. Adapters without reliable focus detection use the same overlay in
manual mode after a browser tap. Browser edits are synced as a full value:
adapters with replacement APIs receive the full current value, and append-only
adapters delete the last value mirrored by the overlay before sending the new
full value. Append-only adapters can only clear text that was previously
mirrored by this browser session.

- Android TV sends literal inserts through `androidtvremote2` text input and
  connects with Android IME feature negotiation disabled so focus is captured
  manually in the browser instead of relying on protocol focus detection.
- Apple TV uses pyatv's Companion keyboard interface for focus state and text
  append/set/clear operations when the connected device advertises those
  features.
- Samsung uses `samsungtvws` IME start/end websocket events when the TV emits
  them and sends text with the websocket text-input command. Model and firmware
  behavior varies, so manual keyboard mode remains useful.
- LG webOS sends text through `com.webos.service.ime` operations. Focus
  subscription exists in the webOS IME service, but the current aiowebostv path
  does not expose it as a stable high-level API.
- Roku sends literal keyboard characters through ECP `Lit_` keypresses. ECP
  does not expose a general "text field focused" event, so this is manual mode.

For adapters that do not reliably emit a keyboard-hide event, `Back`, `Home`,
power commands, and text submit clear the app's cached keyboard-active state so
the browser can dismiss its local keyboard capture.

## Platform Gaps

Power, media controls, and text input are available to the direct remote when
the selected adapter advertises those capabilities. Text input capture is also
loaded on the gesture page, while gesture commands remain limited to the mapped
TV command set. Source selection is tracked as
`not_implemented` when an adapter extension could reasonably add it without
changing the gesture pipeline.

Power behavior varies by protocol:

- Android TV / Google TV and Samsung expose a power toggle key.
- Roku ECP exposes `PowerOff` for Roku TV devices; standalone Roku streaming
  players may not support TV power control.
- Apple TV exposes separate `turn_on` and `turn_off` through pyatv power
  management.
- All adapters can send a generic Wake-on-LAN magic packet before connecting
  when `tv_mac_address` is known and `tv_wake_enabled` is true.
- Android TV / Google TV can learn a MAC address from the Android TV Remote
  Protocol pairing certificate.
- Roku can learn the active network MAC address from ECP `query/device-info`
  while the device is awake.
- Apple TV can learn a MAC address from pyatv scan/device metadata when that
  metadata is available, and can use pyatv power management after connecting.
- Samsung can learn the reported Wi-Fi MAC from the REST device info endpoint
  and saves it as the Wake-on-LAN candidate. Some Samsung TVs report wired
  networking while still exposing only `wifiMac`, so wake success depends on
  model and network standby behavior.
- LG webOS can use Wake-on-LAN when a MAC address is known. The app tries webOS
  connection-manager and system payloads after a successful connection, then
  falls back to local neighbor/ARP discovery. LG does not expose a reliable
  public MAC-address API across all webOS TV models, so manual entry or router
  lookup can still be required.

Voice input is split by protocol capability:

- auto target: a gesture-triggered voice request uses the adapter's TV/global
  voice route. App voice input is started by a TV/app voice-session request,
  not by the gesture.
- remote mic stream: this app sends microphone PCM audio to the TV. Android TV
  supports this through Android TV Remote Protocol voice payloads.
- native voice UI: this app only asks the TV to open its own voice listener.
  Roku uses ECP `Search`; Samsung uses `KEY_VOICE`; neither path accepts this
  app's microphone audio through the current adapter.
- app voice input: this app sends microphone PCM audio to a foreground app's
  active voice listener after the TV reports that the foreground app requested
  one. Android TV supports this by attaching to an app-requested Android TV
  Remote Protocol voice session. Roku, Samsung, and webOS do not expose public
  raw microphone upload paths for arbitrary foreground apps through the current
  adapters.
