# My Python App

## Setup

Install Python 3.12 or newer and `uv`.

```bash
uv sync --dev
```

Create a local environment file:

```bash
cp .env.example .env
```

## Running Tests

```bash
uv run pytest
```

## Running the Application

```bash
uv run my-python-app
```

Alternatively:

```bash
uv run python -m app.main
```
