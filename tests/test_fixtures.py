from __future__ import annotations

from sqlmodel import Session, create_engine, select

from causal_coding.commercial_events import FinanceRecord
from causal_coding.events import (
    ComponentDefinition,
    ComponentOwnership,
    Deployment,
    Incident,
    PullRequest,
)
from causal_coding.store import OWN_TABLES, create_schema, save_events
from causal_coding.store.fixtures import generate_all


def test_generate_all_covers_every_table_exactly_once():
    data = generate_all()
    assert set(data.keys()) == {t.name for t in OWN_TABLES}
    assert all(rows for rows in data.values()), "every table should get at least one fixture row"


def test_generate_all_is_deterministic():
    assert generate_all(seed=0)["ingested_pull_requests"][0].additions == generate_all(seed=0)["ingested_pull_requests"][0].additions
    a = [pr.additions for pr in generate_all(seed=1)["ingested_pull_requests"]]
    b = [pr.additions for pr in generate_all(seed=1)["ingested_pull_requests"]]
    assert a == b


def test_component_ownership_references_a_defined_component():
    data = generate_all()
    defined = {(c.repository_id, c.component_name) for c in data["ingested_component_definitions"]}
    owned = {(c.repository_id, c.component_name) for c in data["ingested_component_ownerships"]}
    assert owned <= defined


def test_deployments_only_generated_for_merged_pull_requests():
    data = generate_all()
    merged_shas = {f"sha-{pr.pull_request_id}" for pr in data["ingested_pull_requests"] if pr.merged_at is not None}
    for deployment in data["ingested_deployments"]:
        assert set(deployment.commit_shas) <= merged_shas


def test_incidents_only_attributed_to_failed_deployments():
    data = generate_all()
    failed_ids = {d.deployment_id for d in data["ingested_deployments"] if d.status == "FAILURE"}
    for incident in data["ingested_incidents"]:
        assert set(incident.attributable_deployment_ids) <= failed_ids


def test_full_fixture_dataset_round_trips_through_the_store():
    engine = create_engine("sqlite://")
    create_schema(engine)
    data = generate_all()

    with Session(engine) as session:
        for rows in data.values():
            save_events(session, rows)

    with Session(engine) as session:
        assert len(session.exec(select(PullRequest)).all()) == len(data["ingested_pull_requests"])
        assert len(session.exec(select(Deployment)).all()) == len(data["ingested_deployments"])
        assert len(session.exec(select(Incident)).all()) == len(data["ingested_incidents"])
        assert len(session.exec(select(ComponentDefinition)).all()) == len(data["ingested_component_definitions"])
        assert len(session.exec(select(ComponentOwnership)).all()) == len(data["ingested_component_ownerships"])
        assert len(session.exec(select(FinanceRecord)).all()) == len(data["ingested_finance_records"])
