from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.shared.config import (
    CONFIG_FIELDS,
    AppConfig,
    config_field_default,
    get_config_value,
    replace_config_value,
    validate_config,
)

_CONFIG_ROW_ID = 1


class ConfigRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def get_config(self) -> AppConfig | None:
        self._ensure_schema()
        with self._store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM app_config WHERE id = ?",
                (_CONFIG_ROW_ID,),
            ).fetchone()

        if row is None:
            return None

        config = AppConfig()
        for field in CONFIG_FIELDS:
            config = replace_config_value(
                config,
                field.name,
                _from_db_value(config_field_default(field), row[field.name]),
            )
        validate_config(config)
        return config

    def save_config(self, config: AppConfig) -> None:
        validate_config(config)
        self._ensure_schema()

        column_names = [field.name for field in CONFIG_FIELDS]
        quoted_columns = ", ".join(_quote_identifier(name) for name in column_names)
        placeholders = ", ".join("?" for _ in column_names)
        update_assignments = ", ".join(
            f"{_quote_identifier(name)} = excluded.{_quote_identifier(name)}"
            for name in column_names
        )
        values = [_to_db_value(get_config_value(config, name)) for name in column_names]

        with self._store.connect() as connection:
            connection.execute(
                f"""
                INSERT INTO app_config (
                    id,
                    {quoted_columns},
                    updated_at
                )
                VALUES (?, {placeholders}, ?)
                ON CONFLICT(id) DO UPDATE SET
                    {update_assignments},
                    updated_at = excluded.updated_at
                """,
                (
                    _CONFIG_ROW_ID,
                    *values,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def reset_config(self) -> None:
        self._ensure_schema()
        with self._store.connect() as connection:
            connection.execute(
                "DELETE FROM app_config WHERE id = ?",
                (_CONFIG_ROW_ID,),
            )

    def _ensure_schema(self) -> None:
        with self._store.connect() as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS app_config (
                    id INTEGER PRIMARY KEY CHECK (id = {_CONFIG_ROW_ID}),
                    {_column_definitions()},
                    updated_at TEXT NOT NULL
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(app_config)")
            }
            for field in CONFIG_FIELDS:
                if field.name in existing_columns:
                    continue
                connection.execute(
                    f"""
                    ALTER TABLE app_config
                    ADD COLUMN {_migration_column_definition(field.name, config_field_default(field))}
                    DEFAULT {_sql_literal(_to_db_value(config_field_default(field)))}
                    """
                )


def _column_definitions() -> str:
    return ",\n                    ".join(
        _column_definition(field.name, config_field_default(field))
        for field in CONFIG_FIELDS
    )


def _column_definition(name: str, default: Any) -> str:
    column_name = _quote_identifier(name)
    if isinstance(default, bool):
        return f"{column_name} INTEGER NOT NULL CHECK ({column_name} IN (0, 1))"
    if isinstance(default, int):
        return f"{column_name} INTEGER NOT NULL"
    if isinstance(default, float):
        return f"{column_name} REAL NOT NULL"
    if isinstance(default, Path | str):
        return f"{column_name} TEXT NOT NULL"

    raise TypeError(f"Unsupported AppConfig field type for {name}")


def _migration_column_definition(name: str, default: Any) -> str:
    column_name = _quote_identifier(name)
    if isinstance(default, bool | int):
        return f"{column_name} INTEGER"
    if isinstance(default, float):
        return f"{column_name} REAL"
    if isinstance(default, Path | str):
        return f"{column_name} TEXT"

    raise TypeError(f"Unsupported AppConfig field type for {name}")


def _quote_identifier(name: str) -> str:
    return f'"{name}"'


def _sql_literal(value: str | int | float) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)


def _to_db_value(value: Any) -> str | int | float:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Path):
        return str(value)
    return value


def _from_db_value(default: Any, value: Any) -> Any:
    if isinstance(default, bool):
        return bool(value)
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    if isinstance(default, Path):
        return Path(value)
    if isinstance(default, str):
        return str(value)

    raise TypeError(f"Unsupported AppConfig field default {default!r}")
