from src.shared.config import AppConfig


class FakeConfigProvider:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.calls = 0

    def __call__(self) -> AppConfig:
        self.calls += 1
        return self.config


class FakeConfigStore:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config
        self.saved: list[AppConfig] = []
        self.reset_called = False

    def get_config(self) -> AppConfig | None:
        return self.config

    def save_config(self, config: AppConfig) -> None:
        self.config = config
        self.saved.append(config)

    def reset_config(self) -> None:
        self.config = None
        self.reset_called = True
