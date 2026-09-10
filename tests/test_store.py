from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel import Session, create_engine, select

from causal_coding.commercial_events import FinanceRecord
from causal_coding.events import PullRequest, ingest_event
from causal_coding.store import OWN_TABLES, create_schema, save_events
from causal_coding.survey_events import SurveyResponse

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    create_schema(engine)
    return engine


def test_create_schema_only_creates_our_own_tables(engine):
    from sqlalchemy import inspect

    table_names = set(inspect(engine).get_table_names())
    assert table_names == {t.name for t in OWN_TABLES}
    assert "pull_requests" not in table_names  # devlake's external mirror tablename, must never appear here
    assert "ingested_pull_requests" in table_names


def test_own_tables_cover_every_event_module():
    names = {t.name for t in OWN_TABLES}
    assert "ingested_pull_requests" in names
    assert "ingested_survey_responses" in names
    assert "ingested_finance_records" in names
    assert len(names) == len(OWN_TABLES)


def test_save_events_round_trips_across_modules(engine):
    pr = ingest_event(
        PullRequest,
        observed_at=NOW,
        source_system="devlake",
        pull_request_id="pr-1",
        repository_id="repo-1",
        team_id="team-checkout",
        opened_at=NOW,
        is_draft=False,
        additions=10,
        deletions=2,
        changed_files=["x.py"],
    )
    survey = ingest_event(
        SurveyResponse,
        observed_at=NOW,
        source_system="survey-tool",
        respondent_id="p1",
        team_id="team-checkout",
        instrument="dora_capability_scale",
        instrument_version="2025",
        items={"continuous_delivery": 4.2},
    )
    finance = ingest_event(
        FinanceRecord, observed_at=NOW, source_system="finance", period="2026-01", product_id="prod-1", recognised_revenue=1000.0
    )

    with Session(engine) as session:
        save_events(session, [pr, survey, finance])

    with Session(engine) as session:
        stored_pr = session.exec(select(PullRequest)).one()
        assert stored_pr.pull_request_id == "pr-1"
        assert stored_pr.changed_files == ["x.py"]

        stored_survey = session.exec(select(SurveyResponse)).one()
        assert stored_survey.items == {"continuous_delivery": 4.2}

        stored_finance = session.exec(select(FinanceRecord)).one()
        assert stored_finance.recognised_revenue == 1000.0
