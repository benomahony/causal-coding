"""Layout pipeline property tests, run against the real causal model (not a synthetic
graph) - see layout_metrics.py for the geometry-primitive unit tests.

Regression thresholds for crossings/intersections are anchored to two numbers: the
baseline measured against the *original*, unmodified force-sim-only layout (never
regress past that), and the result actually achieved by the optimised pipeline at the
time this test was written (with headroom, to catch a future regression without being
brittle to exact floating-point reproduction).
"""

import math

from fastapi.testclient import TestClient

from causal_coding.web import app
from causal_coding.workbench import NODE_H, NODE_W, _build_dag, _compute_layout, layout

client = TestClient(app)

# Measured against the original single-seed, no-local-search, center-clipped layout
# (git history before this optimisation), via layout_metrics.compute_metrics.
BASELINE = {
    "overview": {"edge_crossings": 21, "edge_node_intersections": 8},
    "full": {"edge_crossings": 168, "edge_node_intersections": 81},
}

# Achieved by the optimised multi-seed + local-search + routing pipeline, with headroom.
ACHIEVED_CEILING = {
    "overview": {"edge_crossings": 20, "edge_node_intersections": 5},
    "full": {"edge_crossings": 105, "edge_node_intersections": 18},
}


def test_no_node_overlaps_on_real_graph() -> None:
    for view in ("overview", "full"):
        result = _compute_layout(view, "commercial_success")
        assert result.metrics.node_overlaps == 0


def test_no_nan_or_infinite_coordinates() -> None:
    for view in ("overview", "full"):
        gv = layout(view)
        for node in gv.nodes:
            assert math.isfinite(node.x)
            assert math.isfinite(node.y)


def test_nodes_within_expected_padded_bounds() -> None:
    for view in ("overview", "full"):
        gv = layout(view)
        for node in gv.nodes:
            assert node.x >= NODE_W / 2
            assert node.y >= NODE_H / 2
            assert node.x <= gv.width
            assert node.y <= gv.height


def test_layout_is_deterministic_for_a_fixed_view() -> None:
    _compute_layout.cache_clear()
    first = _compute_layout("overview", "commercial_success")
    _compute_layout.cache_clear()
    second = _compute_layout("overview", "commercial_success")
    assert first.positions == second.positions
    assert first.edge_paths == second.edge_paths
    assert first.seed == second.seed


def test_crossings_and_intersections_do_not_regress_past_baseline() -> None:
    for view in ("overview", "full"):
        result = _compute_layout(view, "commercial_success")
        assert result.metrics.edge_crossings <= BASELINE[view]["edge_crossings"]
        assert result.metrics.edge_node_intersections <= BASELINE[view]["edge_node_intersections"]


def test_crossings_and_intersections_stay_near_the_achieved_result() -> None:
    for view in ("overview", "full"):
        result = _compute_layout(view, "commercial_success")
        assert result.metrics.edge_crossings <= ACHIEVED_CEILING[view]["edge_crossings"]
        assert result.metrics.edge_node_intersections <= ACHIEVED_CEILING[view]["edge_node_intersections"]


def test_viewport_utilization_and_aspect_ratio_are_sensible() -> None:
    for view in ("overview", "full"):
        result = _compute_layout(view, "commercial_success")
        assert 0.05 <= result.metrics.viewport_utilization <= 1.0
        assert result.metrics.aspect_ratio_error <= 0.6


def test_edge_routing_only_bends_flagged_edges() -> None:
    # Every path is either a straight line (M ... L ...) or a bend (M ... Q ...); bends
    # should be the minority, not decorative curvature applied everywhere.
    for view in ("overview", "full"):
        gv = layout(view)
        curved = sum("Q" in p.path for p in gv.edges)
        assert curved < len(gv.edges) / 2


def test_focus_does_not_change_node_positions() -> None:
    # Positions are cached per (view, target) and must not depend on focus.
    dag = _build_dag("overview", "commercial_success")
    any_node = next(iter(dag.nodes))
    unfocused = layout("overview")
    focused = layout("overview", focus=any_node)
    unfocused_positions = {n.id: (n.x, n.y) for n in unfocused.nodes}
    focused_positions = {n.id: (n.x, n.y) for n in focused.nodes}
    assert unfocused_positions == focused_positions


def test_graph_metrics_endpoint_exposes_diagnostics() -> None:
    response = client.get("/graph/metrics?view=overview")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "nodes",
        "edges",
        "node_overlaps",
        "edge_node_intersections",
        "edge_crossings",
        "edge_overlap_score",
        "viewport_utilization",
        "aspect_ratio_error",
        "mean_edge_length",
        "score",
        "selected_seed",
    ):
        assert key in body
    assert body["node_overlaps"] == 0
