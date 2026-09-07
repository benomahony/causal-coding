from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)
    observed_at: datetime
    source_system: str


class AgentSession(Event):
    session_id: str
    team_id: str
    person_id: str | None = None
    task_id: str | None = None
    pull_request_id: str | None = None
    model: str | None = None
    active_seconds: int | None = None
    available_tools: tuple[str, ...] = ()
    tool_permissions: tuple[str, ...] = ()
    tool_calls: int = 0
    execution_steps: int | None = None
    human_messages: int = 0
    human_interventions: int | None = None
    approval_events: int = 0
    takeover_events: int | None = None
    clarification_events: int | None = None
    required_context_items: tuple[str, ...] = ()
    retrieved_context_items: tuple[str, ...] = ()
    context_age_seconds: tuple[int, ...] = ()
    material_agent_work: bool | None = None
    agent_edit_bytes: int | None = None
    total_edit_bytes: int | None = None
    session_outcome: str | None = None


class PullRequest(Event):
    pull_request_id: str
    repository_id: str
    team_id: str
    opened_at: datetime
    ready_for_review_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    is_draft: bool
    additions: int
    deletions: int
    changed_files: tuple[str, ...]
    first_commit_at: datetime | None = None


class ReviewEvent(Event):
    pull_request_id: str
    reviewer_id: str
    review_requested_at: datetime | None = None
    review_started_at: datetime | None = None
    review_submitted_at: datetime
    state: str
    substantive: bool = True


class CIRun(Event):
    ci_run_id: str
    pull_request_id: str | None = None
    commit_sha: str
    check_category: str
    required: bool = True
    triggered_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str | None = None
    failure_classification: str | None = None


class Deployment(Event):
    deployment_id: str
    team_id: str
    environment: str
    status: str
    deployed_at: datetime
    commit_shas: tuple[str, ...]
    manual_intervention: bool | None = None
    deployment_type: str | None = None
    rollback_of_deployment_id: str | None = None


class Incident(Event):
    incident_id: str
    started_at: datetime
    resolved_at: datetime | None = None
    severity: str | None = None
    attributable_deployment_ids: tuple[str, ...] = ()


class WorkItem(Event):
    work_item_id: str
    team_id: str
    status: str
    status_changed_at: datetime


class RepositorySnapshot(Event):
    repository_id: str
    files_in_scope: int | None = None
    typed_files: int | None = None
    files_analyzed: int | None = None
    required_checks: tuple[str, ...] = ()
    required_rules: tuple[str, ...] = ()
    declared_boundaries: tuple[str, ...] = ()
    enforced_boundaries: tuple[str, ...] = ()
    known_contracts: tuple[str, ...] = ()
    tested_contracts: tuple[str, ...] = ()
    applicable_policies: tuple[str, ...] = ()
    automated_policy_checks: tuple[str, ...] = ()
    component_map_version: str | None = None
    documentation_paths: tuple[str, ...] = ()
    test_targets: tuple[str, ...] = ()


class TeamMembership(Event):
    team_id: str
    person_id: str
    joined_at: datetime
    left_at: datetime | None = None
    domain_start_date: datetime | None = None
    capacity_hours: float | None = None
    allocated_nonreview_hours: float | None = None


class EnvironmentProvision(Event):
    environment_id: str
    team_id: str
    requested_at: datetime
    ready_at: datetime | None = None
    environment_type: str | None = None


class ServiceObservabilitySnapshot(Event):
    service_id: str
    repository_id: str | None = None
    critical: bool = False
    logs_enabled: bool | None = None
    metrics_enabled: bool | None = None
    traces_enabled: bool | None = None
    owner_defined: bool | None = None


class AgentPolicySnapshot(Event):
    team_id: str
    allowed_actions: tuple[str, ...]
    approval_requirements: tuple[str, ...] = ()


class AgentBenchmarkResult(Event):
    benchmark_task_id: str
    model: str
    tools: tuple[str, ...]
    success: bool
    task_family: str | None = None
