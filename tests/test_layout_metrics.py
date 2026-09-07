import math

from hypothesis import given
from hypothesis import strategies as st

from causal_coding.layout_metrics import (
    compute_metrics,
    count_node_overlaps,
    find_edge_crossings,
    find_edge_node_intersections,
    find_hub_angle_conflicts,
    find_parallel_bundles,
    point_in_rect,
    segment_intersects_rect,
    segments_intersect,
)

# ---- segments_intersect ----------------------------------------------------------------


def test_x_crossing_segments_intersect() -> None:
    assert segments_intersect((0, 0), (10, 10), (0, 10), (10, 0))


def test_parallel_non_touching_segments_do_not_intersect() -> None:
    assert not segments_intersect((0, 0), (10, 0), (0, 5), (10, 5))


def test_collinear_overlapping_segments_intersect() -> None:
    assert segments_intersect((0, 0), (10, 0), (5, 0), (15, 0))


def test_collinear_disjoint_segments_do_not_intersect() -> None:
    assert not segments_intersect((0, 0), (5, 0), (10, 0), (15, 0))


def test_endpoint_touching_segments_report_true() -> None:
    # Raw geometric contract: touching at a shared point is a true intersection.
    # Graph-level callers filter out edge pairs that share a node before calling this.
    assert segments_intersect((0, 0), (10, 0), (10, 0), (10, 10))


def test_perpendicular_far_apart_segments_do_not_intersect() -> None:
    assert not segments_intersect((0, 0), (1, 0), (100, 100), (100, 101))


# ---- segment_intersects_rect / point_in_rect -------------------------------------------


def test_segment_through_rect_intersects() -> None:
    assert segment_intersects_rect((-10, 0), (10, 0), 0, 0, 5, 5)


def test_segment_missing_rect_does_not_intersect() -> None:
    assert not segment_intersects_rect((-10, 20), (10, 20), 0, 0, 5, 5)


def test_segment_tangent_to_rect_edge_intersects() -> None:
    assert segment_intersects_rect((-10, 5), (10, 5), 0, 0, 5, 5)


def test_segment_fully_inside_rect_intersects() -> None:
    assert segment_intersects_rect((-1, -1), (1, 1), 0, 0, 5, 5)


def test_point_in_rect() -> None:
    assert point_in_rect((0, 0), 0, 0, 5, 5)
    assert not point_in_rect((6, 0), 0, 0, 5, 5)


# ---- node overlap -----------------------------------------------------------------------


def test_overlapping_node_rects_are_counted() -> None:
    positions = {"a": (0.0, 0.0), "b": (10.0, 0.0)}
    assert count_node_overlaps(positions, node_w=180, node_h=50) == 1


def test_separated_node_rects_are_not_counted() -> None:
    positions = {"a": (0.0, 0.0), "b": (300.0, 0.0)}
    assert count_node_overlaps(positions, node_w=180, node_h=50) == 0


# ---- edge crossings -----------------------------------------------------------------------


def test_crossing_edges_are_flagged() -> None:
    positions = {"a": (0, 0), "b": (10, 10), "c": (0, 10), "d": (10, 0)}
    segments = {("a", "b"): (positions["a"], positions["b"]), ("c", "d"): (positions["c"], positions["d"])}
    assert find_edge_crossings(segments) == [(("a", "b"), ("c", "d"))]


def test_edges_sharing_a_node_are_not_flagged_as_crossing() -> None:
    positions = {"a": (0, 0), "b": (10, 10), "c": (10, 0)}
    # a->b and a->c share node "a" - they touch there by construction, not a real crossing.
    segments = {("a", "b"): (positions["a"], positions["b"]), ("a", "c"): (positions["a"], positions["c"])}
    assert find_edge_crossings(segments) == []


# ---- edge/node intersection ---------------------------------------------------------------


def test_edge_through_unrelated_node_is_flagged() -> None:
    positions = {"a": (-100, 0), "b": (100, 0), "blocker": (0, 0)}
    segments = {("a", "b"): (positions["a"], positions["b"])}
    hits = find_edge_node_intersections(segments, positions, node_w=180, node_h=50)
    assert (("a", "b"), "blocker") in hits


def test_edge_not_touching_unrelated_node_is_not_flagged() -> None:
    positions = {"a": (-100, 0), "b": (100, 0), "far": (0, 500)}
    segments = {("a", "b"): (positions["a"], positions["b"])}
    hits = find_edge_node_intersections(segments, positions, node_w=180, node_h=50)
    assert hits == set()


# ---- parallel / near-overlap bundles ------------------------------------------------------


def test_near_parallel_close_edges_are_flagged() -> None:
    positions = {"a": (0, 0), "b": (200, 0), "c": (0, 10), "d": (200, 10)}
    segments = {("a", "b"): (positions["a"], positions["b"]), ("c", "d"): (positions["c"], positions["d"])}
    bundles = find_parallel_bundles(segments, gap_thresh=30.0)
    assert len(bundles) == 1
    assert bundles[0][:2] in {(("a", "b"), ("c", "d")), (("c", "d"), ("a", "b"))}


def test_perpendicular_edges_are_not_flagged_as_parallel() -> None:
    positions = {"a": (0, 0), "b": (200, 0), "c": (0, 0), "d": (0, 200)}
    segments = {("a", "b"): (positions["a"], positions["b"]), ("c", "d"): (positions["c"], positions["d"])}
    assert find_parallel_bundles(segments, gap_thresh=30.0) == []


