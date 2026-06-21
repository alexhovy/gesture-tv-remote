import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SqliteStore:
    def __init__(self, db_file: Path) -> None:
        self._db_file = db_file

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_file)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
