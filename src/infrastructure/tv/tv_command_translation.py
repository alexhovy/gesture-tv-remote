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
from src.infrastructure.tv.tv_remote import (
    TV_ADAPTER_ANDROIDTV,
    TV_ADAPTER_ROKU,
    TV_ADAPTER_SAMSUNG,
    TV_ADAPTER_WEBOS,
    TvRemoteCommandError,
)


ANDROIDTV_COMMANDS = {
    TV_COMMAND_HOME: "HOME",
    TV_COMMAND_BACK: "BACK",
    TV_COMMAND_DPAD_CENTER: "DPAD_CENTER",
    TV_COMMAND_DPAD_LEFT: "DPAD_LEFT",
    TV_COMMAND_DPAD_RIGHT: "DPAD_RIGHT",
    TV_COMMAND_DPAD_UP: "DPAD_UP",
    TV_COMMAND_DPAD_DOWN: "DPAD_DOWN",
    TV_COMMAND_VOLUME_UP: "VOLUME_UP",
    TV_COMMAND_VOLUME_DOWN: "VOLUME_DOWN",
}

SAMSUNG_COMMANDS = {
    TV_COMMAND_HOME: "KEY_HOME",
    TV_COMMAND_BACK: "KEY_RETURN",
    TV_COMMAND_DPAD_CENTER: "KEY_ENTER",
    TV_COMMAND_DPAD_LEFT: "KEY_LEFT",
    TV_COMMAND_DPAD_RIGHT: "KEY_RIGHT",
    TV_COMMAND_DPAD_UP: "KEY_UP",
    TV_COMMAND_DPAD_DOWN: "KEY_DOWN",
    TV_COMMAND_VOLUME_UP: "KEY_VOLUP",
    TV_COMMAND_VOLUME_DOWN: "KEY_VOLDOWN",
}

WEBOS_COMMANDS = {
    TV_COMMAND_HOME: "home",
    TV_COMMAND_BACK: "back",
    TV_COMMAND_DPAD_CENTER: "enter",
    TV_COMMAND_DPAD_LEFT: "left",
    TV_COMMAND_DPAD_RIGHT: "right",
    TV_COMMAND_DPAD_UP: "up",
    TV_COMMAND_DPAD_DOWN: "down",
    TV_COMMAND_VOLUME_UP: "volume_up",
    TV_COMMAND_VOLUME_DOWN: "volume_down",
}

ROKU_COMMANDS = {
    TV_COMMAND_HOME: "Home",
    TV_COMMAND_BACK: "Back",
    TV_COMMAND_DPAD_CENTER: "Select",
    TV_COMMAND_DPAD_LEFT: "Left",
    TV_COMMAND_DPAD_RIGHT: "Right",
    TV_COMMAND_DPAD_UP: "Up",
    TV_COMMAND_DPAD_DOWN: "Down",
    TV_COMMAND_VOLUME_UP: "VolumeUp",
    TV_COMMAND_VOLUME_DOWN: "VolumeDown",
}

_COMMANDS_BY_ADAPTER = {
    TV_ADAPTER_ANDROIDTV: ANDROIDTV_COMMANDS,
    TV_ADAPTER_SAMSUNG: SAMSUNG_COMMANDS,
    TV_ADAPTER_WEBOS: WEBOS_COMMANDS,
    TV_ADAPTER_ROKU: ROKU_COMMANDS,
}


def translate_tv_command(adapter: str, command: str) -> str:
    normalized_adapter = adapter.lower()
    try:
        commands = _COMMANDS_BY_ADAPTER[normalized_adapter]
    except KeyError as error:
        raise TvRemoteCommandError(f"Unsupported TV adapter: {adapter}") from error

    try:
        return commands[command]
    except KeyError as error:
        raise TvRemoteCommandError(
            f"Adapter {adapter} does not support command: {command}"
        ) from error
