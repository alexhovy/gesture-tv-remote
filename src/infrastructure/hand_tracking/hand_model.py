import urllib.request
from pathlib import Path

from src.shared.config import AppConfig
from src.shared.logging import AppLogger


def download_model_if_missing(config: AppConfig) -> None:
    if config.model.file.exists():
        return

    config.model.file.parent.mkdir(parents=True, exist_ok=True)
    logger = AppLogger()
    logger.info(f"Downloading {config.model.file}...")
    _download_with_retries(config, logger)


def _download_with_retries(config: AppConfig, logger: AppLogger) -> None:
    attempts = config.model.download_retries + 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            _download_to_temp_file(config.model.url, config.model.file, config)
            return
        except Exception as error:
            last_error = error
            _temp_path(config.model.file).unlink(missing_ok=True)
            if attempt < attempts:
                logger.info(
                    f"Model download failed ({error}); "
                    f"retrying {attempt}/{attempts - 1}."
                )

    raise RuntimeError(f"Could not download model: {last_error}") from last_error


def _download_to_temp_file(url: str, destination: Path, config: AppConfig) -> None:
    temp_path = _temp_path(destination)
    with urllib.request.urlopen(
        url,
        timeout=config.model.download_timeout_seconds,
    ) as response:
        with temp_path.open("wb") as model_file:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                model_file.write(chunk)
    temp_path.replace(destination)


def _temp_path(destination: Path) -> Path:
    return destination.with_name(f"{destination.name}.tmp")
