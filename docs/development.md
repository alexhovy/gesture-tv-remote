# Development

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run

```bash
python main.py
```

Press `q` to quit the webcam window.

## Test

```bash
python -m unittest discover -s tests
```

The current tests focus on pure domain behavior. Hardware-dependent behavior
should be covered through adapters or integration tests when test doubles are
available.

