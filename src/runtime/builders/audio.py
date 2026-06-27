from __future__ import annotations

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import TVRemotePort
from src.application.ports.voice_capture import VoiceCapturePort
from src.shared.config import AppConfig


def build_voice_capture(
    remote: TVRemotePort,
    config: AppConfig,
    logger: LoggerPort,
) -> VoiceCapturePort:
    from src.infrastructure.audio.voice_capture import MicrophoneVoiceCapture

    return MicrophoneVoiceCapture(remote, config, logger)
