import urllib.request

from src.shared.config import AppConfig


def download_model_if_missing(config: AppConfig) -> None:
    if config.model_file.exists():
        return

    config.model_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {config.model_file}...")
    urllib.request.urlretrieve(config.model_url, config.model_file)
