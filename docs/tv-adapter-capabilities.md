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

| Adapter | Connection | Power | Volume | Navigation | Media Controls | Text Input | Source Selection | Wake-on-LAN | Pairing | Remote Mic Stream | Native Voice UI | App Voice Input |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Android TV / Google TV | `androidtvremote2` TLS remote protocol | `implemented` | `implemented` | `implemented` | `implemented` | `not_implemented` | `unsupported` | `unsupported` | `implemented` | `implemented` | `implemented` | `implemented` |
| Samsung TV | `samsungtvws` websocket | `implemented` | `implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `implemented` | `unsupported` | `implemented` | `unsupported` |
| LG webOS | `aiowebostv` websocket | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `implemented` | `unsupported` | `unsupported` | `unsupported` |
| Roku | Roku ECP HTTP | `implemented` | `implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `unsupported` | `unsupported` | `unsupported` | `implemented` | `unsupported` |
| Apple TV | `pyatv` Media Remote Protocol | `implemented` | `implemented` | `implemented` | `implemented` | `not_implemented` | `unsupported` | `unsupported` | `implemented` | `unsupported` | `unsupported` | `unsupported` |

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

## Platform Gaps

Power and media controls are available to the direct remote when the selected
adapter advertises those commands. They remain outside the current gesture
command surface. Text input, source selection, and Wake-on-LAN are tracked as
`not_implemented` when an adapter extension could reasonably add them without
changing the gesture pipeline.

Power behavior varies by protocol:

- Android TV / Google TV and Samsung expose a power toggle key.
- Roku ECP exposes `PowerOff` for Roku TV devices; standalone Roku streaming
  players may not support TV power control.
- Apple TV exposes separate `turn_on` and `turn_off` through pyatv power
  management.
- LG webOS power-off and Wake-on-LAN need additional verified API and
  configuration work before being advertised.

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
