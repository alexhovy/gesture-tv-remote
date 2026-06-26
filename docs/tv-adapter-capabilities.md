# TV Adapter Capabilities

The app keeps common commands adapter-neutral, but each TV platform has
different protocol support. Capability metadata is exposed through the
application TV remote port and implemented by the concrete TV adapters.
Capability status is explicit:

- `implemented`: available through the current adapter code.
- `not_implemented`: the platform or library is expected to support this class
  of capability, but the app does not implement it yet.
- `unsupported`: not supported by the current protocol path or intentionally not
  available through this adapter.

| Adapter | Connection | Power | Volume | Navigation | Media Controls | Text Input | Source Selection | Wake-on-LAN | Pairing | Remote Mic Stream | Native Voice UI | App Voice Input |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Android TV / Google TV | `androidtvremote2` TLS remote protocol | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `unsupported` | `unsupported` | `implemented` | `implemented` | `implemented` | `not_implemented` |
| Samsung TV | `samsungtvws` websocket | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `implemented` | `unsupported` | `implemented` | `unsupported` |
| LG webOS | `aiowebostv` websocket | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `implemented` | `unsupported` | `unsupported` | `unsupported` |
| Roku | Roku ECP HTTP | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `unsupported` | `unsupported` | `unsupported` | `implemented` | `unsupported` |

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

The gesture layer emits these common commands through the dispatcher. Adapter
translations live in `src/infrastructure/tv/tv_command_translation.py`.

## Platform Gaps

Power, media controls, text input, source selection, and Wake-on-LAN are outside
the current gesture command surface. They are tracked as `not_implemented`
when an adapter extension could reasonably add them without changing the
gesture pipeline.

Voice input is split by protocol capability:

- remote mic stream: this app sends microphone PCM audio to the TV. Android TV
  supports this through Android TV Remote Protocol voice payloads.
- native voice UI: this app only asks the TV to open its own voice listener.
  Roku uses ECP `Search`; Samsung uses `KEY_VOICE`; neither path accepts this
  app's microphone audio through the current adapter.
- app voice input: foreground app-requested microphone sessions are tracked
  separately and are not implemented by the current adapters.
