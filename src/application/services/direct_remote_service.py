from dataclasses import dataclass

from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.tv_remote import TVRemotePort
from src.domain.constants import (
    TV_COMMAND_BACK,
    TV_COMMAND_DPAD_CENTER,
    TV_COMMAND_DPAD_DOWN,
    TV_COMMAND_DPAD_LEFT,
    TV_COMMAND_DPAD_RIGHT,
    TV_COMMAND_DPAD_UP,
    TV_COMMAND_HOME,
    TV_COMMAND_VOLUME_DOWN,
    TV_COMMAND_VOLUME_UP,
)

REMOTE_COMMANDS = (
    TV_COMMAND_HOME,
    TV_COMMAND_BACK,
    TV_COMMAND_DPAD_UP,
    TV_COMMAND_DPAD_DOWN,
    TV_COMMAND_DPAD_LEFT,
    TV_COMMAND_DPAD_RIGHT,
    TV_COMMAND_DPAD_CENTER,
    TV_COMMAND_VOLUME_UP,
    TV_COMMAND_VOLUME_DOWN,
)


@dataclass(frozen=True)
class DirectRemoteCommandResult:
    accepted: bool
    command: str
    reason: str | None = None


class DirectRemoteService:
    def __init__(
        self,
        remote: TVRemotePort,
        command_dispatcher: CommandDispatcherPort,
    ) -> None:
        self._remote = remote
        self._command_dispatcher = command_dispatcher

    def supported_commands(self) -> tuple[str, ...]:
        supported = self._remote.capabilities().supported_commands
        return tuple(command for command in REMOTE_COMMANDS if command in supported)

    def dispatch(self, command: str) -> DirectRemoteCommandResult:
        normalized = command.strip().upper()
        if normalized not in REMOTE_COMMANDS:
            return DirectRemoteCommandResult(
                accepted=False,
                command=normalized,
                reason="unknown_command",
            )
        if normalized not in self._remote.capabilities().supported_commands:
            return DirectRemoteCommandResult(
                accepted=False,
                command=normalized,
                reason="unsupported_command",
            )

        self._command_dispatcher.enqueue(f"remote:{normalized}", normalized)
        return DirectRemoteCommandResult(accepted=True, command=normalized)
