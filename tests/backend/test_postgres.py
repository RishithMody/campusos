"""Uses a dedicated, disposable database on an explicitly supplied local test cluster."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Negotiation


@pytest.mark.skipif(
    not os.environ.get("CAMPUSOS_TEST_POSTGRES_URL"),
    reason="Set CAMPUSOS_TEST_POSTGRES_URL to an isolated local PostgreSQL cluster",
)
def test_empty_postgres_migration_persistence_and_serialized_updates(monkeypatch):
    url = os.environ["CAMPUSOS_TEST_POSTGRES_URL"]
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "t2_test_" + uuid.uuid4().hex
    # Generated identifier contains lowercase hex only, never caller SQL.
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = admin.url.set(database=name)
    engine = create_engine(target)
    try:
        monkeypatch.setenv("CAMPUSOS_DATABASE_URL", target.render_as_string(hide_password=False))
        config = Config("backend/alembic.ini")
        command.upgrade(config, "head")
        assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
        sessions = sessionmaker(engine)
        with sessions.begin() as session:
            session.add(Negotiation(id="neg_fixture", data={"counter": 0}))

        def increment(_):
            with sessions.begin() as session:
                row = session.scalar(
                    select(Negotiation).where(Negotiation.id == "neg_fixture").with_for_update()
                )
                row.data = {"counter": row.data["counter"] + 1}

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(increment, range(12)))
        with sessions() as session:
            assert session.get(Negotiation, "neg_fixture").data["counter"] == 12
        engine.dispose()
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT data FROM negotiations")).scalar()["counter"] == 12
            )
        command.downgrade(config, "base")
        assert not set(Base.metadata.tables) & set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
        print(
            "PostgreSQL: empty upgrade, persistence, 12 concurrent locked updates, downgrade/re-upgrade passed"
        )
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()
