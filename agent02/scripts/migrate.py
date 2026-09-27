from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.config import get_settings
from app.database import Base, Database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEK1_REVISION = "b0097d8017cf"
WEEK1_COLUMNS: dict[str, set[str]] = {
    "tasks": {
        "id",
        "request_id",
        "user_id",
        "session_id",
        "knowledge_base_id",
        "message",
        "status",
        "answer",
        "error_json",
        "state_json",
        "current_step",
        "max_steps",
        "input_tokens",
        "output_tokens",
        "created_at",
        "updated_at",
    },
    "task_steps": {
        "id",
        "task_id",
        "step_number",
        "node",
        "status",
        "detail_json",
        "created_at",
    },
    "tool_calls": {
        "id",
        "task_id",
        "tool_name",
        "arguments_json",
        "result_json",
        "success",
        "retry_count",
        "latency_ms",
        "created_at",
    },
    "checkpoints": {
        "id",
        "task_id",
        "state_version",
        "current_step",
        "next_node",
        "state_json",
        "created_at",
    },
    "memories": {
        "id",
        "user_id",
        "session_id",
        "kind",
        "key",
        "value_json",
        "created_at",
        "updated_at",
    },
    "evaluation_runs": {
        "id",
        "dataset_name",
        "configuration_json",
        "metrics_json",
        "created_at",
    },
}


def build_alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url"] = database_url
    return config


def _schema_differences(
    database: Database, expected: dict[str, set[str]]
) -> tuple[set[str], dict[str, list[str]]]:
    inspector = inspect(database.engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = set(expected) - existing_tables
    missing_columns: dict[str, list[str]] = {}
    for table_name, expected_columns in expected.items():
        if table_name in missing_tables:
            continue
        actual_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        missing = sorted(expected_columns - actual_columns)
        if missing:
            missing_columns[table_name] = missing
    return missing_tables, missing_columns


def _current_columns() -> dict[str, set[str]]:
    return {
        table_name: {column.name for column in table.columns}
        for table_name, table in Base.metadata.tables.items()
    }


def _raise_schema_difference(
    missing_tables: set[str], missing_columns: dict[str, list[str]]
) -> None:
    parts = []
    if missing_tables:
        parts.append("missing tables: " + ", ".join(sorted(missing_tables)))
    if missing_columns:
        details = "; ".join(
            f"{table}: {', '.join(columns)}"
            for table, columns in sorted(missing_columns.items())
        )
        parts.append("missing columns: " + details)
    raise RuntimeError("Existing database cannot be adopted; " + "; ".join(parts))


def upgrade_database(database_url: str) -> None:
    database = Database(database_url)
    config = build_alembic_config(database_url)
    inspector = inspect(database.engine)
    existing_tables = set(inspector.get_table_names())

    if "alembic_version" in existing_tables or not existing_tables:
        command.upgrade(config, "head")
        return

    current_missing = _schema_differences(database, _current_columns())
    if not any(current_missing):
        command.stamp(config, "head")
        return

    week1_missing = _schema_differences(database, WEEK1_COLUMNS)
    if not any(week1_missing):
        command.stamp(config, WEEK1_REVISION)
        command.upgrade(config, "head")
        return

    _raise_schema_difference(*week1_missing)


def main() -> None:
    settings = get_settings()
    upgrade_database(settings.database_url)
    print("Database migration is at head")


if __name__ == "__main__":
    main()
