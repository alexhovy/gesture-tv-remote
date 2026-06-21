from pathlib import Path


DEFAULT_LOG_FILE = Path("logs/logs.txt")


def configure_app_logging(
    log_file: Path = DEFAULT_LOG_FILE,
    *,
    reset: bool = True,
    console: bool = False,
) -> None:
    AppLogger.configure(log_file, reset=reset, console=console)


class AppLogger:
    _log_file: Path | None = None
    _console = True

    @classmethod
    def configure(
        cls,
        log_file: Path,
        *,
        reset: bool = True,
        console: bool = False,
    ) -> None:
        cls._log_file = log_file
        cls._console = console
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if reset:
            log_file.write_text("", encoding="utf-8")

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def debug(self, message: str) -> None:
        self._write("DEBUG", message)

    def _write(self, level: str, message: str) -> None:
        line = f"[{level}] {message}"
        if self._log_file is not None:
            with self._log_file.open("a", encoding="utf-8") as log:
                log.write(f"{line}\n")
        if self._console or self._log_file is None:
            print(line)
