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

## Test

```bash
uv run python -m unittest discover -s tests
```

The current tests focus on pure domain behavior and adapter selection or command
translation. Hardware-dependent TV behavior should be covered through adapters
or integration tests when test doubles are available.
