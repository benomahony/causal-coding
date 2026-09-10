from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, Table, inspect, select, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from causal_coding import web
from causal_coding.commercial_events import FinanceRecord
from causal_coding.devlake.config import DevLakeConfig
from causal_coding.devlake.ingest import (
    fetch_ci_runs,
    fetch_deployments,
    fetch_incidents,
    fetch_pull_requests,
)
from causal_coding.devlake.tables import (
    DevLakeCicdDeployment,
    DevLakeCicdTask,
    DevLakeIncident,
    DevLakePullRequest,
)
from causal_coding.events import (
    AgentBenchmarkResult,
    AgentSession,
    CIRun,
    Deployment,
    PullRequest,
    RepositorySnapshot,
    ingest_event,
)
from causal_coding.store import OWN_TABLES, create_schema, save_events
from causal_coding.store.config import StoreConfig
from causal_coding.store.coverage import (
    sources_with_data,
    variable_data_summary,
    variable_summaries,
)
from causal_coding.store.joins import deployed_changes
from causal_coding.store.schema import upgrade_schema
from causal_coding.visualize import render

NOW = datetime(2026, 1, 4, tzinfo=UTC)


@pytest.fixture
def engine():
    database = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    create_schema(database)
    yield database
    database.dispose()


def save(engine, event_type, **values):
    with Session(engine) as session:
        save_events(session, [ingest_event(event_type, observed_at=NOW, source_system="real", **values)])


def test_one_revenue_row_does_not_unlock_costs_margin_or_latent_targets(engine):
    save(engine, FinanceRecord, period="2026-01", product_id="product-1", recognised_revenue=100)
    summaries = variable_summaries(engine)
    assert summaries["revenue"].inputs_available
    for variable in ("engineering_cost", "cost_to_serve", "gross_margin", "commercial_success"):
        assert not summaries[variable].inputs_available
    assert summaries["cost_to_serve"].row_count == 0
    assert summaries["commercial_success"].status == "latent"


def test_incomplete_and_proxy_inputs_do_not_make_constructs_observed(engine):
    save(engine, AgentSession, session_id="session", team_id="team")
    assert not variable_data_summary(engine, "realised_agent_autonomy").inputs_available
    save(engine, AgentBenchmarkResult, benchmark_task_id="task", model="model", tools=[], success=True)
    assert variable_data_summary(engine, "agent_capability").status == "proxy"
    assert not variable_data_summary(engine, "agent_task_success").inputs_available


def test_zero_denominator_does_not_unlock_coverage(engine):
    save(engine, RepositorySnapshot, repository_id="repo", files_in_scope=0, typed_files=0, required_checks=["mypy"])
    assert not variable_data_summary(engine, "type_constraint_coverage").inputs_available


def test_fixture_records_are_not_live_coverage(engine):
    with Session(engine) as session:
        save_events(session, [ingest_event(FinanceRecord, observed_at=NOW, source_system="fixtures", period="2026-01", product_id="p", recognised_revenue=100)])
    assert not sources_with_data(engine)
    assert not variable_data_summary(engine, "revenue").inputs_available


@pytest.mark.parametrize("config_class", [StoreConfig, DevLakeConfig])
def test_database_credentials_are_not_reparsed_as_url_components(config_class):
    configuration = config_class(host="db.example.test", user="user@name", password="test@:/?#%secret", database="database")
    assert configuration.sqlalchemy_url.host == configuration.host
    assert configuration.sqlalchemy_url.username == configuration.user
    assert configuration.sqlalchemy_url.password == configuration.password
    assert configuration.password not in str(configuration.sqlalchemy_url)


def test_empty_source_selection_stays_empty_with_real_data(engine, monkeypatch):
    save(engine, FinanceRecord, period="2026-01", product_id="product", recognised_revenue=100)
    monkeypatch.setattr(web, "_store_engine", engine)
    response = TestClient(web.app).get("/graph?keep_panel=true&sources=")
    assert response.status_code == 200
    assert 'data-sources="none"' in response.text
    assert 'value="finance" checked' not in response.text
    assert "sources=none" in response.headers["HX-Push-Url"]
    live = TestClient(web.app).get("/graph?keep_panel=true&sources=connected")
    assert 'value="finance" checked' in live.text


@pytest.mark.parametrize("route", ["/", "/graph", "/sources", "/focus/revenue", "/edge/B16"])
def test_missing_schema_degrades_to_readable_pages(route, monkeypatch):
    empty = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(web, "_store_engine", empty)
    response = TestClient(web.app).get(route)
    assert response.status_code == 200
    assert "Data store unavailable" in response.text or "Input presence does not establish estimability" in response.text


def test_connection_failure_does_not_break_hypothetical_preview(monkeypatch):
    from sqlalchemy.exc import OperationalError

    class Unavailable:
        def connect(self):
            raise OperationalError("", {}, Exception("offline"))

    monkeypatch.setattr(web, "_store_engine", Unavailable())
    monkeypatch.setattr(web, "inspect", lambda engine: engine.connect())
    response = TestClient(web.app).get("/graph?keep_panel=true&sources=finance")
    assert response.status_code == 200
    assert "Data store unavailable" in response.text
    assert 'data-sources="finance"' in response.text


