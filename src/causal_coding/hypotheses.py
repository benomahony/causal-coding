from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Hypothesis(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    statement: str
    treatment: str
    outcome: str
    moderator: str | None = None
    expected_effect: Literal["positive", "negative", "heterogeneous", "unknown"]
    falsification: str
    edge_ids: tuple[str, ...] = ()


HYPOTHESES = [
    Hypothesis(id="H_AI_EFFECT_HETEROGENEITY", statement="The effect of agent involvement on implementation effort is heterogeneous across task and repository contexts.", treatment="agentic_task_share", outcome="implementation_effort", moderator="task_familiarity", expected_effect="heterogeneous", falsification="A well-powered design finds a stable treatment effect with no meaningful task-context heterogeneity.", edge_ids=("K4", "K5", "K6", "K7")),
    Hypothesis(id="H_INTERFACE_SUCCESS", statement="Better agent-computer interfaces increase coding-agent task success.", treatment="agent_interface_quality", outcome="agent_task_success", expected_effect="positive", falsification="Controlled interface ablations do not materially change task success.", edge_ids=("A3",)),
    Hypothesis(id="H_CONTEXT_RELEVANCE", statement="More relevant and fresher context increases agent task success, while raw context volume has a non-monotonic effect.", treatment="agent_context_relevance", outcome="agent_task_success", moderator="agent_context_volume", expected_effect="heterogeneous", falsification="Context relevance/freshness do not improve success and volume shows no saturation or adverse region.", edge_ids=("A5", "A6", "A7")),
    Hypothesis(id="H_DIFFUSION_EFFORT", statement="Change diffusion increases implementation and verification effort.", treatment="change_diffusion", outcome="implementation_effort", expected_effect="positive", falsification="Diffused changes require no additional implementation effort after pre-treatment task scope is controlled.", edge_ids=("C3", "C5")),
    Hypothesis(id="H_DIFFUSION_FAILURE", statement="Change diffusion increases production change-failure risk.", treatment="change_diffusion", outcome="change_failure_rate", expected_effect="positive", falsification="Change diffusion has no effect on failed-change probability under an identified design.", edge_ids=("C6",)),
    Hypothesis(id="H_SMALL_BATCH", statement="Small-batch discipline suppresses growth in batch size as change rate increases.", treatment="change_rate", outcome="batch_size", moderator="small_batch_discipline", expected_effect="heterogeneous", falsification="Batch size rises similarly with change rate regardless of small-batch discipline.", edge_ids=("F3", "F4")),
    Hypothesis(id="H_BATCH_REVIEW", statement="Larger batches increase active review service time and lead time.", treatment="batch_size", outcome="lead_time", expected_effect="positive", falsification="Larger changes do not increase review effort or lead time after pre-treatment task scope is controlled.", edge_ids=("F11", "F12")),
    Hypothesis(id="H_QUEUE_LEAD_TIME", statement="Higher WIP and review queues increase change lead time at a given throughput.", treatment="wip", outcome="lead_time", expected_effect="positive", falsification="Queueing relationships fail after measurement error and throughput are accounted for.", edge_ids=("F9", "F10")),
    Hypothesis(id="H_MACHINE_FEEDBACK", statement="Greater automated verification reduces residual human verification demand through pre-merge defect detection.", treatment="automated_verification", outcome="human_verification_demand", expected_effect="negative", falsification="More effective machine verification does not reduce residual human verification.", edge_ids=("F5", "H7", "H8")),
    Hypothesis(id="H_CI_FEEDBACK", statement="CI execution, queueing and flakiness increase verification latency; actionable diagnostics reduce human review service time.", treatment="ci_execution_latency", outcome="verification_latency", expected_effect="positive", falsification="CI latency/reliability changes do not alter verification latency or diagnostic effort.", edge_ids=("P1", "P2", "P3", "P4")),
    Hypothesis(id="H_DEPLOYMENT_AUTOMATION", statement="Deployment automation increases deployment frequency and reduces recovery time.", treatment="deployment_automation", outcome="deployment_frequency", expected_effect="positive", falsification="Deployment automation does not improve delivery frequency or recovery under an identified design.", edge_ids=("P6", "P7")),
    Hypothesis(id="H_OBSERVABILITY_RECOVERY", statement="Higher observability quality reduces failed-deployment recovery time.", treatment="observability_quality", outcome="recovery_time", expected_effect="negative", falsification="Improved diagnostic observability does not shorten recovery after failed changes.", edge_ids=("P8",)),
    Hypothesis(id="H_AGENT_COMMERCIAL_VALUE", statement="The commercial effect of agentic coding is heterogeneous and mediated by engineering cost, delivery flow, product learning and reliability.", treatment="agentic_task_share", outcome="commercial_success", moderator="task_familiarity", expected_effect="heterogeneous", falsification="Identified commercial effects show no meaningful mediation or heterogeneity across the modeled engineering and product pathways.", edge_ids=("K6", "K7", "I2", "I3", "B1", "B2", "B13", "B17", "B19", "B20")),
    Hypothesis(id="H_DELIVERY_TO_LEARNING", statement="Higher deployment frequency increases product learning through a higher feasible experiment cadence.", treatment="deployment_frequency", outcome="product_learning_rate", expected_effect="positive", falsification="Increasing feasible delivery frequency does not increase valid experiment cadence or resolved product hypotheses.", edge_ids=("B1", "B5")),
    Hypothesis(id="H_RELIABILITY_RETENTION", statement="Higher change failure and slower recovery reduce customer retention through degraded product reliability and value.", treatment="change_failure_rate", outcome="customer_retention", expected_effect="negative", falsification="Production change failures and recovery duration do not materially affect experienced reliability, customer value or retention.", edge_ids=("B3", "B4", "B8", "B10")),
    Hypothesis(id="H_AGENT_COST_MARGIN", statement="Agentic coding can improve gross margin when reductions in implementation effort exceed added compute/tooling and downstream rework costs.", treatment="agentic_task_share", outcome="gross_margin", expected_effect="heterogeneous", falsification="Agent involvement does not change engineering cost or the cost path is too small to affect margin under realistic cost boundaries.", edge_ids=("K6", "K7", "B13", "B17")),
]
