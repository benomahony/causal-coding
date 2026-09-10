from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
from causal_coding.events import ComponentDefinition, ComponentOwnership
from causal_coding.survey_events import SurveyResponse

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_component_definition_backs_component_map_raw_input():
    definition = ComponentDefinition.model_validate(
        {"observed_at": NOW, "source_system": "devlake", "repository_id": "repo-1", "component_name": "checkout", "path_patterns": ("src/checkout/**",)}
    )
    assert definition.component_name == "checkout"


def test_component_ownership_backs_ownership_map_raw_input():
    ownership = ComponentOwnership.model_validate(
        {
            "observed_at": NOW,
            "source_system": "codeowners",
            "repository_id": "repo-1",
            "component_name": "checkout",
            "owner_team_id": "team-checkout",
            "effective_from": NOW,
        }
    )
    assert ownership.owner_team_id == "team-checkout"


def test_survey_response_model_validate_requires_instrument():
    response = SurveyResponse.model_validate(
        {
            "observed_at": NOW,
            "source_system": "survey-tool",
            "respondent_id": "p1",
            "team_id": "team-checkout",
            "instrument": "dora_capability_scale",
            "instrument_version": "2025",
            "items": {"continuous_delivery": 4.2},
        }
    )
    assert response.instrument == "dora_capability_scale"

    # SQLModel table classes skip validation on bare Model(**kwargs) construction --
    # model_validate() is required to actually enforce required fields.
    with pytest.raises(ValidationError):
        SurveyResponse.model_validate({"observed_at": NOW, "source_system": "survey-tool", "respondent_id": "p1", "team_id": "team-checkout", "items": {}})


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (ProductExperiment, {"experiment_id": "exp-1", "started_at": NOW, "hypothesis": "faster checkout increases conversion"}),
        (ProductDecision, {"decision_id": "dec-1", "committed_at": NOW}),
        (CustomerSession, {"session_id": "sess-1"}),
        (ProductHypothesis, {"hypothesis_id": "hyp-1"}),
        (CustomerOutcomeEvent, {"customer_id": "cust-1", "core_outcome_event": "checkout_completed", "success": True}),
        (CustomerActivation, {"customer_id": "cust-1", "activation_event": "first_purchase", "occurred_at": NOW}),
        (CustomerRetentionSnapshot, {"customer_id": "cust-1", "eligible_at": NOW}),
        (FinanceRecord, {"period": "2026-08", "product_id": "prod-1", "recognised_revenue": 10_000.0}),
        (EngineeringCostRecord, {"period": "2026-08", "engineering_labour_cost": 5_000.0, "agent_compute_cost": 200.0, "tooling_cost": 100.0}),
        (ServiceCostRecord, {"period": "2026-08", "infrastructure_cost": 800.0, "support_cost": 300.0, "incident_cost": 50.0}),
    ],
)
def test_commercial_event_constructs_from_measurement_raw_inputs(cls, kwargs):
    event = cls.model_validate(dict(observed_at=NOW, source_system="test", **kwargs))
    assert event.observed_at == NOW
