from typing import Protocol


class MacAddressResolverPort(Protocol):
    def resolve(self, host: str) -> str | None: ...

    def resolve_broadcast_address(self, host: str) -> str | None: ...
