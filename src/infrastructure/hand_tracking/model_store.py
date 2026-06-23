from src.infrastructure.hand_tracking.hand_model import download_model_if_missing
from src.shared.config import AppConfig


class MediaPipeModelStore:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def ensure_model(self) -> None:
        download_model_if_missing(self._config)
