from __future__ import annotations

from causal_coding.identifiability import (
    coverage,
    edge_estimability_detail,
    graph_estimability,
    identify_edge,
    is_estimable,
)
from causal_coding.measurements import Source
from causal_coding.model import EDGES
from causal_coding.store.coverage import observed_variables


def _edge(hypothesis: str):
    return next(e for e in EDGES if e.hypothesis == hypothesis)


def test_identify_edge_is_graph_structural_only():
    result = identify_edge(_edge("F13"))
    assert result.cause == "batch_size"
    assert result.effect == "change_failure_rate"
    assert "change_diffusion" in result.backdoor_variables


def test_is_estimable_false_with_nothing_observed():
    assert not is_estimable("batch_size", "change_failure_rate", frozenset())


def test_is_estimable_true_when_cause_effect_and_all_parents_observed():
    from causal_coding.model import graph

    dag = graph()
    cause, effect = "batch_size", "change_failure_rate"
    fully_observed = frozenset(dag.predecessors(cause)) | {cause, effect}
    assert is_estimable(cause, effect, fully_observed)


def test_is_estimable_is_deterministic_regardless_of_extra_observed_variables():
    """Regression test: an earlier implementation fed the *entire* observed set to a
    d-separation search, which could flip false given extra unrelated observed
    variables (collider-opening) or a single observed descendant of the cause
    anywhere in the set. Parent-adjustment must not be sensitive to either."""
    from causal_coding.model import graph

    dag = graph()
    cause, effect = "deployment_automation", "deployment_frequency"
    minimal = frozenset(dag.predecessors(cause)) | {cause, effect}
    assert is_estimable(cause, effect, minimal)

    descendant = next(iter(set(dag.successors(effect)) | set(dag.successors(cause))), None)
    if descendant is not None:
        assert is_estimable(cause, effect, minimal | {descendant})


def test_coverage_with_nothing_observed_is_zero():
    n_estimable, total = coverage(frozenset())
    assert n_estimable == 0
    assert total == len(EDGES)


def test_coverage_is_monotonic_in_observed_data():
    """More observed data should never make coverage go down."""
    devlake_sources = frozenset({Source.SCM, Source.CI, Source.CD, Source.ISSUE_TRACKER, Source.INCIDENT_MANAGEMENT})
    everything = frozenset(Source)
    small = coverage(observed_variables(devlake_sources))[0]
    full = coverage(observed_variables(everything))[0]
    assert full >= small
    assert full < len(EDGES)
    assert "agent_value" not in observed_variables(everything)
    assert "commercial_success" not in observed_variables(everything)
    assert "task_familiarity" not in observed_variables(everything)


def test_edge_estimability_detail_gives_missing_variables_when_not_estimable():
    result = edge_estimability_detail(_edge("F13"), frozenset())
    assert not result.estimable
    assert "batch_size" in result.missing_variables
    assert "change_failure_rate" in result.missing_variables


def test_edge_estimability_detail_never_contradicts_the_fast_path():
    """detail.estimable must never disagree with is_estimable(), and detail's own
    required_parents checklist must never disagree with detail.estimable either --
    DoWhy's separately-computed dowhy_adjustment_set is informational and must not
    leak into either determination."""
    devlake_sources = frozenset({Source.SCM, Source.CI, Source.CD, Source.ISSUE_TRACKER, Source.INCIDENT_MANAGEMENT})
    observed = observed_variables(devlake_sources)
    for edge in EDGES[::7]:  # sample, not all 91 -- edge_estimability_detail calls DoWhy per edge
        fast = is_estimable(edge.cause, edge.effect, observed)
        detailed = edge_estimability_detail(edge, observed)
        assert fast == detailed.estimable, edge.hypothesis
        assert detailed.estimable == (
            detailed.cause_status.observed and detailed.effect_status.observed and all(p.observed for p in detailed.required_parents)
        )


def test_graph_estimability_covers_every_edge():
    results = graph_estimability(frozenset())
    assert len(results) == len(EDGES)
    assert all(not r.estimable for r in results)
