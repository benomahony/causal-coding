import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, Table, create_engine, text
from sqlmodel import Session, select

from causal_coding.commercial_events import FinanceRecord
from causal_coding.events import CIRun, PullRequest, ingest_event
from causal_coding.store import save_events
from causal_coding.store.coverage import variable_summaries
from causal_coding.store.schema import upgrade_schema

DATABASE_URL = os.environ.get("CAUSAL_TEST_DB_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Set CAUSAL_TEST_DB_URL for PostgreSQL integration tests")


@pytest.fixture
def database():
    schema = "causal_test_" + uuid4().hex
    admin = create_engine(DATABASE_URL)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(DATABASE_URL, connect_args={"options": "-csearch_path=" + schema})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_postgres_legacy_upgrade_and_live_coverage(database):
    metadata = MetaData()
    for model in (PullRequest, CIRun):
        columns = [
            Column(column.name, column.type, primary_key=column.primary_key,
                   nullable=False if column.name in {"additions", "deletions", "is_draft", "required"} else column.nullable)
            for column in model.__table__.columns if column.name not in {"commit_shas", "merge_commit_sha"}
        ]
        Table(model.__tablename__, metadata, *columns)
    metadata.create_all(database)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with database.begin() as connection:
        connection.execute(metadata.tables[PullRequest.__tablename__].insert().values(
            observed_at=now, source_system="devlake", pull_request_id="pr", repository_id="repo",
            team_id="team", opened_at=now, is_draft=False, additions=100, deletions=50,
        ))
        connection.execute(metadata.tables[CIRun.__tablename__].insert().values(
            observed_at=now, source_system="devlake", ci_run_id="ci", commit_sha="sha",
            check_category="test", triggered_at=now, required=True,
        ))
    upgrade_schema(database)
    upgrade_schema(database)
    with Session(database) as session:
        pull_request = session.exec(select(PullRequest)).one()
        assert pull_request.pull_request_id == "pr"
        assert pull_request.additions is None
        assert pull_request.is_draft is None
        assert session.exec(select(CIRun)).one().required is None
        save_events(session, [ingest_event(
            FinanceRecord, observed_at=now, source_system="real", period="2026-01",
            product_id="product", recognised_revenue=100,
        )])
    summaries = variable_summaries(database)
    assert summaries["revenue"].inputs_available
    assert not summaries["gross_margin"].inputs_available
    assert not summaries["cost_to_serve"].inputs_available