def test_edge_view_does_not_run_slow_identification_by_default(monkeypatch):
    from causal_coding import identifiability

    def unexpected(*arguments):
        pytest.fail("DoWhy must only run when explicitly requested")

    monkeypatch.setattr(identifiability, "_identify", unexpected)
    assert TestClient(web.app).get("/edge/K6").status_code == 200


def test_later_updates_to_old_entities_are_ingested():
    database = create_engine("sqlite://")
    for model in (DevLakePullRequest, DevLakeCicdTask, DevLakeCicdDeployment, DevLakeIncident):
        model.__table__.create(database)
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(database)
    created = datetime(2026, 1, 1, tzinfo=UTC)
    updated = datetime(2026, 1, 3, tzinfo=UTC)
    watermark = datetime(2026, 1, 2, tzinfo=UTC)
    with Session(database) as session:
        session.add(DevLakePullRequest(id="pr", base_repo_id="repo", created_date=created, updated_at=updated, merged_date=updated))
        session.add(DevLakeCicdTask(id="ci", created_date=created, updated_at=updated, finished_date=updated))
        session.add(DevLakeCicdDeployment(id="deployment", created_date=created, updated_at=updated, finished_date=updated))
        session.add(DevLakeIncident(id="incident", created_date=created, updated_at=updated, resolution_date=updated))
        from causal_coding.devlake.tables import DevLakeCicdDeploymentCommit

        session.add(DevLakeCicdDeploymentCommit(id="link", cicd_deployment_id="deployment", repo_id="repo", commit_sha="sha"))
        session.commit()
        batches = [
            fetch_pull_requests(session, {"repo": "team"}, since=watermark, observed_at=NOW).events,
            fetch_ci_runs(session, since=watermark, observed_at=NOW),
            fetch_deployments(session, {"repo": "team"}, since=watermark, observed_at=NOW).events,
            fetch_incidents(session, since=watermark, observed_at=NOW),
        ]
        for batch in batches:
            assert len(batch) == 1
            assert batch[0].observed_at == NOW
        assert batches[0][0].additions is None
        assert batches[0][0].is_draft is None
        assert not fetch_pull_requests(session, {"repo": "team"}, since=datetime(2026, 1, 5, tzinfo=UTC)).events


def test_commit_links_round_trip_and_join_once_to_first_production_deployment(engine):
    save(engine, PullRequest, pull_request_id="pr", repository_id="repo", team_id="team", opened_at=datetime(2026, 1, 1, tzinfo=UTC), first_commit_at=datetime(2026, 1, 1, tzinfo=UTC), merged_at=datetime(2026, 1, 2, tzinfo=UTC), commit_shas=["old-sha", "sha"], merge_commit_sha="merge")
    for deployment_id, commit, day, team in (("obsolete", "old-sha", 2, "team"), ("wrong-team", "merge", 2, "another"), ("first", "merge", 3, "team"), ("repeat", "merge", 4, "team")):
        save(engine, Deployment, deployment_id=deployment_id, team_id=team, environment="PRODUCTION", status="SUCCESS", deployed_at=datetime(2026, 1, day, tzinfo=UTC), commit_shas=[commit])
    with Session(engine) as session:
        changes = deployed_changes(session)
        assert len(changes) == 1
        assert changes[0].deployment_id == "first"
        assert changes[0].lead_time_hours == 48


def test_legacy_schema_upgrade_preserves_rows_and_is_idempotent():
    database = create_engine("sqlite://")
    metadata = MetaData()
    for model in (PullRequest, CIRun):
        columns = []
        for column in model.__table__.columns:
            if column.name not in {"commit_shas", "merge_commit_sha"}:
                columns.append(Column(column.name, column.type, primary_key=column.primary_key, nullable=False if column.name in {"additions", "deletions", "is_draft", "required"} else column.nullable))
        Table(model.__tablename__, metadata, *columns)
    Table("unrelated", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(database)
    with database.begin() as connection:
        connection.execute(text("INSERT INTO ingested_pull_requests (id, observed_at, source_system, pull_request_id, repository_id, team_id, opened_at, is_draft, additions, deletions) VALUES (1, '2026-01-01', 'devlake', 'pr', 'repo', 'team', '2026-01-01', 0, 100, 50)"))
    upgrade_schema(database)
    upgrade_schema(database)
    with Session(database) as session:
        pull_request = session.exec(select(PullRequest.__table__)).one()
        assert pull_request.pull_request_id == "pr"
        assert pull_request.additions is None
        assert pull_request.is_draft is None
    assert "unrelated" in inspect(database).get_table_names()
    assert set(inspect(database).get_table_names()) == {table.name for table in OWN_TABLES} | {"unrelated"}


def test_static_export_is_self_contained_and_covers_all_edge_statuses(tmp_path):
    output = render(tmp_path / "model.html", view="full").read_text()
    assert "pyvis" not in output
    assert '<script src=' not in output
    assert "mechanistic" in output
    assert "agentic_task_share" not in output
    assert "agentic task share" in output


@pytest.mark.parametrize("route", ["/?view=invalid", "/focus/revenue?view=invalid", "/sources?view=invalid"])
def test_invalid_view_is_rejected(route):
    assert TestClient(web.app).get(route).status_code == 422
