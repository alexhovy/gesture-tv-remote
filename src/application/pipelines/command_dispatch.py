import asyncio

from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.logger import LoggerPort
from src.application.ports.voice_capture import VoiceCapturePort
from src.application.services.pipeline_metrics import PipelineMetrics
from src.domain.commands import GESTURE_TO_COMMAND
from src.domain.constants import GESTURE_MIC
from src.domain.session import GestureSession


class CommandDispatchPipeline:
    def __init__(
        self,
        gesture_session: GestureSession,
        voice_capture: VoiceCapturePort,
        command_dispatcher: CommandDispatcherPort,
        metrics: PipelineMetrics | None,
        logger: LoggerPort,
    ) -> None:
        self._gesture_session = gesture_session
        self._voice_capture = voice_capture
        self._command_dispatcher = command_dispatcher
        self._metrics = metrics
        self._logger = logger

    async def handle_decision(
        self,
        command_gesture: str | None,
        activated: bool,
        now: float,
        voice_task: asyncio.Task | None,
    ) -> asyncio.Task | None:
        if not activated:
            self._gesture_session.record_idle()
            return voice_task
        if command_gesture is None:
            return voice_task

        command = GESTURE_TO_COMMAND.get(command_gesture)
        if not self._gesture_session.should_emit(command_gesture, command, now):
            return voice_task

        if command_gesture == GESTURE_MIC:
            voice_task = self._ensure_voice_task(voice_task)
        elif command:
            self._logger.debug(
                f"sending command_gesture={command_gesture} command={command}"
            )
            self._command_dispatcher.enqueue(command_gesture, command)
            self.record_dispatch_metrics()

        self._gesture_session.record_emit(command_gesture, now)
        return voice_task

    def record_dispatch_metrics(self) -> None:
        if self._metrics is None:
            return
        self._metrics.record_dispatch(
            self._command_dispatcher.queue_depth,
            self._command_dispatcher.last_send_latency_seconds,
            self._command_dispatcher.dropped_commands,
        )

    def _ensure_voice_task(
        self, voice_task: asyncio.Task | None
    ) -> asyncio.Task | None:
        if voice_task is None or voice_task.done():
            self._logger.debug("starting microphone capture")
            return asyncio.create_task(self._voice_capture.capture())

        self._logger.debug("microphone capture already running")
        return voice_task
