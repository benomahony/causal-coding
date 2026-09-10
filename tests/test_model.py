import networkx as nx
import pytest

from causal_coding.data_requirements import missing_measurements
from causal_coding.evidence import LITERATURE, EvidenceRelation
from causal_coding.hypotheses import HYPOTHESES
from causal_coding.measurements import MEASUREMENTS, Observability, measurement_for
from causal_coding.model import EDGES, EdgeStatus, graph


def test_graph_is_dag() -> None:
    assert nx.is_directed_acyclic_graph(graph())


def test_edge_endpoints_are_nonempty() -> None:
    assert all(edge.cause and edge.effect for edge in EDGES)


def test_edge_ids_are_unique() -> None:
    ids = [edge.hypothesis for edge in EDGES]
    assert len(ids) == len(set(ids))


def test_hypothesis_ids_are_unique() -> None:
    ids = [hypothesis.id for hypothesis in HYPOTHESES]
    assert len(ids) == len(set(ids))


def test_every_graph_node_has_measurement_definition() -> None:
    assert missing_measurements() == set()


def test_measurement_variables_are_unique() -> None:
    variables = [measurement.variable for measurement in MEASUREMENTS]
    assert len(variables) == len(set(variables))


def test_no_hand_wavy_aggregate_nodes_remain() -> None:
    coarse = {
        "agentic_coding",
        "hardening",
        "platform_quality",
        "team_capability",
        "codebase_quality",
        "delivery_performance",
        "agent_context_quality",
        "agent_autonomy",
        "ci_feedback_latency",
        "ci_reliability",
    }
    assert set(graph().nodes).isdisjoint(coarse)


@pytest.mark.parametrize(
    "variable",
    (
        "agent_capability",
        "domain_experience",
        "software_delivery_skill",
        "modularity",
        "documentation_quality",
        "testability",
        "observability_quality",
        "task_familiarity",
        "task_complexity",
        "agent_value",
    ),
)
def test_latent_constructs_admit_proxy_or_latent_measurement(variable: str) -> None:
    measurement = measurement_for(variable)
    assert any(
        metric.observability in {Observability.PROXY, Observability.LATENT}
        for metric in measurement.candidates
    )


def test_all_evidence_ids_resolve() -> None:
    assert all(evidence_id in LITERATURE for edge in EDGES for evidence_id in edge.evidence_ids)


def test_literature_ids_match_dictionary_keys() -> None:
    assert all(key == item.id for key, item in LITERATURE.items())


def test_supported_edges_have_literature() -> None:
    for edge in EDGES:
        if edge.status in {EdgeStatus.LITERATURE_SUPPORTED, EdgeStatus.MIXED}:
            assert edge.evidence_ids, edge.hypothesis


def test_mixed_edges_include_support_and_contradiction() -> None:
    for edge in EDGES:
        if edge.status == EdgeStatus.MIXED:
            relations = {LITERATURE[evidence_id].relation for evidence_id in edge.evidence_ids}
            assert EvidenceRelation.SUPPORTS in relations
            assert EvidenceRelation.CONTRADICTS in relations


def test_mechanistic_edges_do_not_claim_literature_by_status() -> None:
    assert all(edge.status != EdgeStatus.LITERATURE_SUPPORTED for edge in EDGES if edge.status == EdgeStatus.MECHANISTIC)


def test_hypothesis_edge_references_exist() -> None:
    edge_ids = {edge.hypothesis for edge in EDGES}
    for hypothesis in HYPOTHESES:
        assert set(hypothesis.edge_ids) <= edge_ids


def test_every_literature_item_is_used() -> None:
    used = {evidence_id for edge in EDGES for evidence_id in edge.evidence_ids}
    assert set(LITERATURE) <= used


def test_task_characteristics_are_in_graph() -> None:
    assert {"task_familiarity", "task_complexity", "task_scope"} <= set(graph().nodes)


def test_change_diffusion_is_explicit_mediator() -> None:
    dag = graph()
    assert dag.has_edge("coupling", "change_diffusion")
    assert dag.has_edge("change_diffusion", "batch_size")
    assert dag.has_edge("change_diffusion", "change_failure_rate")


def test_agent_interface_quality_is_explicit() -> None:
    dag = graph()
    assert dag.has_edge("agent_interface_quality", "agent_task_success")
    assert dag.has_edge("agent_tool_access", "agent_interface_quality")


def test_context_is_decomposed() -> None:
    nodes = set(graph().nodes)
    assert {"agent_context_relevance", "agent_context_freshness", "agent_context_volume"} <= nodes


def test_ci_latency_is_decomposed() -> None:
    nodes = set(graph().nodes)
    assert {"ci_execution_latency", "ci_queue_latency", "ci_flakiness", "ci_diagnostic_quality"} <= nodes


def test_defect_escape_path_is_explicit() -> None:
    dag = graph()
    assert nx.has_path(dag, "automated_verification", "change_failure_rate")
    assert dag.has_edge("automated_verification", "premerge_defect_detection")
    assert dag.has_edge("premerge_defect_detection", "escaped_defects")
    assert dag.has_edge("escaped_defects", "change_failure_rate")


def test_commercial_success_is_explicit_target() -> None:
    dag = graph()
    assert "commercial_success" in dag
    assert nx.has_path(dag, "agentic_task_share", "commercial_success")
    assert nx.has_path(dag, "deployment_frequency", "commercial_success")
    assert nx.has_path(dag, "change_failure_rate", "commercial_success")


def test_commercial_nodes_have_measurements() -> None:
    for variable in (
        "experiment_frequency",
        "time_to_customer_value",
        "product_reliability",
        "product_learning_rate",
        "customer_value",
        "customer_adoption",
        "customer_retention",
        "revenue",
        "engineering_cost",
        "cost_to_serve",
        "gross_margin",
        "commercial_success",
    ):
        assert measurement_for(variable).variable == variable
