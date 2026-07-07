from collections.abc import Callable
from dataclasses import dataclass

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import (
    CapabilityStatus,
    TextInputCapabilities,
    TextInputMode,
    TextInputStatus,
    TVRemotePort,
)
from src.domain.constants import (
    TV_COMMAND_BACK,
    TV_COMMAND_HOME,
    TV_COMMAND_POWER_OFF,
    TV_COMMAND_POWER_ON,
    TV_COMMAND_POWER_TOGGLE,
)


@dataclass(frozen=True)
class TextInputActionResult:
    accepted: bool
    reason: str | None = None


class TextInputService:
    _DISMISS_COMMANDS = frozenset(
        {
            TV_COMMAND_BACK,
            TV_COMMAND_HOME,
            TV_COMMAND_POWER_OFF,
            TV_COMMAND_POWER_ON,
            TV_COMMAND_POWER_TOGGLE,
        }
    )

    def __init__(self, remote: TVRemotePort, logger: LoggerPort | None = None) -> None:
        self._remote = remote
        self._logger = logger
        self._subscribers: list[Callable[[TextInputStatus], None]] = []
        self._status = remote.text_input_status()
        self._dismissed_remote_status: TextInputStatus | None = None
        self._synced_text = self._status.value
        self._remote.set_text_input_handler(self._handle_status)

    def capabilities(self) -> TextInputCapabilities:
        return self._remote.capabilities().text_input

    def status(self) -> TextInputStatus:
        remote_status = self._remote.text_input_status()
        if (
            self._dismissed_remote_status is not None
            and remote_status == self._dismissed_remote_status
        ):
            return self._status
        self._dismissed_remote_status = None
        self._status = remote_status
        return self._status

    def subscribe(
        self,
        subscriber: Callable[[TextInputStatus], None],
    ) -> Callable[[], None]:
        self._subscribers.append(subscriber)
        subscriber(self.status())

        def unsubscribe() -> None:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

        return unsubscribe

    async def send(self, text: str) -> TextInputActionResult:
        if not text:
            return TextInputActionResult(accepted=False, reason="empty_text")
        if not self._is_implemented(self.capabilities().send_text):
            return TextInputActionResult(accepted=False, reason="unsupported")
        self._log(f"TV text input send length={len(text)}")
        await self._remote.send_text(text)
        self._synced_text += text
        return TextInputActionResult(accepted=True)

    async def replace(self, text: str) -> TextInputActionResult:
        if not self._is_implemented(self.capabilities().replace_text):
            return TextInputActionResult(accepted=False, reason="unsupported")
        self._log(f"TV text input replace length={len(text)}")
        await self._remote.replace_text(text)
        self._synced_text = text
        return TextInputActionResult(accepted=True)

    async def delete(self, count: int = 1) -> TextInputActionResult:
        if count < 1:
            return TextInputActionResult(accepted=False, reason="invalid_count")
        if not self._is_implemented(self.capabilities().delete_text):
            return TextInputActionResult(accepted=False, reason="unsupported")
        self._log(f"TV text input delete count={count}")
        await self._remote.delete_text(count)
        self._synced_text = self._synced_text[:-count]
        return TextInputActionResult(accepted=True)

    async def sync(self, text: str) -> TextInputActionResult:
        capabilities = self.capabilities()
        if self._is_implemented(capabilities.replace_text):
            self._log(f"TV text input sync replace length={len(text)}")
            await self._remote.replace_text(text)
            self._synced_text = text
            return TextInputActionResult(accepted=True)

        delete_count = len(self._synced_text)
        if delete_count and not self._is_implemented(capabilities.delete_text):
            return TextInputActionResult(accepted=False, reason="unsupported")
        if text and not self._is_implemented(capabilities.send_text):
            return TextInputActionResult(accepted=False, reason="unsupported")

        self._log(
            "TV text input sync replay "
            f"delete_count={delete_count} length={len(text)}"
        )
        if delete_count:
            await self._remote.delete_text(delete_count)
        if text:
            await self._remote.send_text(text)
        self._synced_text = text
        return TextInputActionResult(accepted=True)

    async def submit(self) -> TextInputActionResult:
        if not self._is_implemented(self.capabilities().submit_text):
            return TextInputActionResult(accepted=False, reason="unsupported")
        self._log("TV text input submit")
        await self._remote.submit_text()
        self._synced_text = ""
        self.dismiss("submit")
        return TextInputActionResult(accepted=True)

    def dismiss_for_command(self, command: str) -> None:
        if command.strip().upper() in self._DISMISS_COMMANDS:
            self.dismiss(f"command:{command.strip().upper()}")

    def dismiss(self, reason: str) -> None:
        if not self._status.active and not self._synced_text:
            return
        self._log(f"TV text input dismissed reason={reason}")
        self._dismissed_remote_status = self._status
        self._synced_text = ""
        self._handle_status(
            TextInputStatus(
                active=False,
                mode=self._status.mode,
                value="",
                label=self._status.label,
                app_id=self._status.app_id,
            )
        )

    def _handle_status(self, status: TextInputStatus) -> None:
        if status.active:
            self._dismissed_remote_status = None
            if status.value:
                self._synced_text = status.value
        else:
            self._synced_text = ""
        self._status = status
        self._log(
            "TV text input status "
            f"active={status.active} mode={status.mode.value} "
            f"label={status.label or 'unknown'} app={status.app_id or 'unknown'}"
        )
        for subscriber in tuple(self._subscribers):
            subscriber(status)

    def _log(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(message)

    @staticmethod
    def _is_implemented(status: CapabilityStatus) -> bool:
        return status == CapabilityStatus.IMPLEMENTED


def manual_text_status() -> TextInputStatus:
    return TextInputStatus(active=False, mode=TextInputMode.MANUAL)
