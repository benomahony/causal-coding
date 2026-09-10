from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from causal_coding.devlake.ingest import (
    fetch_ci_runs,
    fetch_deployments,
    fetch_incidents,
    fetch_pull_requests,
    fetch_review_events,
    fetch_work_items,
)
from causal_coding.devlake.tables import (
    DevLakeCicdDeployment,
    DevLakeCicdDeploymentCommit,
    DevLakeCicdPipelineCommit,
    DevLakeCicdTask,
    DevLakeCommit,
    DevLakeCommitFile,
    DevLakeIncident,
    DevLakeIssue,
    DevLakeIssueChangelog,
    DevLakePullRequest,
    DevLakePullRequestComment,
    DevLakePullRequestCommit,
)

REPO_ID = "github:GithubRepo:1:12345"
TEAM_MAP = {REPO_ID: "team-checkout", "CHECKOUT": "team-checkout"}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_fetch_pull_requests_maps_size_and_first_commit(session):
    session.add(
        DevLakePullRequest(
            id="pr-1",
            base_repo_id=REPO_ID,
            status="MERGED",
            created_date=datetime(2026, 1, 1, tzinfo=UTC),
            merged_date=datetime(2026, 1, 3, tzinfo=UTC),
            additions=8,
            deletions=1,
            is_draft=False,
            merge_commit_sha="merge-sha",
        )
    )
    session.add(DevLakePullRequestCommit(pull_request_id="pr-1", commit_sha="sha-a"))
    session.add(DevLakePullRequestCommit(pull_request_id="pr-1", commit_sha="sha-b"))
    session.add(DevLakeCommit(sha="sha-a", authored_date=datetime(2026, 1, 1, 9, tzinfo=UTC), additions=10, deletions=2))
    session.add(DevLakeCommit(sha="sha-b", authored_date=datetime(2026, 1, 1, 10, tzinfo=UTC), additions=5, deletions=1))
    session.add(DevLakeCommitFile(id="sha-a:x.py", commit_sha="sha-a", file_path="x.py"))
    session.add(DevLakeCommitFile(id="sha-b:y.py", commit_sha="sha-b", file_path="y.py"))
    session.commit()

    result = fetch_pull_requests(session, TEAM_MAP)

    assert result.unmapped_scope_keys == frozenset()
    assert len(result.events) == 1
    pr = result.events[0]
    assert pr.team_id == "team-checkout"
    assert pr.additions == 8
    assert pr.deletions == 1
    assert pr.changed_files is None
    assert pr.commit_shas == ["sha-a", "sha-b"]
    assert pr.merge_commit_sha == "merge-sha"
    # sqlite drops tzinfo on round-trip, matching DevLake's own naive datetime(3) columns.
    assert pr.first_commit_at == datetime(2026, 1, 1, 9, tzinfo=UTC).replace(tzinfo=None)
    assert pr.is_draft is False


def test_fetch_pull_requests_reports_unmapped_repo(session):
    session.add(
        DevLakePullRequest(
            id="pr-2",
            base_repo_id="github:GithubRepo:1:99999",
            status="OPEN",
            created_date=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()

    result = fetch_pull_requests(session, TEAM_MAP)

    assert result.events == ()
    assert "github:GithubRepo:1:99999" in result.unmapped_scope_keys


def test_fetch_review_events_filters_by_type(session):
    session.add(
        DevLakePullRequestComment(
            id="c-1",
            pull_request_id="pr-1",
            account_id="acct-1",
            created_date=datetime(2026, 1, 2, tzinfo=UTC),
            type="REVIEW",
            status="APPROVED",
        )
    )
    session.add(
        DevLakePullRequestComment(
            id="c-2",
            pull_request_id="pr-1",
            account_id="acct-2",
            created_date=datetime(2026, 1, 2, tzinfo=UTC),
            type="NORMAL",
        )
    )
    session.commit()

    events = fetch_review_events(session)

    assert len(events) == 1
    assert events[0].reviewer_id == "acct-1"
    assert events[0].state == "APPROVED"


def test_fetch_ci_runs_resolves_commit_via_pipeline(session):
    session.add(
        DevLakeCicdTask(
            id="task-1",
            pipeline_id="pipe-1",
            result="SUCCESS",
            type="TEST",
            created_date=datetime(2026, 1, 1, tzinfo=UTC),
            started_date=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            finished_date=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        )
    )
    session.add(DevLakeCicdPipelineCommit(pipeline_id="pipe-1", commit_sha="sha-a", repo_id=REPO_ID))
    session.commit()

    runs = fetch_ci_runs(session)

    assert len(runs) == 1
    assert runs[0].commit_sha == "sha-a"
    assert runs[0].required is None


def test_fetch_deployments_resolves_team_from_linked_repo(session):
    session.add(
        DevLakeCicdDeployment(
            id="deploy-1",
            result="SUCCESS",
            environment="PRODUCTION",
            created_date=datetime(2026, 1, 4, tzinfo=UTC),
            finished_date=datetime(2026, 1, 4, 0, 10, tzinfo=UTC),
        )
    )
    session.add(
        DevLakeCicdDeploymentCommit(
            id="dc-1", cicd_deployment_id="deploy-1", commit_sha="sha-a", repo_id=REPO_ID
        )
    )
    session.commit()

    result = fetch_deployments(session, TEAM_MAP)

    assert len(result.events) == 1
    deployment = result.events[0]
    assert deployment.team_id == "team-checkout"
    assert deployment.commit_shas == ["sha-a"]
    assert deployment.status == "SUCCESS"
    assert deployment.manual_intervention is None


def test_fetch_incidents_maps_severity_and_timing(session):
    session.add(
        DevLakeIncident(
            id="inc-1", created_date=datetime(2026, 1, 5, tzinfo=UTC), resolution_date=datetime(2026, 1, 5, 2, tzinfo=UTC), severity="SEV2"
        )
    )
    session.commit()

    incidents = fetch_incidents(session)

    assert len(incidents) == 1
    assert incidents[0].severity == "SEV2"
    assert incidents[0].attributable_deployment_ids == []


def test_fetch_work_items_uses_changelog_for_status_transitions(session):
    session.add(DevLakeIssue(id="issue-1", original_project="CHECKOUT", status="Done"))
    session.add(
        DevLakeIssueChangelog(
            id="log-1", issue_id="issue-1", field_name="status", to_value="In Progress", created_date=datetime(2026, 1, 2, tzinfo=UTC)
        )
    )
    session.add(
        DevLakeIssueChangelog(
            id="log-2", issue_id="issue-1", field_name="status", to_value="Done", created_date=datetime(2026, 1, 3, tzinfo=UTC)
        )
    )
    session.commit()

    result = fetch_work_items(session, TEAM_MAP)

    assert result.unmapped_scope_keys == frozenset()
    assert len(result.events) == 2
    assert {e.status for e in result.events} == {"In Progress", "Done"}
    assert all(e.team_id == "team-checkout" for e in result.events)
