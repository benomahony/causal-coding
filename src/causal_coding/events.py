"""Ingestion contracts for engineering telemetry -- and, simultaneously, their storage schema.

Each class is a SQLModel table: the pydantic contract a source (devlake/, or
any future connector) constructs and validates against *is* the Postgres
table it gets persisted into. There is no separate hand-maintained schema to
drift out of sync with the interface.

Tablenames are prefixed `ingested_` because `devlake/tables.py` registers its
own SQLModel classes (read-only mirrors of DevLake's external MySQL schema,
e.g. tablename "pull_requests") in the same global `SQLModel.metadata`
registry; without the prefix, `PullRequest` here and DevLake's own
`pull_requests` table would collide.

List-valued fields use `list[...]` backed by a JSON column rather than
Postgres `ARRAY`, so the same schema round-trips on SQLite in tests without a
live Postgres instance.

IMPORTANT: SQLModel `table=True` classes do NOT run pydantic validation on
plain `Model(**kwargs)` construction -- required fields silently go missing
and types silently fail to coerce, no error either way. Always construct
these via `Model.model_validate(dict(...))` (or the `ingest_event` helper
below) when the data comes from outside this process, e.g. a connector like
devlake/ingest.py. Bare `Model(**kwargs)` is fine only for values you already
know are well-typed (e.g. re-hydrating from a trusted in-process source).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _json_list(*, required: bool = False) -> list:
    if required:
        return Field(sa_column=Column(JSON))
    return Field(default_factory=list, sa_column=Column(JSON))


def ingest_event[T: SQLModel](cls: type[T], **kwargs: Any) -> T:
    """Construct a table-backed event with real pydantic validation.

    Thin wrapper around `cls.model_validate(kwargs)` -- exists so connectors
    can't accidentally fall back to unvalidated `cls(**kwargs)` construction.
    """
    return cls.model_validate(kwargs)


class Event(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    observed_at: datetime
    source_system: str


class AgentSession(Event, table=True):
    __tablename__ = "ingested_agent_sessions"

    session_id: str
    team_id: str
    person_id: str | None = None
    task_id: str | None = None
    pull_request_id: str | None = None
    model: str | None = None
    active_seconds: int | None = None
    available_tools: list[str] = _json_list()
    tool_permissions: list[str] = _json_list()
    tool_calls: int = 0
    execution_steps: int | None = None
    human_messages: int = 0
    human_interventions: int | None = None
    approval_events: int = 0
    takeover_events: int | None = None
    clarification_events: int | None = None
    required_context_items: list[str] = _json_list()
    retrieved_context_items: list[str] = _json_list()
    context_age_seconds: list[int] = _json_list()
    material_agent_work: bool | None = None
    agent_edit_bytes: int | None = None
    total_edit_bytes: int | None = None
    session_outcome: str | None = None


class PullRequest(Event, table=True):
    __tablename__ = "ingested_pull_requests"

    pull_request_id: str
    repository_id: str
    team_id: str
    opened_at: datetime
    ready_for_review_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    is_draft: bool | None = None
    additions: int | None = Field(default=None, ge=0)
    deletions: int | None = Field(default=None, ge=0)
    changed_files: list[str] | None = Field(default=None, sa_column=Column(JSON))
    first_commit_at: datetime | None = None
    commit_shas: list[str] = _json_list()
    merge_commit_sha: str | None = None


class ReviewEvent(Event, table=True):
    __tablename__ = "ingested_review_events"

    pull_request_id: str
    reviewer_id: str
    review_requested_at: datetime | None = None
    review_started_at: datetime | None = None
    review_submitted_at: datetime
    state: str
    substantive: bool = True


class CIRun(Event, table=True):
    __tablename__ = "ingested_ci_runs"

    ci_run_id: str
    pull_request_id: str | None = None
    commit_sha: str
    check_category: str
    required: bool | None = None
    triggered_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str | None = None
    failure_classification: str | None = None


class Deployment(Event, table=True):
    __tablename__ = "ingested_deployments"

    deployment_id: str
    team_id: str
    environment: str
    status: str
    deployed_at: datetime
    commit_shas: list[str] = _json_list(required=True)
    manual_intervention: bool | None = None
    deployment_type: str | None = None
    rollback_of_deployment_id: str | None = None


class Incident(Event, table=True):
    __tablename__ = "ingested_incidents"

    incident_id: str
    started_at: datetime
    resolved_at: datetime | None = None
    severity: str | None = None
    attributable_deployment_ids: list[str] = _json_list()


class WorkItem(Event, table=True):
    __tablename__ = "ingested_work_items"

    work_item_id: str
    team_id: str
    status: str
    status_changed_at: datetime


class RepositorySnapshot(Event, table=True):
    __tablename__ = "ingested_repository_snapshots"

    repository_id: str
    files_in_scope: int | None = None
    typed_files: int | None = None
    files_analyzed: int | None = None
    required_checks: list[str] = _json_list()
    required_rules: list[str] = _json_list()
    declared_boundaries: list[str] = _json_list()
    enforced_boundaries: list[str] = _json_list()
    known_contracts: list[str] = _json_list()
    tested_contracts: list[str] = _json_list()
    applicable_policies: list[str] = _json_list()
    automated_policy_checks: list[str] = _json_list()
    component_map_version: str | None = None
    documentation_paths: list[str] = _json_list()
    test_targets: list[str] = _json_list()


class ComponentDefinition(Event, table=True):
    """Maps repository paths to a declared component, versioned over time.

    Backs `component_map` wherever it appears in measurements.py raw_inputs
    (modularity, coupling, documentation_quality, testability, change_diffusion).
    DevLake's own `components`/`commit_file_components` tables can source this
    directly if the DevLake project has component definitions configured.
    """

    __tablename__ = "ingested_component_definitions"

    repository_id: str
    component_name: str
    path_patterns: list[str] = _json_list(required=True)
    version: str | None = None


class ComponentOwnership(Event, table=True):
    """Maps a declared component to the team responsible for it, versioned over time.

    Backs `ownership_map` wherever it appears in measurements.py raw_inputs
    (coupling, change_diffusion). Not derivable from DevLake -- DevLake has no
    ownership concept, so this needs a CODEOWNERS-style file or an internal
    ownership registry as its source.
    """

    __tablename__ = "ingested_component_ownerships"

    repository_id: str
    component_name: str
    owner_team_id: str
    effective_from: datetime
    effective_to: datetime | None = None


class TeamMembership(Event, table=True):
    __tablename__ = "ingested_team_memberships"

    team_id: str
    person_id: str
    joined_at: datetime
    left_at: datetime | None = None
    domain_start_date: datetime | None = None
    capacity_hours: float | None = None
    allocated_nonreview_hours: float | None = None


class EnvironmentProvision(Event, table=True):
    __tablename__ = "ingested_environment_provisions"

    environment_id: str
    team_id: str
    requested_at: datetime
    ready_at: datetime | None = None
    environment_type: str | None = None


class ServiceObservabilitySnapshot(Event, table=True):
    __tablename__ = "ingested_service_observability_snapshots"

    service_id: str
    repository_id: str | None = None
    critical: bool = False
    logs_enabled: bool | None = None
    metrics_enabled: bool | None = None
    traces_enabled: bool | None = None
    owner_defined: bool | None = None


class AgentPolicySnapshot(Event, table=True):
    __tablename__ = "ingested_agent_policy_snapshots"

    team_id: str
    allowed_actions: list[str] = _json_list(required=True)
    approval_requirements: list[str] = _json_list()


class AgentBenchmarkResult(Event, table=True):
    __tablename__ = "ingested_agent_benchmark_results"

    benchmark_task_id: str
    model: str
    tools: list[str] = _json_list(required=True)
    success: bool
    task_family: str | None = None
