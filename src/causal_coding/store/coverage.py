"""Field-level collection coverage, independent of statistical estimability.

Raw inputs, proxies and latent constructs remain distinct. Usable input rows
are not an analysis dataset: joins, time alignment, sample size, overlap and
causal assumptions still need validation. Fixtures never unlock live coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, String, cast, func, select

from causal_coding import commercial_events as commercial
from causal_coding import events
from causal_coding.data_requirements import sources_by_variable
from causal_coding.measurements import Observability, Source, measurement_for
from causal_coding.model import graph
from causal_coding.survey_events import SurveyResponse

SOURCE_TABLES: dict[Source, tuple[type, ...]] = {
    Source.SCM: (events.PullRequest, events.ReviewEvent),
    Source.CI: (events.CIRun,),
    Source.CD: (events.Deployment,),
    Source.ISSUE_TRACKER: (events.WorkItem,),
    Source.INCIDENT_MANAGEMENT: (events.Incident,),
    Source.REPOSITORY: (events.ComponentDefinition, events.ComponentOwnership, events.RepositorySnapshot),
    Source.STATIC_ANALYSIS: (events.RepositorySnapshot,),
    Source.ORG_DATA: (events.TeamMembership, events.AgentPolicySnapshot),
    Source.PLATFORM: (events.EnvironmentProvision, events.ServiceObservabilitySnapshot),
    Source.AGENT_TELEMETRY: (events.AgentSession, events.AgentBenchmarkResult),
    Source.SURVEY: (SurveyResponse,),
    Source.PRODUCT_ANALYTICS: (
        commercial.ProductExperiment, commercial.ProductDecision, commercial.CustomerSession,
        commercial.ProductHypothesis, commercial.CustomerOutcomeEvent, commercial.CustomerActivation,
        commercial.CustomerRetentionSnapshot,
    ),
    Source.FINANCE: (commercial.FinanceRecord, commercial.EngineeringCostRecord, commercial.ServiceCostRecord),
}


@dataclass(frozen=True)
class InputRule:
    table: type
    fields: tuple[str, ...]
    nonempty: tuple[str, ...] = ()
    positive: tuple[str, ...] = ()


METRIC_INPUTS = {
    "task_benchmark_success_rate": InputRule(events.AgentBenchmarkResult, ("benchmark_task_id", "model", "tools", "success")),
    "effective_tool_surface": InputRule(events.AgentSession, ("session_id", "available_tools", "tool_permissions")),
    "permitted_action_level": InputRule(events.AgentPolicySnapshot, ("team_id", "allowed_actions", "approval_requirements")),
    "unassisted_execution_fraction": InputRule(events.AgentSession, ("execution_steps", "human_interventions", "approval_events", "takeover_events"), positive=("execution_steps",)),
    "required_context_recall": InputRule(events.AgentSession, ("required_context_items", "retrieved_context_items"), nonempty=("required_context_items",)),
    "team_domain_tenure": InputRule(events.TeamMembership, ("person_id", "team_id", "domain_start_date")),
    "available_review_hours": InputRule(events.TeamMembership, ("team_id", "capacity_hours", "allocated_nonreview_hours")),
    "dora_capability_scale_score": InputRule(SurveyResponse, ("team_id", "instrument", "instrument_version", "items"), nonempty=("items",)),
    "typed_surface_fraction": InputRule(events.RepositorySnapshot, ("repository_id", "files_in_scope", "typed_files", "required_checks"), nonempty=("required_checks",), positive=("files_in_scope",)),
    "static_rule_surface_fraction": InputRule(events.RepositorySnapshot, ("repository_id", "files_in_scope", "files_analyzed", "required_rules"), nonempty=("required_rules",), positive=("files_in_scope",)),
    "enforced_boundary_fraction": InputRule(events.RepositorySnapshot, ("repository_id", "declared_boundaries", "enforced_boundaries"), nonempty=("declared_boundaries",)),
    "tested_contract_fraction": InputRule(events.RepositorySnapshot, ("repository_id", "known_contracts", "tested_contracts", "required_checks"), nonempty=("known_contracts", "required_checks")),
    "automated_policy_fraction": InputRule(events.RepositorySnapshot, ("repository_id", "applicable_policies", "automated_policy_checks"), nonempty=("applicable_policies",)),
    "p50_environment_ready_time": InputRule(events.EnvironmentProvision, ("team_id", "requested_at", "ready_at")),
    "fully_automated_deployment_fraction": InputRule(events.Deployment, ("deployment_id", "team_id", "environment", "status", "manual_intervention")),
    "diagnostic_signal_coverage": InputRule(events.ServiceObservabilitySnapshot, ("service_id", "critical", "logs_enabled", "metrics_enabled", "traces_enabled", "owner_defined")),
    "reviewable_pr_arrival_rate": InputRule(events.PullRequest, ("pull_request_id", "team_id", "ready_for_review_at")),
    "requested_review_count": InputRule(events.ReviewEvent, ("pull_request_id", "review_requested_at", "reviewer_id")),
    "substantive_review_events": InputRule(events.ReviewEvent, ("pull_request_id", "reviewer_id", "review_submitted_at", "substantive")),
    "review_queue_wait": InputRule(events.ReviewEvent, ("pull_request_id", "review_requested_at", "review_started_at")),
    "diff_size": InputRule(events.PullRequest, ("pull_request_id", "additions", "deletions")),
    "large_change_fraction": InputRule(events.PullRequest, ("pull_request_id", "additions", "deletions", "changed_files")),
    "successful_prod_deployments": InputRule(events.Deployment, ("deployment_id", "team_id", "environment", "status", "deployed_at")),
    "completed_product_experiments": InputRule(commercial.ProductExperiment, ("experiment_id", "started_at", "completed_at", "hypothesis", "result")),
    "decision_to_value_hours": InputRule(commercial.ProductDecision, ("decision_id", "committed_at", "deployment_id", "customer_available_at")),
    "customer_impact_free_session_fraction": InputRule(commercial.CustomerSession, ("session_id", "service_errors", "availability_impact", "correctness_impact")),
    "validated_hypotheses_per_week": InputRule(commercial.ProductHypothesis, ("hypothesis_id", "decision", "evidence_threshold", "resolved_at")),
    "core_outcome_success_rate": InputRule(commercial.CustomerOutcomeEvent, ("customer_id", "core_outcome_event", "success")),
    "activated_customers": InputRule(commercial.CustomerActivation, ("customer_id", "activation_event", "occurred_at")),
    "recognised_revenue": InputRule(commercial.FinanceRecord, ("period", "product_id", "recognised_revenue")),
    "engineering_delivery_cost": InputRule(commercial.EngineeringCostRecord, ("period", "engineering_labour_cost", "agent_compute_cost", "tooling_cost")),
    "service_cost": InputRule(commercial.ServiceCostRecord, ("period", "infrastructure_cost", "support_cost", "incident_cost")),
}


@dataclass(frozen=True)
class TableSummary:
    table_name: str
    row_count: int
    earliest_observed_at: datetime | None
    latest_observed_at: datetime | None
    fixture_row_count: int = 0


def _table_summary(connection, table: type) -> TableSummary:
    count, earliest, latest = connection.execute(
        select(func.count(), func.min(table.observed_at), func.max(table.observed_at))
        .where(table.source_system != "fixtures")
    ).one()
    fixtures = connection.execute(
        select(func.count()).select_from(table).where(table.source_system == "fixtures")
    ).scalar_one()
    return TableSummary(table.__tablename__, count, earliest, latest, fixtures)


def _usable_rows(connection, rule: InputRule) -> int:
    table = rule.table
    conditions = [table.source_system != "fixtures"]
    for field in rule.fields:
        column = getattr(table, field)
        conditions.extend((column.is_not(None), cast(column, String).not_in(("", "null"))))
    for field in rule.nonempty:
        conditions.append(cast(getattr(table, field), String).not_in(("[]", "{}")))
    conditions.extend(getattr(table, field) > 0 for field in rule.positive)
    return connection.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()


@dataclass(frozen=True)
class VariableDataSummary:
    variable: str
    sources: tuple[str, ...]
    table_summaries: tuple[TableSummary, ...]
    usable_row_count: int
    status: str
    explanation: str

    @property
    def row_count(self) -> int:
        return sum(table.row_count for table in self.table_summaries)

    @property
    def inputs_available(self) -> bool:
        return self.status == "inputs_available"

    @property
    def latest_observed_at(self) -> datetime | None:
        timestamps = [table.latest_observed_at for table in self.table_summaries if table.latest_observed_at]
        return max(timestamps, default=None)


def _variable_summary(connection, variable: str, table_cache: dict) -> VariableDataSummary:
    measurement = measurement_for(variable)
    rules = [(metric, METRIC_INPUTS[metric.name]) for metric in measurement.candidates if metric.name in METRIC_INPUTS]
    tables = tuple(dict.fromkeys(rule.table for _, rule in rules))
    for table in tables:
        if table not in table_cache:
            table_cache[table] = _table_summary(connection, table)
    counts = [(metric, _usable_rows(connection, rule)) for metric, rule in rules]
    usable = max((count for _, count in counts), default=0)
    direct = any(count and metric.observability in {Observability.DIRECT, Observability.DERIVED} for metric, count in counts)
    if all(metric.observability == Observability.LATENT for metric in measurement.candidates):
        status, explanation = "latent", "A counterfactual or decision target; raw telemetry cannot make it directly observed."
    elif direct:
        status, explanation = "inputs_available", "Required fields are present. Derivation, scope and time alignment still need validation."
    elif usable:
        status, explanation = "proxy", "Proxy inputs are present; they do not directly observe the underlying construct."
    elif not rules:
        status, explanation = "needs_derivation", "This measurement needs additional instrumentation or validated joins; source presence alone is insufficient."
    else:
        status, explanation = "missing", "No real rows contain all required inputs for this variable. Fixture rows are excluded."
    return VariableDataSummary(
        variable, tuple(source.value for source in sources_by_variable()[variable]),
        tuple(table_cache[table] for table in tables), usable, status, explanation,
    )


def variable_data_summary(engine: Engine, variable: str) -> VariableDataSummary:
    with engine.connect() as connection:
        return _variable_summary(connection, variable, {})


def variable_summaries(engine: Engine) -> dict[str, VariableDataSummary]:
    table_cache: dict = {}
    with engine.connect() as connection:
        return {variable: _variable_summary(connection, variable, table_cache) for variable in sorted(graph())}


@dataclass(frozen=True)
class SourceSummary:
    source: str
    connected: bool
    row_count: int
    latest_observed_at: datetime | None
    table_summaries: tuple[TableSummary, ...]
    unlocked_variable_count: int
    fixture_row_count: int = 0


def all_sources_summary(engine: Engine | None) -> tuple[SourceSummary, ...]:
    table_cache = {}
    if engine is not None:
        with engine.connect() as connection:
            for tables in SOURCE_TABLES.values():
                for table in tables:
                    if table not in table_cache:
                        table_cache[table] = _table_summary(connection, table)
    summaries = []
    for source, tables in SOURCE_TABLES.items():
        table_summaries = tuple(table_cache[table] for table in tables if table in table_cache)
        row_count = sum(table.row_count for table in table_summaries)
        latest = [table.latest_observed_at for table in table_summaries if table.latest_observed_at]
        summaries.append(SourceSummary(
            source.value, row_count > 0, row_count, max(latest, default=None), table_summaries,
            len(observed_variables(frozenset({source}))),
            sum(table.fixture_row_count for table in table_summaries),
        ))
    return tuple(sorted(summaries, key=lambda summary: summary.source))


def sources_with_data(engine: Engine) -> frozenset[Source]:
    return frozenset(Source(summary.source) for summary in all_sources_summary(engine) if summary.connected)


def observed_variables(sources: frozenset[Source]) -> frozenset[str]:
    """Hypothetical source coverage only; never use this as evidence of live observations."""
    return frozenset(
        variable for variable in graph()
        if any(
            metric.source in sources and metric.observability in {Observability.DIRECT, Observability.DERIVED}
            for metric in measurement_for(variable).candidates
        )
    )
