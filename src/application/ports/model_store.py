from typing import Protocol


class ModelStorePort(Protocol):
    def ensure_model(self) -> None: ...
