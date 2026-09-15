from __future__ import annotations

from functools import reduce

import networkx as nx

from causal_coding.model import EDGES, EdgeStatus, graph
from causal_coding.strategy import (
    _STRONG_STATUS,
    Sign,
    _plus,
    _times,
    ambiguity_sources,
    confident_strategies,
    directed_paths,
    edge_sign,
    gating_variables,
    net_influence,
    on_path_edges,
)


def test_sign_product_composes_influences_in_series():
    assert _times(Sign.POSITIVE, Sign.POSITIVE) is Sign.POSITIVE
    assert _times(Sign.POSITIVE, Sign.NEGATIVE) is Sign.NEGATIVE
    assert _times(Sign.NEGATIVE, Sign.NEGATIVE) is Sign.POSITIVE
    assert _times(Sign.POSITIVE, Sign.AMBIGUOUS) is Sign.AMBIGUOUS
    assert _times(Sign.ZERO, Sign.AMBIGUOUS) is Sign.ZERO


def test_sign_sum_makes_competing_paths_ambiguous():
    assert _plus(Sign.POSITIVE, Sign.POSITIVE) is Sign.POSITIVE
    assert _plus(Sign.POSITIVE, Sign.NEGATIVE) is Sign.AMBIGUOUS
    assert _plus(Sign.POSITIVE, Sign.ZERO) is Sign.POSITIVE
    assert _plus(Sign.AMBIGUOUS, Sign.NEGATIVE) is Sign.AMBIGUOUS


def test_edge_sign_maps_heterogeneous_to_ambiguous():
    assert edge_sign("agentic_task_share", "agent_value") is Sign.AMBIGUOUS  # K6
    assert edge_sign("deployment_automation", "deployment_frequency") is Sign.POSITIVE  # P6
    assert edge_sign("automated_verification", "human_verification_demand") is Sign.NEGATIVE  # F5


def test_pure_chain_has_determinate_sign():
    """A single-path effect through only determinate edges is itself determinate."""
    ni = net_influence("deployment_automation", "deployment_frequency")
    assert ni.sign is Sign.POSITIVE
    assert ni.determinate


def test_competing_determinate_paths_cancel_to_ambiguous():
    """human_implementation_efficiency reaches gross_margin by a positive and a
    negative path with no heterogeneous edge on either, so the net sign is an open
    question purely because the paths cancel."""
    paths = directed_paths("human_implementation_efficiency", "gross_margin")
    signs = {p.sign for p in paths}
    assert Sign.POSITIVE in signs and Sign.NEGATIVE in signs
    assert Sign.AMBIGUOUS not in signs
    assert net_influence("human_implementation_efficiency", "gross_margin").sign is Sign.AMBIGUOUS


def test_net_influence_matches_path_enumeration_for_every_reachable_pair():
    """The topological DP must give the same verdict as summing over all enumerated
    directed paths -- for every reachable pair in the real model, not a sample."""
    dag = graph()
    for cause in dag.nodes:
        for effect in nx.descendants(dag, cause):
            expected = reduce(_plus, (p.sign for p in directed_paths(cause, effect)), Sign.ZERO)
            assert net_influence(cause, effect).sign is expected, (cause, effect)


def test_no_path_is_zero_influence():
    """No directed path is a determinate 'no effect', not an ambiguity."""
    ni = net_influence("commercial_success", "agentic_task_share")
    assert ni.sign is Sign.ZERO
    assert ni.determinate


def test_commercial_case_for_agents_is_ambiguous_and_gated():
    """The headline result: the whole commercial effect of agent involvement is
    sign-ambiguous, gated on agent_value and implementation_effort, and the single
    edge to resolve is K6."""
    ni = net_influence("agentic_task_share", "commercial_success")
    assert ni.sign is Sign.AMBIGUOUS
    gates = gating_variables("agentic_task_share", "commercial_success")
    assert "agent_value" in gates
    assert "implementation_effort" in gates
    sources = ambiguity_sources("agentic_task_share", "commercial_success")
    assert {a.hypothesis for a in sources} == {"K6"}


def test_gates_lie_on_every_path_and_exclude_endpoints():
    cause, effect = "agentic_task_share", "commercial_success"
    gates = gating_variables(cause, effect)
    assert cause not in gates and effect not in gates
    for path in directed_paths(cause, effect):
        assert set(gates) <= set(path.nodes)


def test_confident_strategies_are_determinate_and_fully_evidence_backed():
    """Every returned strategy has a committed sign and no hypothesis / mixed edge
    carries it -- that is the definition of the confidence filter."""
    strategies = confident_strategies()
    assert strategies
    for s in strategies:
        assert s.sign in (Sign.POSITIVE, Sign.NEGATIVE)
        assert net_influence(s.cause, s.effect).sign is s.sign
        for edge in on_path_edges(s.cause, s.effect):
            assert edge.status in _STRONG_STATUS
        assert s.literature_edges + s.mechanistic_edges == s.edge_count


def test_confident_strategies_ranked_best_first():
    strategies = confident_strategies()
    keys = [(-s.literature_edges, s.hops, s.edge_count, s.cause, s.effect) for s in strategies]
    assert keys == sorted(keys)


def test_highest_confidence_strategy_is_small_batch_reduces_lead_time():
    """The single most literature-backed determinate claim in the model, and
    tellingly it is about delivery flow, not agents (every agent path is
    ambiguous, so none qualifies)."""
    top = confident_strategies()[0]
    assert (top.cause, top.effect, top.sign) == ("small_batch_discipline", "lead_time", Sign.NEGATIVE)
    assert top.literature_edges >= 3
    assert all(s.cause != "agentic_task_share" for s in confident_strategies())


def test_confident_strategies_excludes_any_hypothesis_or_mixed_carried_effect():
    covered = {(s.cause, s.effect) for s in confident_strategies()}
    weak = {e.status for e in EDGES if e.status not in _STRONG_STATUS}
    assert EdgeStatus.HYPOTHESIS in weak  # sanity: the model does contain weak edges
    for cause, effect in covered:
        assert all(edge.status in _STRONG_STATUS for edge in on_path_edges(cause, effect))


def test_ambiguity_sources_only_reports_on_path_heterogeneous_edges():
    sources = ambiguity_sources("agentic_task_share", "commercial_success")
    dag = graph()
    from_cause = nx.descendants(dag, "agentic_task_share") | {"agentic_task_share"}
    to_effect = nx.ancestors(dag, "commercial_success") | {"commercial_success"}
    for edge in sources:
        assert edge.sign in ("heterogeneous", "unknown")
        assert edge.cause in from_cause
        assert edge.effect in to_effect