def test_far_apart_parallel_edges_are_not_flagged() -> None:
    positions = {"a": (0, 0), "b": (200, 0), "c": (0, 500), "d": (200, 500)}
    segments = {("a", "b"): (positions["a"], positions["b"]), ("c", "d"): (positions["c"], positions["d"])}
    assert find_parallel_bundles(segments, gap_thresh=30.0) == []


# ---- hub angle bunching --------------------------------------------------------------------


def test_tight_angle_hub_is_flagged() -> None:
    center = (0.0, 0.0)
    positions = {
        "hub": center,
        "n1": (100.0, 0.0),
        "n2": (100.0, 5.0),
        "n3": (100.0, -5.0),
    }
    edges = [("hub", "n1"), ("hub", "n2"), ("hub", "n3")]
    total, per_node = find_hub_angle_conflicts(positions, edges)
    assert total > 0
    assert "hub" in per_node


def test_wide_angle_hub_is_not_flagged() -> None:
    positions = {
        "hub": (0.0, 0.0),
        "n1": (100.0, 0.0),
        "n2": (-50.0, 87.0),
        "n3": (-50.0, -87.0),
    }
    edges = [("hub", "n1"), ("hub", "n2"), ("hub", "n3")]
    total, per_node = find_hub_angle_conflicts(positions, edges)
    assert total == 0
    assert per_node == {}


def test_hub_conflict_requires_at_least_three_incident_edges() -> None:
    positions = {"hub": (0.0, 0.0), "n1": (100.0, 0.0), "n2": (100.0, 1.0)}
    edges = [("hub", "n1"), ("hub", "n2")]
    total, per_node = find_hub_angle_conflicts(positions, edges)
    assert total == 0
    assert per_node == {}


# ---- overall score monotonicity ------------------------------------------------------------


def _clean_fixture() -> tuple[dict[str, tuple[float, float]], list[tuple[str, str]]]:
    # A small, well-separated, non-crossing, roughly square-ish layout.
    positions = {
        "a": (0.0, 0.0),
        "b": (300.0, 0.0),
        "c": (0.0, 300.0),
        "d": (300.0, 300.0),
    }
    edges = [("a", "b"), ("c", "d")]
    return positions, edges


def test_score_worsens_when_node_overlap_is_introduced() -> None:
    positions, edges = _clean_fixture()
    clean = compute_metrics(positions, edges, node_w=180, node_h=50)

    broken = dict(positions)
    broken["c"] = (5.0, 5.0)  # now overlaps "a"
    dirty = compute_metrics(broken, edges, node_w=180, node_h=50)

    assert dirty.node_overlaps > clean.node_overlaps
    assert dirty.score > clean.score


def test_score_worsens_when_crossing_is_introduced() -> None:
    positions, edges = _clean_fixture()
    clean = compute_metrics(positions, edges, node_w=180, node_h=50)

    # Re-wire so the two edges cross: a-d and b-c.
    crossing_edges = [("a", "d"), ("b", "c")]
    dirty = compute_metrics(positions, crossing_edges, node_w=180, node_h=50)

    assert dirty.edge_crossings > clean.edge_crossings
    assert dirty.score > clean.score


def test_metrics_have_no_nan_or_inf_on_clean_fixture() -> None:
    positions, edges = _clean_fixture()
    metrics = compute_metrics(positions, edges, node_w=180, node_h=50)
    for value in (
        metrics.total_edge_length,
        metrics.mean_edge_length,
        metrics.bbox_w,
        metrics.bbox_h,
        metrics.viewport_utilization,
        metrics.aspect_ratio_error,
        metrics.score,
    ):
        assert math.isfinite(value)


# ---- property-based tests over random geometry ----------------------------------------------

finite_coord = st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False)
point_strategy = st.tuples(finite_coord, finite_coord)


@given(point_strategy, point_strategy, point_strategy, point_strategy)
def test_segments_intersect_is_symmetric(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], p4: tuple[float, float]) -> None:
    assert segments_intersect(p1, p2, p3, p4) == segments_intersect(p3, p4, p1, p2)


@given(point_strategy, point_strategy, point_strategy, point_strategy)
def test_segments_intersect_is_endpoint_order_independent(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], p4: tuple[float, float]) -> None:
    assert segments_intersect(p1, p2, p3, p4) == segments_intersect(p2, p1, p4, p3)


@given(point_strategy, st.floats(min_value=1, max_value=500), st.floats(min_value=1, max_value=500))
def test_point_in_rect_center_is_always_inside(center: tuple[float, float], half_w: float, half_h: float) -> None:
    assert point_in_rect(center, center[0], center[1], half_w, half_h)


@given(point_strategy, point_strategy, point_strategy, st.floats(min_value=1, max_value=500), st.floats(min_value=1, max_value=500))
def test_segment_intersects_rect_true_when_either_endpoint_inside(
    p1: tuple[float, float], p2: tuple[float, float], center: tuple[float, float], half_w: float, half_h: float
) -> None:
    if point_in_rect(p1, center[0], center[1], half_w, half_h) or point_in_rect(p2, center[0], center[1], half_w, half_h):
        assert segment_intersects_rect(p1, p2, center[0], center[1], half_w, half_h)
