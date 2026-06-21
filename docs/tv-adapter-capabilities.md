# TV Adapter Capabilities

The app keeps common commands adapter-neutral, but each TV platform has
different protocol support. Capabilities are exposed by each adapter in code and
summarized here.

| Adapter | Connection | Power | Volume | Navigation | Media Controls | Text Input | Source Selection | Wake-on-LAN | Pairing | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Android TV / Google TV | `androidtvremote2` TLS remote protocol | No | Yes | Yes | No | No | No | No | Yes | Key commands and voice capture are implemented. |
| Samsung TV | `samsungtvws` websocket | No | Yes | Yes | No | No | No | No | Yes | Key commands are implemented; accepts TV pairing prompt/token flow. |
| LG webOS | `aiowebostv` websocket | No | Yes | Yes | No | No | No | No | Yes | Input-control navigation and media volume methods are implemented. |
| Roku | Roku ECP HTTP | No | Yes | Yes | No | No | No | No | No | ECP keypress commands are implemented. |

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

Unsupported capabilities are explicit so future work can add them per adapter
without forcing every platform to pretend it supports the same feature set.

Voice capture is not part of the key-command table. The `MIC` gesture asks the
active adapter for a voice stream; currently only Android TV returns one.
