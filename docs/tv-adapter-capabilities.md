# TV Adapter Capabilities

The app keeps common commands adapter-neutral, but each TV platform has
different protocol support. Capability status is explicit:

- `implemented`: available through the current adapter code.
- `not_implemented`: the platform or library is expected to support this class
  of capability, but the app does not implement it yet.
- `unsupported`: not supported by the current protocol path or intentionally not
  available through this adapter.

| Adapter | Connection | Power | Volume | Navigation | Media Controls | Text Input | Source Selection | Wake-on-LAN | Pairing | Voice Capture |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Android TV / Google TV | `androidtvremote2` TLS remote protocol | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `unsupported` | `unsupported` | `implemented` | `implemented` |
| Samsung TV | `samsungtvws` websocket | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `implemented` | `unsupported` |
| LG webOS | `aiowebostv` websocket | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `implemented` | `unsupported` |
| Roku | Roku ECP HTTP | `not_implemented` | `implemented` | `implemented` | `not_implemented` | `not_implemented` | `not_implemented` | `unsupported` | `unsupported` | `unsupported` |

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
the current gesture MVP command surface. They are tracked as `not_implemented`
when a future adapter extension could reasonably add them without changing the
gesture pipeline.

Voice capture is not part of the key-command table. The `MIC` gesture asks the
active adapter for a voice stream; currently only Android TV returns one.
