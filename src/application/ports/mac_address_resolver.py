from typing import Protocol


class MacAddressResolverPort(Protocol):
    def resolve(self, host: str) -> str | None: ...
