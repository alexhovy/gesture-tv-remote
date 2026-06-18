class AppLogger:
    def info(self, message: str) -> None:
        print(message)

    def error(self, message: str) -> None:
        print(message)

    def debug(self, message: str) -> None:
        print(f"[DEBUG] {message}")
