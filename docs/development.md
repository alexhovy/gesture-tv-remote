# Development

## Setup

Install `uv` first if it is not already available.

```powershell
python -m pip install uv
```

Restart the terminal after installation so PowerShell can pick up the updated
`PATH`.

```bash
uv sync
```

If PowerShell still cannot find `uv` after installing it with Python, run it as
a Python module:

```powershell
python -m uv sync
```

## Run

```bash
uv run python main.py
```

Press `q` to quit the webcam window.

## Config UI

```bash
uv run python config_server.py
```

Open `http://localhost`. When mDNS is available on the local network, the
UI is also advertised as `http://gesturetvremote.local`. Saved settings are
written to the local config database. Gesture, timing, voice-duration, and zoom
tuning changes are reloaded by the running gesture process; integration and
hardware settings still require restarting it.

## Test

```bash
uv run python -m unittest discover -s tests
```

The current tests focus on pure domain behavior and adapter selection or command
translation. Hardware-dependent TV behavior should be covered through adapters
or integration tests when test doubles are available.

## Gesture Log Analysis

Gesture debug logs can be summarized with:

```bash
uv run python scripts/analyze_gesture_log.py logs/logs.txt
```

The analyzer reports command counts, candidate classifications, blocked reasons,
neutral-zone frames, and near-threshold misses. Use it when tuning pointer or
volume motion behavior so threshold changes are based on measured log patterns.
