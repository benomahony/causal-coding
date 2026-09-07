from __future__ import annotations

from enum import StrEnum
from typing import Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict


class EdgeStatus(StrEnum):
    HYPOTHESIS = "hypothesis"
    LITERATURE_SUPPORTED = "literature_supported"
    MIXED = "mixed"
    MECHANISTIC = "mechanistic"


class Edge(BaseModel):
    model_config = ConfigDict(frozen=True)

    cause: str
    effect: str
    hypothesis: str
    sign: Literal["positive", "negative", "unknown", "heterogeneous"]
    rationale: str
    status: EdgeStatus = EdgeStatus.HYPOTHESIS
    evidence_ids: tuple[str, ...] = ()


def e(
    cause: str,
    effect: str,
    hypothesis: str,
    sign: Literal["positive", "negative", "unknown", "heterogeneous"],
    rationale: str,
    *,
    status: EdgeStatus = EdgeStatus.HYPOTHESIS,
    evidence_ids: tuple[str, ...] = (),
) -> Edge:
    return Edge(
        cause=cause,
        effect=effect,
        hypothesis=hypothesis,
        sign=sign,
        rationale=rationale,
        status=status,
        evidence_ids=evidence_ids,
    )


EDGES = [
    # Agent availability, interface and usage.
    e("agent_access", "agent_usage_intensity", "A1", "positive", "Teams cannot materially use coding agents without access."),
    e("agent_capability", "agent_task_success", "A2", "positive", "More capable agents can successfully complete a broader task distribution."),
    e("agent_interface_quality", "agent_task_success", "A3", "positive", "Agent-oriented search, edit and feedback interfaces improve successful task execution.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("sweagent2024",)),
    e("agent_tool_access", "agent_interface_quality", "A4", "positive", "Useful tools are a necessary component of an effective agent-computer interface."),
    e("agent_context_relevance", "agent_task_success", "A5", "positive", "Relevant task and repository context should improve decision quality.", status=EdgeStatus.MIXED, evidence_ids=("dora2025_ai", "gloaguen2026")),
    e("agent_context_freshness", "agent_task_success", "A6", "positive", "Current context should reduce actions based on obsolete repository state."),
    e("agent_context_volume", "agent_task_success", "A7", "heterogeneous", "Additional context can help until irrelevant context creates attention and cost overhead.", status=EdgeStatus.MIXED, evidence_ids=("dora2025_ai", "gloaguen2026")),
    e("documentation_quality", "agent_context_relevance", "A8", "positive", "Accurate machine-readable documentation can supply relevant repository knowledge."),
    e("agent_autonomy_policy", "realised_agent_autonomy", "A10", "positive", "Policy constrains which actions agents may take independently."),
    e("agent_task_success", "realised_agent_autonomy", "A11", "positive", "Agents that can reliably complete steps require fewer human interventions."),
    e("agent_usage_intensity", "agentic_task_share", "A12", "positive", "More frequent use increases the share of engineering work involving agents."),
    e("realised_agent_autonomy", "agentic_task_share", "A13", "positive", "More autonomous sessions can cover a larger fraction of a task."),

    # Task characteristics: needed to reconcile contradictory AI productivity evidence.
    e("task_familiarity", "human_implementation_efficiency", "K1", "positive", "Familiar tasks require less repository and domain discovery.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("wang2020_familiarity",)),
    e("task_complexity", "implementation_effort", "K2", "positive", "More complex tasks require more implementation and coordination work."),
    e("task_scope", "change_diffusion", "K3", "positive", "Broader tasks naturally require changes across more files or components."),
    e("task_familiarity", "agent_value", "K4", "heterogeneous", "AI effects may differ for familiar mature-repository work versus bounded unfamiliar tasks.", status=EdgeStatus.MIXED, evidence_ids=("peng2023", "metr2025")),
    e("task_complexity", "agent_value", "K5", "heterogeneous", "The treatment effect of AI likely varies with task complexity and repository context.", status=EdgeStatus.MIXED, evidence_ids=("peng2023", "metr2025")),
    e("agentic_task_share", "agent_value", "K6", "heterogeneous", "The value of agent involvement depends on the task and environment rather than having a fixed sign.", status=EdgeStatus.MIXED, evidence_ids=("peng2023", "metr2025", "dora2025_ai")),
    e("agent_value", "implementation_effort", "K7", "negative", "Positive agent value reduces human-equivalent implementation effort; negative value increases it."),

    # Team characteristics.
    e("domain_experience", "human_implementation_efficiency", "T1", "positive", "Domain knowledge reduces search and rework during implementation."),
    e("software_delivery_skill", "human_implementation_efficiency", "T2", "positive", "Delivery skill affects how efficiently intended work becomes reviewable changes.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("dora_capabilities2018",)),
    e("team_stability", "domain_experience", "T3", "positive", "Stable teams retain system and domain knowledge."),
    e("domain_experience", "change_failure_rate", "T7", "negative", "More experienced engineers make fewer defect-inducing changes.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("mockus_weiss2000", "kamei2012")),
    e("review_capacity", "human_verification_queue", "T4", "negative", "More review service capacity reduces queued verification work.", status=EdgeStatus.MECHANISTIC),
    e("software_delivery_skill", "review_service_time", "T5", "negative", "Experienced reviewers can often evaluate changes more quickly."),
    e("review_service_time", "review_capacity", "T6", "negative", "Longer service time reduces the number of changes reviewers can process per period.", status=EdgeStatus.MECHANISTIC),

    # Codebase structure and change diffusion.
    e("modularity", "change_diffusion", "C1", "negative", "Modular systems localise a logical change to fewer components."),
    e("coupling", "change_diffusion", "C2", "positive", "Coupled systems require related modifications across more locations.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("mockus_weiss2000", "kamei2012")),
    e("change_diffusion", "implementation_effort", "C3", "positive", "Changes spanning more files/components require more implementation and coordination effort.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("mockus_weiss2000", "kamei2012")),
    e("change_diffusion", "batch_size", "C4", "positive", "A logical change distributed across more components increases delivered change size.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("mockus_weiss2000", "kamei2012")),
    e("change_diffusion", "verification_demand", "C5", "positive", "More touched components create a wider regression and review surface."),
    e("change_diffusion", "change_failure_rate", "C6", "positive", "Diffused changes are more difficult to verify and are predictive of defect-inducing changes.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("mockus_weiss2000", "kamei2012")),
    e("testability", "test_feedback_coverage", "C7", "positive", "Testable systems make behavioural feedback easier to automate."),
    e("modularity", "architecture_constraint_coverage", "C8", "positive", "Clear module boundaries make architectural rules more enforceable."),

    # Implementation flow.
    e("human_implementation_efficiency", "implementation_effort", "I1", "negative", "Greater human efficiency reduces effort for a given task."),
    e("implementation_effort", "implementation_capacity", "I2", "negative", "Higher effort per task lowers the number of candidate changes produced per unit time.", status=EdgeStatus.MECHANISTIC),
    e("implementation_capacity", "change_rate", "I3", "positive", "Additional implementation capacity increases candidate-change arrivals.", status=EdgeStatus.MECHANISTIC),

    # Automated verification mechanisms.
    e("test_feedback_coverage", "automated_verification", "H1", "positive", "Automated tests detect behavioural regressions mechanically.", evidence_ids=("roman2021",)),
    e("type_constraint_coverage", "automated_verification", "H2", "positive", "Type constraints reject invalid changes mechanically.", status=EdgeStatus.MECHANISTIC),
    e("static_analysis_coverage", "automated_verification", "H3", "positive", "Static analysis provides machine-readable correctness and policy feedback.", status=EdgeStatus.MECHANISTIC),
    e("architecture_constraint_coverage", "automated_verification", "H4", "positive", "Executable architecture rules detect boundary violations.", status=EdgeStatus.MECHANISTIC),
    e("contract_test_coverage", "automated_verification", "H5", "positive", "Contract tests detect incompatible cross-system changes.", status=EdgeStatus.MECHANISTIC),
    e("policy_automation_coverage", "automated_verification", "H6", "positive", "Automated policy checks discharge classes of manual verification.", status=EdgeStatus.MECHANISTIC),
    e("automated_verification", "premerge_defect_detection", "H7", "positive", "More effective automated verification should find more defects before merge."),
    e("premerge_defect_detection", "escaped_defects", "H8", "negative", "Defects found before merge cannot escape to production if corrected."),
    e("escaped_defects", "change_failure_rate", "H9", "positive", "Escaped defects increase the probability of degraded production changes."),

    # CI/platform feedback quality.
    e("ci_execution_latency", "verification_latency", "P1", "positive", "Slow execution delays machine feedback.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("google_build_latency",)),
    e("ci_queue_latency", "verification_latency", "P2", "positive", "Waiting for a CI worker delays machine feedback.", status=EdgeStatus.MECHANISTIC),
    e("ci_flakiness", "verification_latency", "P3", "positive", "Flaky failures cause reruns and delay trustworthy feedback."),
    e("ci_diagnostic_quality", "review_service_time", "P4", "negative", "Actionable failure evidence should reduce diagnosis and review effort.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("huang2026_ci",)),
    e("environment_provisioning_latency", "lead_time", "P5", "positive", "Waiting for usable environments adds delivery latency.", status=EdgeStatus.MECHANISTIC),
    e("deployment_automation", "deployment_frequency", "P6", "positive", "Low-friction automated deployment makes frequent delivery practical.", evidence_ids=("dora2025_ai",)),
    e("deployment_automation", "recovery_time", "P7", "negative", "Automated rollback/redeploy mechanisms shorten recovery.", evidence_ids=("dora2025_ai",)),
    e("observability_quality", "recovery_time", "P8", "negative", "Better observability reduces diagnosis time during production failures.", evidence_ids=("dora2025_ai",)),

    # Flow / queues / batch mechanisms.
    e("change_rate", "verification_demand", "F1", "positive", "More candidate changes create more verification work.", status=EdgeStatus.MECHANISTIC),
    e("change_rate", "wip", "F2", "positive", "Arrival rates above downstream capacity accumulate as WIP.", status=EdgeStatus.MECHANISTIC),
    e("change_rate", "batch_size", "F3", "positive", "Without small-batch discipline, excess production can accumulate into larger changes."),
    e("small_batch_discipline", "batch_size", "F4", "negative", "Explicit small-batch practice constrains change size.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("dora_small_batches",)),
    e("automated_verification", "human_verification_demand", "F5", "negative", "Machine verification discharges work that would otherwise require human attention."),
    e("verification_demand", "human_verification_demand", "F6", "positive", "Residual verification demand reaches humans."),
    e("verification_latency", "human_verification_queue", "F7", "positive", "Slow required machine feedback extends the lifetime of reviewable work."),
    e("human_verification_demand", "human_verification_queue", "F8", "positive", "Demand above review capacity creates a queue.", status=EdgeStatus.MECHANISTIC),
    e("human_verification_queue", "wip", "F9", "positive", "Queued review work remains unfinished WIP.", status=EdgeStatus.MECHANISTIC),
    e("wip", "lead_time", "F10", "positive", "Higher WIP is structurally related to longer time in system at a given throughput.", status=EdgeStatus.MECHANISTIC, evidence_ids=("little_law",)),
    e("batch_size", "review_service_time", "F11", "positive", "Larger changes generally take longer to understand and review.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("google_code_review",)),
    e("batch_size", "lead_time", "F12", "positive", "Larger changes require more review, verification and delivery work.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("google_code_review", "dora_small_batches")),
    e("batch_size", "change_failure_rate", "F13", "positive", "Larger/diffused changes are more difficult to verify and predict higher defect risk.", status=EdgeStatus.LITERATURE_SUPPORTED, evidence_ids=("mockus_weiss2000", "kamei2012", "dora_small_batches")),
    e("change_failure_rate", "deployment_rework_rate", "F14", "positive", "Failed changes create rollback, hotfix and corrective deployment work.", status=EdgeStatus.MECHANISTIC),
    e("deployment_rework_rate", "deployment_frequency", "F15", "negative", "Corrective work consumes delivery capacity."),
    e("lead_time", "deployment_frequency", "F16", "negative", "Longer change lead times constrain achievable delivery frequency."),

    # Product and commercial outcomes. These are deliberately hypotheses until the
    # corresponding literature pass is complete. DORA metrics are mediators, not the goal.
    e("deployment_frequency", "experiment_frequency", "B1", "positive", "More frequent production delivery increases the feasible cadence of product experiments."),
    e("lead_time", "time_to_customer_value", "B2", "positive", "Longer software delivery lead time delays when intended value can reach customers."),
    e("change_failure_rate", "product_reliability", "B3", "negative", "A higher fraction of failed changes degrades experienced product reliability."),
    e("recovery_time", "product_reliability", "B4", "negative", "Longer restoration periods extend customer exposure to failed changes."),
    e("experiment_frequency", "product_learning_rate", "B5", "positive", "More valid experiments can increase the rate at which teams learn what creates customer value."),
    e("product_learning_rate", "customer_value", "B6", "positive", "Faster validated learning should improve the rate at which product decisions create customer value."),
    e("time_to_customer_value", "customer_value", "B7", "negative", "Longer delays between deciding and delivering reduce realised customer value and responsiveness."),
    e("product_reliability", "customer_value", "B8", "positive", "Reliable software preserves the value of delivered product capabilities."),
    e("customer_value", "customer_adoption", "B9", "positive", "Products creating more customer value should attract greater adoption, all else equal."),
    e("customer_value", "customer_retention", "B10", "positive", "Products creating sustained value should improve retention, all else equal."),
    e("customer_adoption", "revenue", "B11", "positive", "Greater paying-customer adoption increases revenue under a stable commercial model."),
    e("customer_retention", "revenue", "B12", "positive", "Higher retention preserves recurring revenue under a stable commercial model."),
    e("implementation_effort", "engineering_cost", "B13", "positive", "More implementation effort consumes engineering labour and compute resources."),
    e("deployment_rework_rate", "engineering_cost", "B14", "positive", "Corrective delivery work consumes engineering capacity and operational resources."),
    e("recovery_time", "cost_to_serve", "B15", "positive", "Longer production recovery consumes support and operational resources."),
    e("revenue", "gross_margin", "B16", "positive", "Higher revenue increases gross profit when variable costs are held constant."),
    e("engineering_cost", "gross_margin", "B17", "negative", "Higher engineering cost reduces margin for a given level of revenue."),
    e("cost_to_serve", "gross_margin", "B18", "negative", "Higher operating and support cost reduces margin for a given level of revenue."),
    e("revenue", "commercial_success", "B19", "positive", "Revenue is one component of commercial success."),
    e("gross_margin", "commercial_success", "B20", "positive", "Sustainable margin is one component of commercial success."),
    e("customer_retention", "commercial_success", "B21", "positive", "Retention captures durable product value not visible in short-run revenue alone."),
]


def graph() -> nx.DiGraph:
    dag = nx.DiGraph((edge.cause, edge.effect) for edge in EDGES)
    assert nx.is_directed_acyclic_graph(dag)
    return dag
