"""Ingestion contracts for the product-analytics and finance layers of the model.

Nothing in events.py or devlake/ can supply these -- they come from product
analytics tooling (experimentation platform, session/event tracking) and
finance systems (billing, cost accounting), not developer tooling. Every
class here backs exactly the raw_inputs already declared for the
corresponding variable in measurements.py; gross_margin and commercial_success
stay derived from these rather than getting their own event, matching how
measurements.py already defines them (DERIVED/LATENT over other measured
values, not a new raw input).

Each class is a SQLModel table -- the ingestion contract and its Postgres
storage schema are the same class, same as events.py.
"""

from __future__ import annotations

from datetime import datetime

from causal_coding.events import Event


class ProductExperiment(Event, table=True):
    __tablename__ = "ingested_product_experiments"

    experiment_id: str
    started_at: datetime
    completed_at: datetime | None = None
    hypothesis: str
    result: str | None = None


class ProductDecision(Event, table=True):
    __tablename__ = "ingested_product_decisions"

    decision_id: str
    committed_at: datetime
    deployment_id: str | None = None
    customer_available_at: datetime | None = None


class CustomerSession(Event, table=True):
    __tablename__ = "ingested_customer_sessions"

    session_id: str
    service_errors: int = 0
    availability_impact: bool = False
    correctness_impact: bool = False


class ProductHypothesis(Event, table=True):
    __tablename__ = "ingested_product_hypotheses"

    hypothesis_id: str
    decision: str | None = None
    evidence_threshold: str | None = None
    resolved_at: datetime | None = None


class CustomerOutcomeEvent(Event, table=True):
    __tablename__ = "ingested_customer_outcome_events"

    customer_id: str
    core_outcome_event: str
    success: bool


class CustomerActivation(Event, table=True):
    __tablename__ = "ingested_customer_activations"

    customer_id: str
    activation_event: str
    occurred_at: datetime


class CustomerRetentionSnapshot(Event, table=True):
    __tablename__ = "ingested_customer_retention_snapshots"

    customer_id: str
    eligible_at: datetime
    retained_at: datetime | None = None


class FinanceRecord(Event, table=True):
    __tablename__ = "ingested_finance_records"

    period: str
    product_id: str
    recognised_revenue: float


class EngineeringCostRecord(Event, table=True):
    __tablename__ = "ingested_engineering_cost_records"

    period: str
    engineering_labour_cost: float
    agent_compute_cost: float
    tooling_cost: float


class ServiceCostRecord(Event, table=True):
    __tablename__ = "ingested_service_cost_records"

    period: str
    infrastructure_cost: float
    support_cost: float
    incident_cost: float
