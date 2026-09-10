"""Deterministic fake-data generators for exercising the persistence and (eventually)
estimation pipeline end to end -- not a source of real observations.

Mirrors the spirit of DevLake's own backend/python/test/fakeplugin: small,
deterministic, seeded generation (index-cycled states, no Faker dependency),
kept in an isolated module so it's obvious this is dev/test fixture data, not
something that could be mistaken for a real ingestion connector. Every
variable in the causal graph gets fixture coverage, not just the
DevLake-observable subset -- this exists to smoke-test the whole pipeline
(persistence, aggregation, estimation) before real connectors for the
agent/org/product/finance layers exist.

Referentially consistent: a fixed cast of teams, repos, components, people,
and customers recur across every generator so downstream joins (PR ->
component -> team, deployment -> commit -> PR, incident -> deployment) behave
like real data would, rather than being independently random per table.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from causal_coding.commercial_events import (
    CustomerActivation,
    CustomerOutcomeEvent,
    CustomerRetentionSnapshot,
    CustomerSession,
    EngineeringCostRecord,
    FinanceRecord,
    ProductDecision,
    ProductExperiment,
    ProductHypothesis,
    ServiceCostRecord,
)
from causal_coding.events import (
    AgentBenchmarkResult,
    AgentPolicySnapshot,
    AgentSession,
    CIRun,
    ComponentDefinition,
    ComponentOwnership,
    Deployment,
    EnvironmentProvision,
    Incident,
    PullRequest,
    RepositorySnapshot,
    ReviewEvent,
    ServiceObservabilitySnapshot,
    TeamMembership,
    WorkItem,
    ingest_event,
)
from causal_coding.survey_events import SurveyResponse

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

TEAMS = ("team-checkout", "team-platform")
REPOS = {"team-checkout": "repo-checkout", "team-platform": "repo-platform"}
COMPONENTS = {
    "repo-checkout": ("checkout-api", "checkout-ui"),
    "repo-platform": ("platform-core",),
}
PEOPLE = {
    "team-checkout": ("p-checkout-1", "p-checkout-2", "p-checkout-3"),
    "team-platform": ("p-platform-1", "p-platform-2"),
}
CUSTOMERS = tuple(f"cust-{i}" for i in range(1, 9))
SOURCE = "fixtures"


def _at(days: float, hours: float = 0) -> datetime:
    return EPOCH + timedelta(days=days, hours=hours)


def generate_component_definitions() -> list[ComponentDefinition]:
    out = []
    for repo_id, names in COMPONENTS.items():
        for name in names:
            out.append(
                ingest_event(
                    ComponentDefinition,
                    observed_at=EPOCH,
                    source_system=SOURCE,
                    repository_id=repo_id,
                    component_name=name,
                    path_patterns=[f"src/{name}/**"],
                    version="v1",
                )
            )
    return out


def generate_component_ownerships() -> list[ComponentOwnership]:
    out = []
    for team_id, repo_id in REPOS.items():
        for name in COMPONENTS[repo_id]:
            out.append(
                ingest_event(
                    ComponentOwnership,
                    observed_at=EPOCH,
                    source_system=SOURCE,
                    repository_id=repo_id,
                    component_name=name,
                    owner_team_id=team_id,
                    effective_from=EPOCH,
                )
            )
    return out


def generate_team_memberships() -> list[TeamMembership]:
    out = []
    for team_id, people in PEOPLE.items():
        for i, person_id in enumerate(people):
            out.append(
                ingest_event(
                    TeamMembership,
                    observed_at=EPOCH,
                    source_system=SOURCE,
                    team_id=team_id,
                    person_id=person_id,
                    joined_at=_at(-365 + i * 30),
                    domain_start_date=_at(-365 + i * 30),
                    capacity_hours=32.0,
                    allocated_nonreview_hours=24.0,
                )
            )
    return out


def generate_pull_requests(rng: random.Random, count: int = 40) -> list[PullRequest]:
    out = []
    states = ("merged", "merged", "merged", "closed")
    for i in range(count):
        team_id = TEAMS[i % len(TEAMS)]
        repo_id = REPOS[team_id]
        component = COMPONENTS[repo_id][i % len(COMPONENTS[repo_id])]
        opened = _at(i * 0.6)
        merged = opened + timedelta(hours=4 + (i % 20))
        out.append(
            ingest_event(
                PullRequest,
                observed_at=opened,
                source_system=SOURCE,
                pull_request_id=f"pr-{i}",
                repository_id=repo_id,
                team_id=team_id,
                opened_at=opened,
                ready_for_review_at=opened + timedelta(hours=1),
                merged_at=merged if states[i % len(states)] == "merged" else None,
                closed_at=merged,
                is_draft=False,
                additions=rng.randint(5, 200),
                deletions=rng.randint(0, 80),
                changed_files=[f"src/{component}/file_{i % 7}.py"],
                first_commit_at=opened - timedelta(hours=2),
                commit_shas=[f"sha-pr-{i}"],
                merge_commit_sha=f"sha-pr-{i}" if states[i % len(states)] == "merged" else None,
            )
        )
    return out


def generate_review_events(pull_requests: list[PullRequest], rng: random.Random) -> list[ReviewEvent]:
    out = []
    for pr in pull_requests:
        reviewer_pool = PEOPLE[pr.team_id]
        reviewer = reviewer_pool[rng.randrange(len(reviewer_pool))]
        submitted = pr.opened_at + timedelta(hours=rng.randint(1, 10))
        out.append(
            ingest_event(
                ReviewEvent,
                observed_at=submitted,
                source_system=SOURCE,
                pull_request_id=pr.pull_request_id,
                reviewer_id=reviewer,
                review_requested_at=pr.opened_at,
                review_started_at=submitted - timedelta(minutes=30),
                review_submitted_at=submitted,
                state="approved",
                substantive=True,
            )
        )
    return out


def generate_ci_runs(pull_requests: list[PullRequest], rng: random.Random) -> list[CIRun]:
    out = []
    results = ("success", "success", "success", "failure")
    for pr in pull_requests:
        for j, category in enumerate(("unit", "integration")):
            triggered = pr.opened_at + timedelta(minutes=10 + j * 5)
            result = results[rng.randrange(len(results))]
            out.append(
                ingest_event(
                    CIRun,
                    observed_at=triggered,
                    source_system=SOURCE,
                    ci_run_id=f"ci-{pr.pull_request_id}-{category}",
                    pull_request_id=pr.pull_request_id,
                    commit_sha=f"sha-{pr.pull_request_id}",
                    check_category=category,
                    required=True,
                    triggered_at=triggered,
                    started_at=triggered + timedelta(seconds=30),
                    completed_at=triggered + timedelta(minutes=rng.randint(2, 15)),
                    result=result,
                    failure_classification=None if result == "success" else "test_failure",
                )
            )
    return out


def generate_deployments(pull_requests: list[PullRequest], rng: random.Random) -> list[Deployment]:
    out = []
    results = ("SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "FAILURE")
    for i, pr in enumerate(pr for pr in pull_requests if pr.merged_at is not None):
        deployed_at = pr.merged_at + timedelta(hours=1)
        out.append(
            ingest_event(
                Deployment,
                observed_at=deployed_at,
                source_system=SOURCE,
                deployment_id=f"deploy-{pr.pull_request_id}",
                team_id=pr.team_id,
                environment="production",
                status=results[i % len(results)],
                deployed_at=deployed_at,
                commit_shas=[f"sha-{pr.pull_request_id}"],
                manual_intervention=False,
                deployment_type="standard",
                rollback_of_deployment_id=None,
            )
        )
    return out


def generate_incidents(deployments: list[Deployment], rng: random.Random) -> list[Incident]:
    out = []
    for deployment in deployments:
        if deployment.status != "FAILURE":
            continue
        started = deployment.deployed_at + timedelta(minutes=15)
        out.append(
            ingest_event(
                Incident,
                observed_at=started,
                source_system=SOURCE,
                incident_id=f"incident-{deployment.deployment_id}",
                started_at=started,
                resolved_at=started + timedelta(minutes=rng.randint(20, 240)),
                severity="SEV2",
                attributable_deployment_ids=[deployment.deployment_id],
            )
        )
    return out


def generate_work_items(rng: random.Random, count: int = 30) -> list[WorkItem]:
    out = []
    statuses = ("todo", "in_progress", "in_review", "done")
    for i in range(count):
        team_id = TEAMS[i % len(TEAMS)]
        for step, status in enumerate(statuses[: rng.randint(2, 4)]):
            out.append(
                ingest_event(
                    WorkItem,
                    observed_at=_at(i * 0.7 + step),
                    source_system=SOURCE,
                    work_item_id=f"work-{i}",
                    team_id=team_id,
                    status=status,
                    status_changed_at=_at(i * 0.7 + step),
                )
            )
    return out


def generate_repository_snapshots() -> list[RepositorySnapshot]:
    out = []
    for repo_id in REPOS.values():
        out.append(
            ingest_event(
                RepositorySnapshot,
                observed_at=EPOCH,
                source_system=SOURCE,
                repository_id=repo_id,
                files_in_scope=120,
                typed_files=90,
                files_analyzed=110,
                required_checks=["lint", "typecheck"],
                required_rules=["no-unused-vars"],
                declared_boundaries=["api->db"],
                enforced_boundaries=["api->db"],
                known_contracts=["checkout-api-v1"],
                tested_contracts=["checkout-api-v1"],
                applicable_policies=["security-review"],
                automated_policy_checks=["security-review"],
                component_map_version="v1",
                documentation_paths=[f"docs/{repo_id}.md"],
                test_targets=["unit", "integration"],
            )
        )
    return out


def generate_environment_provisions(rng: random.Random, count: int = 15) -> list[EnvironmentProvision]:
    out = []
    for i in range(count):
        team_id = TEAMS[i % len(TEAMS)]
        requested = _at(i * 1.3)
        out.append(
            ingest_event(
                EnvironmentProvision,
                observed_at=requested,
                source_system=SOURCE,
                environment_id=f"env-{i}",
                team_id=team_id,
                requested_at=requested,
                ready_at=requested + timedelta(minutes=rng.randint(2, 30)),
                environment_type="ephemeral",
            )
        )
    return out


def generate_service_observability_snapshots() -> list[ServiceObservabilitySnapshot]:
    out = []
    for repo_id in REPOS.values():
        out.append(
            ingest_event(
                ServiceObservabilitySnapshot,
                observed_at=EPOCH,
                source_system=SOURCE,
                service_id=f"svc-{repo_id}",
                repository_id=repo_id,
                critical=True,
                logs_enabled=True,
                metrics_enabled=True,
                traces_enabled=False,
                owner_defined=True,
            )
        )
    return out


def generate_agent_policy_snapshots() -> list[AgentPolicySnapshot]:
    return [
        ingest_event(
            AgentPolicySnapshot,
            observed_at=EPOCH,
            source_system=SOURCE,
            team_id=team_id,
            allowed_actions=["edit", "test", "commit"],
            approval_requirements=["human_approval_before_merge"],
        )
        for team_id in TEAMS
    ]


def generate_agent_benchmark_results(rng: random.Random, count: int = 20) -> list[AgentBenchmarkResult]:
    out = []
    for i in range(count):
        out.append(
            ingest_event(
                AgentBenchmarkResult,
                observed_at=_at(i * 2),
                source_system=SOURCE,
                benchmark_task_id=f"bench-{i}",
                model="fixture-model-v1",
                tools=["search", "edit", "run_tests"],
                success=rng.random() < 0.7,
                task_family="bugfix" if i % 2 == 0 else "feature",
            )
        )
    return out


def generate_agent_sessions(pull_requests: list[PullRequest], rng: random.Random) -> list[AgentSession]:
    out = []
    for pr in pull_requests:
        person = PEOPLE[pr.team_id][0]
        out.append(
            ingest_event(
                AgentSession,
                observed_at=pr.opened_at - timedelta(hours=1),
                source_system=SOURCE,
                session_id=f"session-{pr.pull_request_id}",
                team_id=pr.team_id,
                person_id=person,
                task_id=f"task-{pr.pull_request_id}",
                pull_request_id=pr.pull_request_id,
                model="fixture-model-v1",
                active_seconds=rng.randint(300, 3600),
                available_tools=["search", "edit", "run_tests"],
                tool_permissions=["edit", "run_tests"],
                tool_calls=rng.randint(3, 40),
                execution_steps=rng.randint(3, 40),
                human_messages=rng.randint(0, 5),
                human_interventions=rng.randint(0, 3),
                approval_events=1,
                takeover_events=0,
                clarification_events=rng.randint(0, 2),
                required_context_items=["readme", "component_map"],
                retrieved_context_items=["readme", "component_map"],
                context_age_seconds=[60, 3600],
                material_agent_work=True,
                agent_edit_bytes=rng.randint(100, 5000),
                total_edit_bytes=rng.randint(100, 6000),
                session_outcome="completed",
            )
        )
    return out


def generate_survey_responses() -> list[SurveyResponse]:
    return [
        ingest_event(
            SurveyResponse,
            observed_at=EPOCH,
            source_system=SOURCE,
            respondent_id=PEOPLE[team_id][0],
            team_id=team_id,
            instrument="dora_capability_scale",
            instrument_version="2025",
            items={"continuous_delivery": 3.8, "trunk_based_development": 4.1, "loosely_coupled_architecture": 3.5},
            composite_score=3.8,
        )
        for team_id in TEAMS
    ]


def generate_product_experiments(rng: random.Random, count: int = 10) -> list[ProductExperiment]:
    out = []
    for i in range(count):
        started = _at(i * 3)
        out.append(
            ingest_event(
                ProductExperiment,
                observed_at=started,
                source_system=SOURCE,
                experiment_id=f"exp-{i}",
                started_at=started,
                completed_at=started + timedelta(days=rng.randint(3, 10)),
                hypothesis=f"change {i} improves checkout conversion",
                result="supported" if rng.random() < 0.4 else "not_supported",
            )
        )
    return out


def generate_product_decisions(deployments: list[Deployment], rng: random.Random) -> list[ProductDecision]:
    out = []
    for i, deployment in enumerate(deployments):
        committed = deployment.deployed_at - timedelta(days=rng.randint(1, 5))
        out.append(
            ingest_event(
                ProductDecision,
                observed_at=committed,
                source_system=SOURCE,
                decision_id=f"decision-{i}",
                committed_at=committed,
                deployment_id=deployment.deployment_id,
                customer_available_at=deployment.deployed_at,
            )
        )
    return out


def generate_customer_sessions(rng: random.Random, count: int = 60) -> list[CustomerSession]:
    out = []
    for i in range(count):
        out.append(
            ingest_event(
                CustomerSession,
                observed_at=_at(i * 0.4),
                source_system=SOURCE,
                session_id=f"custsess-{i}",
                service_errors=0 if rng.random() < 0.9 else rng.randint(1, 3),
                availability_impact=rng.random() < 0.03,
                correctness_impact=rng.random() < 0.03,
            )
        )
    return out


def generate_product_hypotheses(rng: random.Random, count: int = 8) -> list[ProductHypothesis]:
    out = []
    for i in range(count):
        out.append(
            ingest_event(
                ProductHypothesis,
                observed_at=_at(i * 4),
                source_system=SOURCE,
                hypothesis_id=f"hyp-{i}",
                decision="ship" if rng.random() < 0.5 else "hold",
                evidence_threshold="p<0.05",
                resolved_at=_at(i * 4 + 3),
            )
        )
    return out


def generate_customer_outcome_events(rng: random.Random) -> list[CustomerOutcomeEvent]:
    return [
        ingest_event(
            CustomerOutcomeEvent,
            observed_at=_at(i * 1.1),
            source_system=SOURCE,
            customer_id=customer_id,
            core_outcome_event="checkout_completed",
            success=rng.random() < 0.85,
        )
        for i, customer_id in enumerate(CUSTOMERS)
    ]


def generate_customer_activations(rng: random.Random) -> list[CustomerActivation]:
    return [
        ingest_event(
            CustomerActivation,
            observed_at=_at(i * 5),
            source_system=SOURCE,
            customer_id=customer_id,
            activation_event="first_purchase",
            occurred_at=_at(i * 5),
        )
        for i, customer_id in enumerate(CUSTOMERS)
    ]


def generate_customer_retention_snapshots(rng: random.Random) -> list[CustomerRetentionSnapshot]:
    out = []
    for i, customer_id in enumerate(CUSTOMERS):
        eligible = _at(i * 5 + 30)
        out.append(
            ingest_event(
                CustomerRetentionSnapshot,
                observed_at=eligible,
                source_system=SOURCE,
                customer_id=customer_id,
                eligible_at=eligible,
                retained_at=eligible + timedelta(days=5) if rng.random() < 0.7 else None,
            )
        )
    return out


def generate_finance_records(count: int = 6) -> list[FinanceRecord]:
    return [
        ingest_event(
            FinanceRecord,
            observed_at=_at(i * 30),
            source_system=SOURCE,
            period=f"2026-{i + 1:02d}",
            product_id="checkout",
            recognised_revenue=50_000.0 + i * 4_000,
        )
        for i in range(count)
    ]


def generate_engineering_cost_records(count: int = 6) -> list[EngineeringCostRecord]:
    return [
        ingest_event(
            EngineeringCostRecord,
            observed_at=_at(i * 30),
            source_system=SOURCE,
            period=f"2026-{i + 1:02d}",
            engineering_labour_cost=20_000.0,
            agent_compute_cost=800.0 + i * 50,
            tooling_cost=500.0,
        )
        for i in range(count)
    ]


def generate_service_cost_records(count: int = 6) -> list[ServiceCostRecord]:
    return [
        ingest_event(
            ServiceCostRecord,
            observed_at=_at(i * 30),
            source_system=SOURCE,
            period=f"2026-{i + 1:02d}",
            infrastructure_cost=3_000.0,
            support_cost=1_200.0,
            incident_cost=200.0 * (i % 3),
        )
        for i in range(count)
    ]


def generate_all(seed: int = 0) -> dict[str, list]:
    """Generate one referentially-consistent fixture dataset, keyed by table name."""
    rng = random.Random(seed)

    pull_requests = generate_pull_requests(rng)
    deployments = generate_deployments(pull_requests, rng)

    datasets: dict[str, list] = {
        "ingested_component_definitions": generate_component_definitions(),
        "ingested_component_ownerships": generate_component_ownerships(),
        "ingested_team_memberships": generate_team_memberships(),
        "ingested_pull_requests": pull_requests,
        "ingested_review_events": generate_review_events(pull_requests, rng),
        "ingested_ci_runs": generate_ci_runs(pull_requests, rng),
        "ingested_deployments": deployments,
        "ingested_incidents": generate_incidents(deployments, rng),
        "ingested_work_items": generate_work_items(rng),
        "ingested_repository_snapshots": generate_repository_snapshots(),
        "ingested_environment_provisions": generate_environment_provisions(rng),
        "ingested_service_observability_snapshots": generate_service_observability_snapshots(),
        "ingested_agent_policy_snapshots": generate_agent_policy_snapshots(),
        "ingested_agent_benchmark_results": generate_agent_benchmark_results(rng),
        "ingested_agent_sessions": generate_agent_sessions(pull_requests, rng),
        "ingested_survey_responses": generate_survey_responses(),
        "ingested_product_experiments": generate_product_experiments(rng),
        "ingested_product_decisions": generate_product_decisions(deployments, rng),
        "ingested_customer_sessions": generate_customer_sessions(rng),
        "ingested_product_hypotheses": generate_product_hypotheses(rng),
        "ingested_customer_outcome_events": generate_customer_outcome_events(rng),
        "ingested_customer_activations": generate_customer_activations(rng),
        "ingested_customer_retention_snapshots": generate_customer_retention_snapshots(rng),
        "ingested_finance_records": generate_finance_records(),
        "ingested_engineering_cost_records": generate_engineering_cost_records(),
        "ingested_service_cost_records": generate_service_cost_records(),
    }
    return datasets


def main() -> None:
    from sqlmodel import Session

    from causal_coding.store import StoreConfig, create_schema, engine_from_config, save_events

    engine = engine_from_config(StoreConfig.from_env())
    create_schema(engine)
    datasets = generate_all()
    with Session(engine) as session:
        for table_name, rows in datasets.items():
            save_events(session, rows)
            print(f"seeded {len(rows):4d} rows -> {table_name}")


if __name__ == "__main__":
    main()
