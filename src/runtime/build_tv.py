from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import TVRemotePort
from src.application.services.pipeline_metrics import PipelineMetrics
from src.application.services.remote_command_dispatcher import RemoteCommandDispatcher
from src.shared.config import AppConfig


@dataclass(frozen=True)
class TvRuntimeDependencies:
    remote: TVRemotePort
    command_dispatcher: RemoteCommandDispatcher
    metrics: PipelineMetrics


def build_tv_dependencies(
    config: AppConfig,
    logger: LoggerPort,
) -> TvRuntimeDependencies:
    from src.infrastructure.tv.tv_remote_factory import create_tv_remote_client

    remote = create_tv_remote_client(config)
    return TvRuntimeDependencies(
        remote=remote,
        command_dispatcher=RemoteCommandDispatcher(remote, logger),
        metrics=PipelineMetrics(config.tv.adapter),
    )
