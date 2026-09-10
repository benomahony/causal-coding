"""Layout pipeline property tests, run against the real causal model (not a synthetic
graph) - see layout_metrics.py for the geometry-primitive unit tests.

The layout algorithm changed from a force-simulation + simulated-annealing local search
(optimising directly against these metrics, multi-seed, non-deterministic-looking but
seeded) to a deterministic Sugiyama-style layered layout (columned by causal depth,
ordered within a column by the barycenter heuristic over depth-chained dummy waypoints).
That was a deliberate legibility trade: a DAG with a real causal ordering reads far better
laid out left-to-right by that ordering than force-simulated into an organic hairball, even
though nothing here explicitly minimises crossings the way the old local search did.
Thresholds below are recalibrated to the new algorithm's actual output (with headroom),
not the old one's -- they're a regression guard against this algorithm getting worse, not
a claim that these are the lowest achievable numbers.
"""

import math

from fastapi.testclient import TestClient

from causal_coding.web import app
from causal_coding.workbench import NODE_H, NODE_W, _build_dag, _compute_layout, layout

client = TestClient(app)

# Measured against the layered layout (depth-columns + dummy-waypoint barycenter
# ordering), with headroom for minor future tuning.
CEILING = {
    "overview": {"edge_crossings": 25, "edge_node_intersections": 15},
    "full": {"edge_crossings": 140, "edge_node_intersections": 45},
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


def test_crossings_and_intersections_do_not_regress() -> None:
    for view in ("overview", "full"):
        result = _compute_layout(view, "commercial_success")
        assert result.metrics.edge_crossings <= CEILING[view]["edge_crossings"]
        assert result.metrics.edge_node_intersections <= CEILING[view]["edge_node_intersections"]


def test_viewport_utilization_is_sensible() -> None:
    # No aspect-ratio assertion here on purpose: a layered layout for a DAG with a long
    # causal chain (22 depth levels in the full model) is *supposed* to come out wide
    # rather than square -- that's legible, not a defect to correct toward 1:1.
    for view in ("overview", "full"):
        result = _compute_layout(view, "commercial_success")
        assert 0.02 <= result.metrics.viewport_utilization <= 1.0


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
