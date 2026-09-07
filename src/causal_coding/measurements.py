from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Observability(StrEnum):
    DIRECT = "direct"
    DERIVED = "derived"
    PROXY = "proxy"
    LATENT = "latent"


class Grain(StrEnum):
    AGENT_SESSION = "agent_session"
    TASK = "task"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    CI_RUN = "ci_run"
    DEPLOYMENT = "deployment"
    INCIDENT = "incident"
    REPOSITORY_DAY = "repository_day"
    TEAM_WEEK = "team_week"
    PRODUCT_WEEK = "product_week"
    BUSINESS_MONTH = "business_month"


class Source(StrEnum):
    AGENT_TELEMETRY = "agent_telemetry"
    SCM = "scm"
    CI = "ci"
    CD = "cd"
    ISSUE_TRACKER = "issue_tracker"
    INCIDENT_MANAGEMENT = "incident_management"
    STATIC_ANALYSIS = "static_analysis"
    REPOSITORY = "repository"
    ORG_DATA = "org_data"
    SURVEY = "survey"
    PLATFORM = "platform"
    PRODUCT_ANALYTICS = "product_analytics"
    FINANCE = "finance"


class Metric(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    source: Source
    grain: Grain
    observability: Observability
    unit: str
    definition: str
    raw_inputs: tuple[str, ...]
    aggregation: str | None = None
    caveat: str | None = None


class VariableMeasurement(BaseModel):
    model_config = ConfigDict(frozen=True)

    variable: str
    construct_definition: str
    preferred_metric: str | None
    candidates: tuple[Metric, ...]


def m(name: str, source: Source, grain: Grain, obs: Observability, unit: str, definition: str, inputs: tuple[str, ...], aggregation: str | None = None, caveat: str | None = None) -> Metric:
    return Metric(name=name, source=source, grain=grain, observability=obs, unit=unit, definition=definition, raw_inputs=inputs, aggregation=aggregation, caveat=caveat)


def vm(variable: str, definition: str, preferred: str | None, *metrics: Metric) -> VariableMeasurement:
    return VariableMeasurement(variable=variable, construct_definition=definition, preferred_metric=preferred, candidates=metrics)


MEASUREMENTS = (
    # Agent system.
    vm("agent_access", "Whether a team has practical access to approved coding agents.", "enabled_agent_seats_fraction",
       m("enabled_agent_seats_fraction", Source.ORG_DATA, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Fraction of active engineers with working access to an approved coding agent.", ("team_members", "enabled_agent_accounts"), "enabled / active engineers")),
    vm("agent_capability", "Capability of the agent/model/toolchain for the team's task distribution.", None,
       m("task_benchmark_success_rate", Source.AGENT_TELEMETRY, Grain.TASK, Observability.PROXY, "fraction", "Success rate on a maintained representative task benchmark.", ("benchmark_task_id", "model", "tools", "success"), caveat="Capability is task-distribution specific; model name is not a sufficient measure.")),
    vm("agent_tool_access", "Breadth of executable tools available to coding agents.", "effective_tool_surface",
       m("effective_tool_surface", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.DERIVED, "count", "Distinct actionable tool classes available in-session.", ("session_id", "available_tools", "tool_permissions"), "count(distinct permitted tool classes)")),
    vm("agent_context_quality", "Completeness, relevance and freshness of context supplied to the agent.", None,
       m("context_retrieval_success", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.PROXY, "fraction", "Fraction of required task artefacts available before execution.", ("required_context_items", "retrieved_context_items", "context_age"), caveat="Requires a definition of required context per task."),
       m("clarification_rate", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.PROXY, "requests/session", "Agent requests for missing or ambiguous context.", ("session_id", "clarification_events"), "count(clarification_events)")),
    vm("agent_autonomy_policy", "Maximum independent action explicitly permitted by team/platform policy.", "permitted_action_level",
       m("permitted_action_level", Source.ORG_DATA, Grain.TEAM_WEEK, Observability.DERIVED, "ordinal", "Policy level from suggestion-only through edit/test/commit/PR/deploy permissions.", ("team_id", "allowed_actions", "approval_requirements"), caveat="Permission is not realised autonomy.")),
    vm("agent_usage_intensity", "Amount of agent use, separate from autonomy or task share.", "agent_active_minutes_per_engineer",
       m("agent_active_minutes_per_engineer", Source.AGENT_TELEMETRY, Grain.TEAM_WEEK, Observability.DERIVED, "minutes/engineer/week", "Active coding-agent session time normalised by engineering headcount.", ("session_id", "active_seconds", "team_id", "active_engineers"), "sum(active_seconds)/60/active_engineers")),
    vm("agent_autonomy", "Realised fraction of execution performed without human intervention.", "unassisted_execution_fraction",
       m("unassisted_execution_fraction", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.DERIVED, "fraction", "Share of material execution steps completed without human correction, approval or takeover.", ("execution_steps", "human_interventions", "approval_events", "takeover_events"), caveat="Must instrument interventions prospectively.")),
    vm("agentic_task_share", "Fraction of engineering tasks with material agent execution.", "material_agent_task_fraction",
       m("material_agent_task_fraction", Source.AGENT_TELEMETRY, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Completed tasks containing material agent execution.", ("task_id", "agent_session_id", "material_agent_work", "completed_at"), "agent-assisted completed tasks / completed tasks")),

    # Team characteristics.
    vm("domain_experience", "Accumulated experience with the product/domain and its operational constraints.", None,
       m("team_domain_tenure", Source.ORG_DATA, Grain.TEAM_WEEK, Observability.PROXY, "months", "Median months team members have worked in the relevant domain/system.", ("person_id", "team_id", "domain_start_date"), "median(months in domain)")),
    vm("software_delivery_skill", "Team capability at designing, reviewing, testing and delivering software changes.", "dora_capability_scale_score",
       m("dora_capability_scale_score", Source.SURVEY, Grain.TEAM_WEEK, Observability.PROXY, "score", "Score on DORA's psychometrically validated technical/process/cultural capability scales (continuous delivery, trunk-based development, loosely coupled architecture, monitoring, etc.).", ("team_id", "capability_survey_items"), caveat="A validated instrument, but still self-report of practice, not of outcomes; do not use DORA outcome metrics themselves as the capability measure, which would create circularity.")),
    vm("team_stability", "Continuity of team membership over time.", "membership_retention_90d",
       m("membership_retention_90d", Source.ORG_DATA, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Fraction of team membership retained across a 90-day window.", ("team_id", "person_id", "joined_at", "left_at"), "retained baseline members / baseline members")),
    vm("review_capacity", "Available human capacity to perform substantive change verification.", "available_review_hours",
       m("available_review_hours", Source.ORG_DATA, Grain.TEAM_WEEK, Observability.DERIVED, "hours/week", "Estimated reviewer capacity after other committed work.", ("reviewer_id", "team_id", "capacity_hours", "allocated_hours"), "sum(capacity_hours - allocated_nonreview_hours)", caveat="Calendar capacity is not effective review throughput; calibrate against observed review completions.")),

    # Codebase characteristics.
    vm("modularity", "Degree to which change can be localised behind stable component boundaries.", None,
       m("change_locality", Source.REPOSITORY, Grain.REPOSITORY_DAY, Observability.PROXY, "fraction", "Fraction of changes confined to one declared component/module.", ("pull_request_id", "changed_files", "component_map"), "single-component PRs / PRs")),
    vm("coupling", "Extent to which changes in one component require coordinated changes elsewhere.", "cross_component_change_rate",
       m("cross_component_change_rate", Source.REPOSITORY, Grain.REPOSITORY_DAY, Observability.DERIVED, "fraction", "Fraction of changes touching multiple independently owned components.", ("pull_request_id", "changed_files", "component_map", "ownership_map"), "multi-component PRs / PRs")),
    vm("documentation_quality", "Freshness and usefulness of code/system documentation for change work.", None,
       m("documentation_freshness", Source.REPOSITORY, Grain.REPOSITORY_DAY, Observability.PROXY, "days", "Age of documentation associated with recently changed components.", ("doc_paths", "component_map", "last_modified_at"), caveat="Freshness does not imply correctness or usefulness.")),
    vm("testability", "Ease with which behaviour can be exercised and asserted automatically.", None,
       m("isolated_testability", Source.CI, Grain.REPOSITORY_DAY, Observability.PROXY, "fraction", "Fraction of components with independently runnable automated tests.", ("component_map", "test_targets", "test_dependencies"), caveat="Needs component-level build/test metadata.")),

    # Hardening mechanisms.
    vm("test_feedback_coverage", "Behavioural surface protected by automated executable tests.", "changed_code_test_exposure",
       m("changed_code_test_exposure", Source.CI, Grain.PULL_REQUEST, Observability.DERIVED, "fraction", "Changed code exercised by required automated test suites.", ("changed_files", "coverage_map", "required_test_suites"), caveat="Line coverage is a proxy for behavioural protection; mutation/branch metrics may be stronger.")),
    vm("type_constraint_coverage", "Code surface checked by a static type system at required strictness.", "typed_surface_fraction",
       m("typed_surface_fraction", Source.STATIC_ANALYSIS, Grain.REPOSITORY_DAY, Observability.DERIVED, "fraction", "In-scope code subject to required type checking.", ("files_in_scope", "typed_files", "typecheck_config"), "typed in-scope files / in-scope files")),
    vm("static_analysis_coverage", "Code surface governed by required lint/security/static rules.", "static_rule_surface_fraction",
       m("static_rule_surface_fraction", Source.STATIC_ANALYSIS, Grain.REPOSITORY_DAY, Observability.DERIVED, "fraction", "In-scope code analysed by required static checks.", ("files_in_scope", "files_analyzed", "required_rules"), "analyzed / in-scope")),
    vm("architecture_constraint_coverage", "Architectural boundaries enforced by executable checks.", "enforced_boundary_fraction",
       m("enforced_boundary_fraction", Source.STATIC_ANALYSIS, Grain.REPOSITORY_DAY, Observability.DERIVED, "fraction", "Declared architecture boundaries with machine-enforced dependency rules.", ("declared_boundaries", "enforced_boundaries"), "enforced / declared")),
    vm("contract_test_coverage", "Cross-service/API contracts protected by automated compatibility tests.", "tested_contract_fraction",
       m("tested_contract_fraction", Source.CI, Grain.REPOSITORY_DAY, Observability.DERIVED, "fraction", "Published/consumed contracts covered by required automated compatibility checks.", ("known_contracts", "contract_tests", "required_checks"), "tested / known contracts")),
    vm("policy_automation_coverage", "Engineering/security/compliance policy enforced mechanically in the change path.", "automated_policy_fraction",
       m("automated_policy_fraction", Source.CI, Grain.REPOSITORY_DAY, Observability.DERIVED, "fraction", "Applicable policies with an executable required check.", ("applicable_policies", "automated_policy_checks"), "automated / applicable")),
    vm("automated_verification", "Effective amount of verification discharged automatically before human acceptance/deployment.", None,
       m("automated_rejection_fraction", Source.CI, Grain.TEAM_WEEK, Observability.PROXY, "fraction", "Candidate changes rejected by required machine checks before human approval.", ("pull_request_id", "required_check_results", "first_human_approval_at"), caveat="Detection frequency depends on defect injection rate; use alongside coverage/latency measures.")),

    # Platform mechanisms.
    vm("ci_feedback_latency", "Time from code/change submission to actionable automated feedback.", "p50_required_check_latency",
       m("p50_required_check_latency", Source.CI, Grain.TEAM_WEEK, Observability.DERIVED, "minutes", "Median time from CI trigger to completion of required checks.", ("triggered_at", "completed_at", "required"), "median(completed_at-triggered_at)")),
    vm("ci_reliability", "Probability CI produces a trustworthy result without infrastructure-induced retry/failure.", "non_flaky_ci_fraction",
       m("non_flaky_ci_fraction", Source.CI, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Required CI runs not failing for infrastructure/flaky reasons.", ("result", "failure_classification", "required"), "non-infra non-flaky completions / required runs")),
    vm("environment_provisioning_latency", "Time to obtain an environment suitable for verification or deployment.", "p50_environment_ready_time",
       m("p50_environment_ready_time", Source.PLATFORM, Grain.TEAM_WEEK, Observability.DERIVED, "minutes", "Median request-to-ready time for ephemeral/test environments.", ("environment_request_at", "environment_ready_at", "team_id"), "median(ready-request)")),
    vm("deployment_automation", "Degree to which production deployment and rollback can proceed without manual procedural work.", "fully_automated_deployment_fraction",
       m("fully_automated_deployment_fraction", Source.CD, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Production deployments completed without manual operational intervention.", ("deployment_id", "environment", "manual_intervention", "status"), "automated successful prod deployments / successful prod deployments")),
    vm("observability_quality", "Ability to detect, localise and diagnose production behaviour from telemetry.", None,
       m("diagnostic_signal_coverage", Source.PLATFORM, Grain.REPOSITORY_DAY, Observability.PROXY, "fraction", "Critical services with required logs/metrics/traces and ownership metadata.", ("critical_services", "logs_enabled", "metrics_enabled", "traces_enabled", "owner_defined"), caveat="Presence of telemetry does not prove diagnostic usefulness.")),

    # Flow and DORA-style outcomes.
    vm("implementation_capacity", "Rate at which intended work becomes reviewable candidate changes.", "reviewable_changes_per_engineer_week",
       m("reviewable_changes_per_engineer_week", Source.SCM, Grain.TEAM_WEEK, Observability.DERIVED, "changes/engineer/week", "PRs reaching ready-for-review, normalised by active engineers.", ("pull_request_id", "ready_for_review_at", "team_id", "active_engineers"), "count(reviewable PRs)/active_engineers")),
    vm("change_rate", "Arrival rate of candidate changes into the delivery system.", "reviewable_pr_arrival_rate",
       m("reviewable_pr_arrival_rate", Source.SCM, Grain.TEAM_WEEK, Observability.DIRECT, "PRs/week", "PRs becoming ready for review per team-week.", ("pull_request_id", "ready_for_review_at", "team_id"), "count(distinct PRs)")),
    vm("verification_demand", "Total verification work induced by candidate changes before acceptance.", None,
       m("required_check_work", Source.CI, Grain.PULL_REQUEST, Observability.DERIVED, "check-minutes", "Machine verification work triggered by a candidate change.", ("pull_request_id", "required_check", "started_at", "completed_at"), "sum(check duration)"),
       m("requested_review_count", Source.SCM, Grain.PULL_REQUEST, Observability.DERIVED, "reviews", "Requested human reviewers/checks for the change.", ("pull_request_id", "review_requested_at", "reviewer_id"), "count(distinct review requests)")),
    vm("human_verification_demand", "Substantive verification effort that remains for humans after automated checks.", "substantive_review_events",
       m("substantive_review_events", Source.SCM, Grain.PULL_REQUEST, Observability.DERIVED, "reviews", "Substantive human review submissions per change.", ("pull_request_id", "reviewer_id", "review_submitted_at", "substantive"), "count(substantive reviews)")),
    vm("verification_latency", "Elapsed time consumed waiting for automated verification feedback.", "required_check_wall_time",
       m("required_check_wall_time", Source.CI, Grain.PULL_REQUEST, Observability.DERIVED, "minutes", "Time from first required CI trigger until all required machine checks complete.", ("pull_request_id", "triggered_at", "completed_at", "required"), "max(required completed_at)-min(required triggered_at)")),
    vm("human_verification_queue", "Backlog/waiting created because human verification demand exceeds available service capacity.", "review_queue_wait",
       m("review_queue_wait", Source.SCM, Grain.PULL_REQUEST, Observability.DERIVED, "hours", "Time from review request to first substantive review start/submission.", ("review_requested_at", "review_started_at", "review_submitted_at"), "first_review_start - review_requested_at", caveat="Need review-start instrumentation for clean service/queue decomposition.")),
    vm("wip", "Started engineering changes not yet delivered or abandoned.", "open_change_wip",
       m("open_change_wip", Source.SCM, Grain.TEAM_WEEK, Observability.DERIVED, "changes", "Concurrent open non-draft changes attributable to the team.", ("opened_at", "merged_at", "closed_at", "is_draft", "team_id"), "time-weighted count of open changes")),
    vm("batch_size", "Size and organisational surface area of an independently delivered change.", None,
       m("diff_size", Source.SCM, Grain.PULL_REQUEST, Observability.DIRECT, "changed lines", "Additions plus deletions in a change.", ("additions", "deletions"), "additions + deletions"),
       m("component_surface", Source.REPOSITORY, Grain.PULL_REQUEST, Observability.DERIVED, "components", "Distinct declared components touched by the change.", ("changed_files", "component_map"), "count(distinct components)")),
    vm("small_batch_discipline", "Practice of intentionally slicing work into independently testable/deployable increments.", None,
       m("large_change_fraction", Source.SCM, Grain.TEAM_WEEK, Observability.PROXY, "fraction", "Fraction of changes above a predeclared size/surface threshold.", ("pull_request_id", "additions", "deletions", "changed_files"), caveat="Outcome-based proxy; threshold must be fixed before analysis and contextualised by language/repo.")),
    vm("lead_time", "Elapsed time from change initiation to successful production delivery.", "change_lead_time",
       m("change_lead_time", Source.CD, Grain.DEPLOYMENT, Observability.DERIVED, "hours", "Time from first commit associated with a deployed change to successful production deployment.", ("commit_sha", "first_commit_at", "deployment_id", "deployed_at", "environment", "status"), "deployed_at-first_commit_at")),
    vm("deployment_frequency", "Frequency of successful production deployments.", "successful_prod_deployments",
       m("successful_prod_deployments", Source.CD, Grain.TEAM_WEEK, Observability.DIRECT, "deployments/week", "Successful production deployments per team-week.", ("deployment_id", "team_id", "environment", "status", "deployed_at"), "count(successful production deployments)")),
    vm("change_failure_rate", "Fraction of production changes causing service degradation requiring remediation.", "failed_change_fraction",
       m("failed_change_fraction", Source.INCIDENT_MANAGEMENT, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Production deployments linked to rollback, hotfix or qualifying incident.", ("deployment_id", "rollback_of_deployment_id", "incident_id", "attributable_deployment_ids"), "failed deployments / production deployments")),
    vm("recovery_time", "Time to restore service after a failed production change.", "failed_deployment_recovery_time",
       m("failed_deployment_recovery_time", Source.INCIDENT_MANAGEMENT, Grain.INCIDENT, Observability.DERIVED, "minutes", "Time from qualifying failed-deployment impact to restored service.", ("incident_id", "started_at", "resolved_at", "attributable_deployment_ids"), "resolved_at-started_at")),
    vm("deployment_rework_rate", "Fraction of deployment activity spent correcting recent failed changes.", "corrective_deployment_fraction",
       m("corrective_deployment_fraction", Source.CD, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Rollbacks/hotfix/recovery deployments as a fraction of production deployment activity.", ("deployment_id", "deployment_type", "rollback_of_deployment_id", "deployed_at"), "corrective deployments / production deployments")),
)


def measurement_for(variable: str) -> VariableMeasurement:
    matches = [measurement for measurement in MEASUREMENTS if measurement.variable == variable]
    assert len(matches) == 1, variable
    return matches[0]

# Finer-grained constructs introduced by the literature pass. These intentionally coexist with
# legacy measurement definitions that are no longer graph nodes; keeping those definitions makes
# migration explicit and preserves a record of how the model was decomposed.
EXTRA_MEASUREMENTS = (
    vm("agent_interface_quality", "How effectively the agent-computer interface exposes repository navigation, editing, execution and actionable feedback.", "aci_task_success_delta",
       m("aci_task_success_delta", Source.AGENT_TELEMETRY, Grain.TASK, Observability.DERIVED, "percentage points", "Difference in task success between the deployed interface and a controlled baseline interface on representative tasks.", ("task_id", "interface_variant", "success"), "success_rate(deployed) - success_rate(baseline)", caveat="Requires periodic interface ablations or benchmark replay.")),
    vm("agent_task_success", "Probability that an agent successfully completes the delegated task or material execution step to acceptance criteria.", "accepted_agent_task_fraction",
       m("accepted_agent_task_fraction", Source.AGENT_TELEMETRY, Grain.TASK, Observability.DERIVED, "fraction", "Material agent tasks meeting explicit acceptance criteria without human takeover.", ("task_id", "agent_session_id", "acceptance_result", "takeover_events"), "accepted without takeover / attempted material agent tasks")),
    vm("agent_context_relevance", "Fraction of supplied agent context that is pertinent to the task and required decision surface.", None,
       m("required_context_recall", Source.AGENT_TELEMETRY, Grain.TASK, Observability.PROXY, "fraction", "Known task-required artefacts present in supplied/retrieved context.", ("required_context_items", "retrieved_context_items"), "required items retrieved / required items", caveat="Requires a task-level gold or reviewed required-context set.")),
    vm("agent_context_freshness", "Age and state-consistency of context relative to the repository/task at execution time.", "stale_context_fraction",
       m("stale_context_fraction", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.DERIVED, "fraction", "Supplied context artefacts older than the repository state or declared freshness SLO.", ("context_item_id", "context_version", "repository_revision", "context_updated_at", "session_started_at"), "stale context items / context items")),
    vm("agent_context_volume", "Amount of contextual material supplied to the agent independent of its relevance.", "context_tokens",
       m("context_tokens", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.DIRECT, "tokens", "Input tokens attributable to repository/task context excluding fixed system instructions.", ("session_id", "context_token_count"))),
    vm("realised_agent_autonomy", "Fraction of material execution performed without human correction, approval or takeover.", "unassisted_execution_fraction",
       m("unassisted_execution_fraction", Source.AGENT_TELEMETRY, Grain.AGENT_SESSION, Observability.DERIVED, "fraction", "Share of material execution steps completed without human correction, approval or takeover.", ("execution_steps", "human_interventions", "approval_events", "takeover_events"), "unassisted material steps / material steps", caveat="Must instrument intervention events prospectively.")),
    vm("task_familiarity", "How familiar the responsible engineer/team is with the repository area, domain and task pattern before work begins.", None,
       m("prior_area_contribution_share", Source.REPOSITORY, Grain.TASK, Observability.PROXY, "fraction", "Share of recent commits in the task's affected area authored/reviewed by the responsible engineer/team.", ("task_id", "predicted_component_scope", "commit_authors", "reviewers", "lookback_window"), caveat="Use only pre-treatment history; affected area must be defined without peeking at final change.")),
    vm("task_complexity", "Intrinsic cognitive/technical complexity of the requested change, separate from implementation outcome.", None,
       m("prework_complexity_assessment", Source.ISSUE_TRACKER, Grain.TASK, Observability.PROXY, "score", "Pre-work complexity rating based on dependencies, ambiguity, required behaviours and systems involved.", ("task_id", "complexity_dimensions", "assessed_at"), caveat="Must be captured before implementation to avoid post-treatment bias.")),
    vm("task_scope", "Breadth of systems/components plausibly implicated by the task before implementation begins.", "declared_component_scope",
       m("declared_component_scope", Source.ISSUE_TRACKER, Grain.TASK, Observability.PROXY, "components", "Count of components/services declared or predicted as in-scope before work starts.", ("task_id", "declared_components", "created_at"), "count(declared components)")),
    vm("human_implementation_efficiency", "Human capability to convert understood requirements into correct candidate changes per unit effort.", None,
       m("historical_similar_task_efficiency", Source.ISSUE_TRACKER, Grain.TEAM_WEEK, Observability.PROXY, "completed tasks/hour", "Pre-period completion efficiency on comparable non-agent tasks.", ("task_class", "completed_at", "active_work_minutes", "team_id"), caveat="Should be estimated from a pre-treatment window and matched task classes.")),
    vm("agent_value", "Task-conditional causal contribution of agent involvement to implementation effort; conceptually heterogeneous rather than a fixed scalar.", None,
       m("paired_task_speedup", Source.AGENT_TELEMETRY, Grain.TASK, Observability.LATENT, "fraction", "Counterfactual speedup/slowdown from agent access for comparable tasks.", ("task_id", "agent_allowed", "completion_time", "task_covariates"), caveat="Not directly observable for a single task; requires experimental or causal estimation later.")),
    vm("implementation_effort", "Active human-equivalent effort required to produce a reviewable candidate change.", "active_implementation_minutes",
       m("active_implementation_minutes", Source.AGENT_TELEMETRY, Grain.TASK, Observability.DERIVED, "minutes", "Active human implementation/steering time plus explicitly costed autonomous agent execution where desired.", ("task_id", "human_active_seconds", "agent_active_seconds", "costing_policy"), "human active seconds / 60", caveat="Keep human time and agent compute as separate raw measures even if a combined cost is later derived.")),
    vm("change_diffusion", "Breadth of a logical change across files, modules, components, services and ownership boundaries.", "component_diffusion",
       m("component_diffusion", Source.REPOSITORY, Grain.PULL_REQUEST, Observability.DERIVED, "components", "Distinct declared components touched by the change.", ("pull_request_id", "changed_files", "component_map"), "count(distinct components)"),
       m("ownership_diffusion", Source.REPOSITORY, Grain.PULL_REQUEST, Observability.DERIVED, "owners", "Distinct code-owner groups touched by the change.", ("changed_files", "ownership_map"), "count(distinct owners)")),
    vm("review_service_time", "Active reviewer time required to substantively evaluate a change, excluding queue waiting.", "active_review_minutes",
       m("active_review_minutes", Source.SCM, Grain.PULL_REQUEST, Observability.DERIVED, "minutes", "Elapsed active review intervals summed across substantive reviewers.", ("review_started_at", "review_paused_at", "review_submitted_at", "reviewer_id"), "sum(active review intervals)", caveat="Requires explicit review-start/activity instrumentation; submission latency alone confounds queue and service time.")),
    vm("ci_execution_latency", "Wall-clock runtime of required CI checks after execution begins.", "p50_required_check_execution",
       m("p50_required_check_execution", Source.CI, Grain.TEAM_WEEK, Observability.DERIVED, "minutes", "Median started-to-completed duration of required checks.", ("started_at", "completed_at", "required", "team_id"), "median(completed_at-started_at)")),
    vm("ci_queue_latency", "Waiting time between CI trigger and actual execution start.", "p50_required_check_queue",
       m("p50_required_check_queue", Source.CI, Grain.TEAM_WEEK, Observability.DERIVED, "minutes", "Median trigger-to-start waiting time for required checks.", ("triggered_at", "started_at", "required", "team_id"), "median(started_at-triggered_at)")),
    vm("ci_flakiness", "Probability that required CI emits a failure not caused by the candidate change.", "flaky_required_check_fraction",
       m("flaky_required_check_fraction", Source.CI, Grain.TEAM_WEEK, Observability.DERIVED, "fraction", "Required checks classified flaky/infrastructure after retry or triage.", ("run_id", "required", "result", "retry_result", "failure_classification"), "flaky required runs / required runs")),
    vm("ci_diagnostic_quality", "How actionable CI failure output is for locating cause and choosing the next action.", None,
       m("failure_to_fix_navigation_rate", Source.CI, Grain.PULL_REQUEST, Observability.PROXY, "fraction", "Failures resolved without exploratory reruns or human clarification after first diagnostic output.", ("run_id", "failure_classification", "rerun_count", "clarification_events", "fixed_at"), caveat="A proxy until diagnostic quality can be evaluated against labeled failure cases.")),
    vm("premerge_defect_detection", "Defects in candidate changes detected before merge/deployment by automated or human verification.", "premerge_defects_per_change",
       m("premerge_defects_per_change", Source.SCM, Grain.PULL_REQUEST, Observability.DERIVED, "defects/change", "Distinct correctness defects detected and corrected before merge.", ("pull_request_id", "defect_id", "detected_by", "detected_at", "fixed_at"), "count(distinct premerge defects)")),
    vm("escaped_defects", "Defects attributable to a change that are first detected after production exposure.", "escaped_defects_per_deployment",
       m("escaped_defects_per_deployment", Source.INCIDENT_MANAGEMENT, Grain.DEPLOYMENT, Observability.DERIVED, "defects/deployment", "Production defects first detected after deployment and attributed to the change.", ("deployment_id", "defect_id", "detected_at", "attributable_deployment_ids"), "count(attributed escaped defects)")),
    vm("experiment_frequency", "Rate at which product hypotheses are exposed to real customer behaviour with a measurable outcome.", "completed_product_experiments",
       m("completed_product_experiments", Source.PRODUCT_ANALYTICS, Grain.PRODUCT_WEEK, Observability.DIRECT, "experiments/week", "Completed production experiments with a predeclared hypothesis and measured result.", ("experiment_id", "started_at", "completed_at", "hypothesis", "result"), "count(completed experiments)")),
    vm("time_to_customer_value", "Elapsed time from a committed product decision or validated opportunity to customer-accessible value.", "decision_to_value_hours",
       m("decision_to_value_hours", Source.PRODUCT_ANALYTICS, Grain.TASK, Observability.DERIVED, "hours", "Time from explicit product commitment to first customer-accessible production exposure.", ("decision_id", "committed_at", "deployment_id", "customer_available_at"), "customer_available_at-committed_at")),
    vm("product_reliability", "Reliability experienced by customers in the product surface affected by software delivery.", "customer_impact_free_session_fraction",
       m("customer_impact_free_session_fraction", Source.PRODUCT_ANALYTICS, Grain.PRODUCT_WEEK, Observability.DERIVED, "fraction", "Fraction of customer sessions without qualifying availability or correctness impact.", ("session_id", "service_errors", "availability_impact", "correctness_impact"), "unimpacted sessions / sessions")),
    vm("product_learning_rate", "Rate at which product uncertainty is reduced through valid customer evidence.", None,
       m("validated_hypotheses_per_week", Source.PRODUCT_ANALYTICS, Grain.PRODUCT_WEEK, Observability.PROXY, "hypotheses/week", "Product hypotheses resolved with sufficient evidence to change or confirm a decision.", ("hypothesis_id", "decision", "evidence_threshold", "resolved_at"), "count(resolved hypotheses)", caveat="A proxy: quantity of resolved hypotheses does not capture importance of learning.")),
    vm("customer_value", "Value customers realise from the product, distinct from engineering output.", None,
       m("core_outcome_success_rate", Source.PRODUCT_ANALYTICS, Grain.PRODUCT_WEEK, Observability.PROXY, "fraction", "Success rate for a product-specific core customer outcome.", ("customer_id", "core_outcome_event", "success"), caveat="Must be defined per product; there is no universal customer-value metric.")),
    vm("customer_adoption", "Extent to which target customers begin meaningful use of the product.", "activated_customers",
       m("activated_customers", Source.PRODUCT_ANALYTICS, Grain.BUSINESS_MONTH, Observability.DERIVED, "customers/month", "Customers reaching a predeclared activation threshold in the period.", ("customer_id", "activation_event", "occurred_at"), "count(distinct activated customers)")),
    vm("customer_retention", "Extent to which customers continue meaningful use or commercial relationship over time.", "retained_customer_fraction",
       m("retained_customer_fraction", Source.PRODUCT_ANALYTICS, Grain.BUSINESS_MONTH, Observability.DERIVED, "fraction", "Eligible customers retained across a declared period.", ("customer_id", "eligible_at", "retained_at"), "retained / eligible")),
    vm("revenue", "Recognised commercial revenue attributable to the product or business scope being modelled.", "recognised_revenue",
       m("recognised_revenue", Source.FINANCE, Grain.BUSINESS_MONTH, Observability.DIRECT, "currency/month", "Recognised revenue for the modelled product/business scope.", ("period", "product_id", "recognised_revenue"))),
    vm("engineering_cost", "Engineering labour, agent-compute and directly attributable tooling cost consumed by software delivery.", "engineering_delivery_cost",
       m("engineering_delivery_cost", Source.FINANCE, Grain.BUSINESS_MONTH, Observability.DERIVED, "currency/month", "Direct engineering labour plus attributable agent/model/tooling cost.", ("engineering_labour_cost", "agent_compute_cost", "tooling_cost", "period"), "sum(direct engineering delivery costs)")),
    vm("cost_to_serve", "Variable operational and support cost required to keep the product usable for customers.", "service_cost",
       m("service_cost", Source.FINANCE, Grain.BUSINESS_MONTH, Observability.DERIVED, "currency/month", "Infrastructure, support and incident-response cost attributable to serving customers.", ("infrastructure_cost", "support_cost", "incident_cost", "period"), "sum(variable service costs)")),
    vm("gross_margin", "Revenue remaining after costs included in the modelled cost-of-service boundary.", "gross_margin_fraction",
       m("gross_margin_fraction", Source.FINANCE, Grain.BUSINESS_MONTH, Observability.DERIVED, "fraction", "Revenue less modelled direct costs, divided by revenue.", ("recognised_revenue", "engineering_delivery_cost", "service_cost"), "(revenue-costs)/revenue", caveat="Cost boundary must be declared before analysis.")),
    vm("commercial_success", "Business success target for the causal workbench; intentionally multi-dimensional rather than a single universal KPI.", None,
       m("commercial_success_index", Source.FINANCE, Grain.BUSINESS_MONTH, Observability.LATENT, "index", "Decision-specific composite or utility over revenue, margin, retention and other declared business objectives.", ("recognised_revenue", "gross_margin_fraction", "retained_customer_fraction", "objective_weights"), caveat="Keep component outcomes separate for estimation; this node is a decision target, not a canonical metric.")),

)

MEASUREMENTS = MEASUREMENTS + EXTRA_MEASUREMENTS
