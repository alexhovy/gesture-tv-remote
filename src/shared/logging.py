class AppLogger:
    def info(self, message: str) -> None:
        print(f"[INFO] {message}")

    def error(self, message: str) -> None:
        print(f"[ERROR] {message}")

    def debug(self, message: str) -> None:
        print(f"[DEBUG] {message}")
