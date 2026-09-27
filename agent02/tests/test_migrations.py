from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect, text

from app.database import Base, Database
from scripts.migrate import WEEK1_REVISION, build_alembic_config, upgrade_database


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_empty_database_upgrades_to_head(tmp_path):
    url = sqlite_url(tmp_path / "empty.db")

    upgrade_database(url)

    tables = set(inspect(Database(url).engine).get_table_names())
    assert set(Base.metadata.tables).issubset(tables)
    assert "alembic_version" in tables


def test_new_database_can_downgrade_and_upgrade(tmp_path):
    url = sqlite_url(tmp_path / "roundtrip.db")
    config = build_alembic_config(url)
    upgrade_database(url)

    command.downgrade(config, "base")
    assert set(inspect(Database(url).engine).get_table_names()) == {"alembic_version"}

    command.upgrade(config, "head")
    tables = set(inspect(Database(url).engine).get_table_names())
    assert set(Base.metadata.tables).issubset(tables)


def test_existing_week1_database_is_adopted_without_data_loss(tmp_path):
    url = sqlite_url(tmp_path / "week1.db")
    database = Database(url)
    config = build_alembic_config(url)
    command.upgrade(config, WEEK1_REVISION)
    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(
            text(
                "INSERT INTO evaluation_runs "
                "(dataset_name, configuration_json, metrics_json, created_at) "
                "VALUES ('baseline', '{}', '{}', CURRENT_TIMESTAMP)"
            )
        )

    upgrade_database(url)

    with database.engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM evaluation_runs")
        ).scalar_one()
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert count == 1
    assert revision


def test_current_unversioned_schema_is_stamped_without_reapplying(tmp_path):
    url = sqlite_url(tmp_path / "current.db")
    database = Database(url)
    database.create_all()

    upgrade_database(url)

    with database.engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision


def test_partial_unversioned_database_is_rejected(tmp_path):
    url = sqlite_url(tmp_path / "partial.db")
    database = Database(url)
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError, match="missing tables"):
        upgrade_database(url)
