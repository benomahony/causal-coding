"""Readability metrics for a node/edge graph layout.

Pure geometry - no dependency on networkx or the sim in ``workbench.py`` - so it can be
unit-tested in isolation and reused both to score candidate layouts and, later, to decide
where edge routing needs to bend around a problem (an edge passing through an unrelated
node, or two edges running almost on top of each other).

All edges are identified by their ``(cause, effect)`` node-id pair. Two edges that share a
node (same cause or same effect) touch there by construction, which is not a meaningful
crossing/overlap - every detector below excludes such pairs before testing them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
EdgeId = tuple[str, str]

PARALLEL_ANGLE_THRESH = math.radians(12)
"""Two edges closer than this in direction are considered "running the same way"."""

PARALLEL_MIN_SHARED_FRACTION = 0.3
"""An overlapping run must span at least this fraction of the shorter edge to count."""

HUB_ANGLE_THRESH = math.radians(15)
"""Incident edges at a node closer than this apart read as a single bunched line."""

IDEAL_EDGE_LENGTH = 220.0
"""Edges longer than this start contributing to the soft length penalty."""

TARGET_ASPECT = 1.6
"""Representative wide desktop graph-panel aspect ratio (see sketch.js computeFit)."""

TARGET_UTILIZATION = 0.55
"""Target fraction of the layout bounding box that node rectangles themselves occupy."""

WEIGHTS = {
    "node_overlap": 4000.0,
    "edge_node_intersection": 1500.0,
    "edge_crossing": 250.0,
    "edge_overlap": 40.0,
    "hub_bunching": 30.0,
    "aspect_ratio_error": 300.0,
    "utilization_deficit": 200.0,
    "edge_length_excess": 0.15,
}
"""Explicit, inspectable objective weights. Heavy: structural defects (overlap/crossing/
intersection/near-duplicate edges). Soft: space usage and edge length."""


# ---- segment/rectangle primitives -----------------------------------------------------


def _orientation(a: Point, b: Point, c: Point) -> int:
    val = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(val) < 1e-9:
        return 0
    return 1 if val > 0 else -1


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    """True if b lies on segment a-c, given a, b, c are already known to be collinear."""
    return (
        min(a[0], c[0]) - 1e-9 <= b[0] <= max(a[0], c[0]) + 1e-9
        and min(a[1], c[1]) - 1e-9 <= b[1] <= max(a[1], c[1]) + 1e-9
    )


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """Proper geometric intersection test, including the collinear-overlap case.

    Does not know about shared endpoints - two edges leaving the same node trivially
    "intersect" there, and callers with edge semantics must filter those pairs out first.
    """
    o1 = _orientation(p1, p2, p3)
    o2 = _orientation(p1, p2, p4)
    o3 = _orientation(p3, p4, p1)
    o4 = _orientation(p3, p4, p2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(p1, p3, p2):
        return True
    if o2 == 0 and _on_segment(p1, p4, p2):
        return True
    if o3 == 0 and _on_segment(p3, p1, p4):
        return True
    return bool(o4 == 0 and _on_segment(p3, p2, p4))


def point_in_rect(p: Point, cx: float, cy: float, half_w: float, half_h: float) -> bool:
    return abs(p[0] - cx) <= half_w and abs(p[1] - cy) <= half_h


def segment_intersects_rect(p1: Point, p2: Point, cx: float, cy: float, half_w: float, half_h: float) -> bool:
    minx, maxx = cx - half_w, cx + half_w
    miny, maxy = cy - half_h, cy + half_h
    # Epsilon-padded reject, consistent with point_in_rect's <=: without it, a point that
    # point_in_rect treats as exactly on the boundary can round to just outside the bbox
    # test here (floating-point subtraction isn't perfectly consistent between the two).
    if max(p1[0], p2[0]) < minx - 1e-9 or min(p1[0], p2[0]) > maxx + 1e-9:
        return False
    if max(p1[1], p2[1]) < miny - 1e-9 or min(p1[1], p2[1]) > maxy + 1e-9:
        return False
    if point_in_rect(p1, cx, cy, half_w, half_h) or point_in_rect(p2, cx, cy, half_w, half_h):
        return True
    corners = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    return any(segments_intersect(p1, p2, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _point_seg_dist(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _seg_seg_dist(p1: Point, p2: Point, p3: Point, p4: Point) -> float:
    if segments_intersect(p1, p2, p3, p4):
        return 0.0
    return min(
        _point_seg_dist(p1, p3, p4),
        _point_seg_dist(p2, p3, p4),
        _point_seg_dist(p3, p1, p2),
        _point_seg_dist(p4, p1, p2),
    )


def _angle(p1: Point, p2: Point) -> float:
    return math.atan2(p2[1] - p1[1], p2[0] - p1[0])


def _direction_diff(a: float, b: float) -> float:
    """Undirected angular difference (mod pi) between two edge directions."""
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def _circular_diff(a: float, b: float) -> float:
    """Angular difference (mod 2*pi) between two directed angles."""
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def _projected_overlap(p1: Point, p2: Point, p3: Point, p4: Point) -> float:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return 0.0
    ux, uy = dx / length, dy / length

    def proj(p: Point) -> float:
        return (p[0] - p1[0]) * ux + (p[1] - p1[1]) * uy

    b0, b1 = proj(p3), proj(p4)
    if b0 > b1:
        b0, b1 = b1, b0
    lo, hi = max(0.0, b0), min(length, b1)
    return max(0.0, hi - lo)


# ---- graph-level detectors --------------------------------------------------------------


def edge_segments(positions: dict[str, Point], edges: list[EdgeId]) -> dict[EdgeId, tuple[Point, Point]]:
    return {(u, v): (positions[u], positions[v]) for u, v in edges if u in positions and v in positions}


def count_node_overlaps(positions: dict[str, Point], node_w: float, node_h: float) -> int:
    ids = list(positions)
    count = 0
    for i in range(len(ids)):
        ax, ay = positions[ids[i]]
        for j in range(i + 1, len(ids)):
            bx, by = positions[ids[j]]
            if abs(ax - bx) < node_w and abs(ay - by) < node_h:
                count += 1
    return count


def find_edge_crossings(segments: dict[EdgeId, tuple[Point, Point]]) -> list[tuple[EdgeId, EdgeId]]:
    keys = list(segments)
    hits: list[tuple[EdgeId, EdgeId]] = []
    for i in range(len(keys)):
        u1, v1 = keys[i]
        p1, p2 = segments[keys[i]]
        for j in range(i + 1, len(keys)):
            u2, v2 = keys[j]
            if {u1, v1} & {u2, v2}:
                continue
            p3, p4 = segments[keys[j]]
            if segments_intersect(p1, p2, p3, p4):
                hits.append((keys[i], keys[j]))
    return hits


def find_edge_node_intersections(
    segments: dict[EdgeId, tuple[Point, Point]],
    positions: dict[str, Point],
    node_w: float,
    node_h: float,
) -> set[tuple[EdgeId, str]]:
    half_w, half_h = node_w / 2, node_h / 2
    hits: set[tuple[EdgeId, str]] = set()
    for (u, v), (p1, p2) in segments.items():
        for node, (cx, cy) in positions.items():
            if node == u or node == v:
                continue
            if segment_intersects_rect(p1, p2, cx, cy, half_w, half_h):
                hits.add(((u, v), node))
    return hits


def pair_parallel_weight(
    p1: Point,
    p2: Point,
    p3: Point,
    p4: Point,
    *,
    gap_thresh: float,
    angle_thresh: float = PARALLEL_ANGLE_THRESH,
    min_fraction: float = PARALLEL_MIN_SHARED_FRACTION,
) -> float:
    """Near-parallel/near-overlap weight for a single pair of segments (0.0 if the pair
    doesn't meet the angle/gap/shared-length thresholds). Shared by `find_parallel_bundles`
    and by the local-search objective in workbench.py, which scores one edge against many
    others per move and needs the per-pair test without the full O(E^2) bundle scan."""
    a1 = _angle(p1, p2)
    a2 = _angle(p3, p4)
    angle_gap = _direction_diff(a1, a2)
    if angle_gap >= angle_thresh:
        return 0.0
    gap = _seg_seg_dist(p1, p2, p3, p4)
    if gap >= gap_thresh:
        return 0.0
    overlap = _projected_overlap(p1, p2, p3, p4)
    len1 = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    len2 = math.hypot(p4[0] - p3[0], p4[1] - p3[1])
    shorter = min(len1, len2)
    if shorter < 1e-9 or overlap < min_fraction * shorter:
        return 0.0
    return overlap * (1 - gap / gap_thresh) * (1 - angle_gap / angle_thresh)


def find_parallel_bundles(
    segments: dict[EdgeId, tuple[Point, Point]],
    *,
    gap_thresh: float,
    angle_thresh: float = PARALLEL_ANGLE_THRESH,
    min_fraction: float = PARALLEL_MIN_SHARED_FRACTION,
) -> list[tuple[EdgeId, EdgeId, float]]:
    """Edge pairs that are near-collinear/near-parallel and close together over a
    meaningful shared length - i.e. they'd read as one line, or as ambiguously overlapping,
    to a viewer. Returns (edge_a, edge_b, weight) with weight increasing as the pair gets
    closer, more parallel, and covers more of the shorter edge."""
    keys = list(segments)
    flagged: list[tuple[EdgeId, EdgeId, float]] = []
    for i in range(len(keys)):
        u1, v1 = keys[i]
        p1, p2 = segments[keys[i]]
        for j in range(i + 1, len(keys)):
            u2, v2 = keys[j]
            if {u1, v1} & {u2, v2}:
                continue
            p3, p4 = segments[keys[j]]
            weight = pair_parallel_weight(
                p1, p2, p3, p4, gap_thresh=gap_thresh, angle_thresh=angle_thresh, min_fraction=min_fraction
            )
            if weight > 0.0:
                flagged.append((keys[i], keys[j], weight))
    return flagged


def find_hub_angle_conflicts(
    positions: dict[str, Point],
    edges: list[EdgeId],
    *,
    angle_thresh: float = HUB_ANGLE_THRESH,
) -> tuple[float, dict[str, float]]:
    """For every node with 3+ incident edges, penalize consecutive incidence angles that
    are closer together than angle_thresh - edges leaving/entering at nearly the same
    angle are hard to tell apart even with zero crossings. Returns (total, per_node)."""
    incident: dict[str, list[float]] = {}
    for u, v in edges:
        if u not in positions or v not in positions:
            continue
        incident.setdefault(u, []).append(_angle(positions[u], positions[v]))
        incident.setdefault(v, []).append(_angle(positions[v], positions[u]))

    per_node: dict[str, float] = {}
    for node, angles in incident.items():
        if len(angles) < 3:
            continue
        ordered = sorted(angles)
        score = 0.0
        for i in range(len(ordered)):
            gap = _circular_diff(ordered[i], ordered[(i + 1) % len(ordered)])
            if gap < angle_thresh:
                score += angle_thresh - gap
        if score:
            per_node[node] = score
    return sum(per_node.values()), per_node


# ---- overall score ------------------------------------------------------------------


@dataclass(frozen=True)
class LayoutMetrics:
    node_overlaps: int
    edge_node_intersections: int
    edge_crossings: int
    edge_overlap_score: float
    hub_bunching_score: float
    total_edge_length: float
    mean_edge_length: float
    bbox_w: float
    bbox_h: float
    viewport_utilization: float
    aspect_ratio_error: float
    score: float


def compute_metrics(
    positions: dict[str, Point],
    edges: list[EdgeId],
    *,
    node_w: float,
    node_h: float,
    target_aspect: float = TARGET_ASPECT,
    target_utilization: float = TARGET_UTILIZATION,
    ideal_edge_length: float = IDEAL_EDGE_LENGTH,
    weights: dict[str, float] = WEIGHTS,
) -> LayoutMetrics:
    segments = edge_segments(positions, edges)

    node_overlaps = count_node_overlaps(positions, node_w, node_h)
    crossings = find_edge_crossings(segments)
    node_hits = find_edge_node_intersections(segments, positions, node_w, node_h)
    gap_thresh = node_h * 0.6
    bundles = find_parallel_bundles(segments, gap_thresh=gap_thresh)
    edge_overlap_score = sum(w for *_ids, w in bundles)
    hub_bunching_score, _ = find_hub_angle_conflicts(positions, edges)

    lengths = [math.hypot(p2[0] - p1[0], p2[1] - p1[1]) for p1, p2 in segments.values()]
    total_edge_length = sum(lengths)
    mean_edge_length = total_edge_length / len(lengths) if lengths else 0.0
    edge_length_excess = sum(max(0.0, length - ideal_edge_length) for length in lengths)

    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    bbox_w = (max(xs) - min(xs) + node_w) if xs else 0.0
    bbox_h = (max(ys) - min(ys) + node_h) if ys else 0.0
    bbox_area = max(bbox_w * bbox_h, 1e-9)
    node_area = len(positions) * node_w * node_h
    utilization = min(node_area / bbox_area, 1.0)
    utilization_deficit = max(0.0, target_utilization - utilization)

    aspect = bbox_w / bbox_h if bbox_h > 0 else target_aspect
    aspect_ratio_error = abs(math.log(max(aspect, 1e-9) / target_aspect))

    score = (
        weights["node_overlap"] * node_overlaps
        + weights["edge_node_intersection"] * len(node_hits)
        + weights["edge_crossing"] * len(crossings)
        + weights["edge_overlap"] * edge_overlap_score
        + weights["hub_bunching"] * hub_bunching_score
        + weights["aspect_ratio_error"] * aspect_ratio_error
        + weights["utilization_deficit"] * utilization_deficit
        + weights["edge_length_excess"] * edge_length_excess
    )

    return LayoutMetrics(
        node_overlaps=node_overlaps,
        edge_node_intersections=len(node_hits),
        edge_crossings=len(crossings),
        edge_overlap_score=edge_overlap_score,
        hub_bunching_score=hub_bunching_score,
        total_edge_length=total_edge_length,
        mean_edge_length=mean_edge_length,
        bbox_w=bbox_w,
        bbox_h=bbox_h,
        viewport_utilization=utilization,
        aspect_ratio_error=aspect_ratio_error,
        score=score,
    )
