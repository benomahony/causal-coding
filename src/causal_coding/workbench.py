from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

import networkx as nx
import numpy as np

from . import layout_metrics
from .layout_metrics import (
    HUB_ANGLE_THRESH,
    IDEAL_EDGE_LENGTH,
    LayoutMetrics,
    compute_metrics,
    find_edge_node_intersections,
    find_parallel_bundles,
    pair_parallel_weight,
    segment_intersects_rect,
    segments_intersect,
)
from .model import EDGES, Edge, graph

METRIC_WEIGHTS = layout_metrics.WEIGHTS


class Stage(StrEnum):
    INPUTS = "Agent inputs"
    SYSTEM = "Task & system"
    AGENT = "Agent execution"
    FLOW = "Engineering flow"
    DELIVERY = "Delivery"
    PRODUCT = "Product"
    COMMERCIAL = "Commercial"


STAGE_ORDER = tuple(Stage)

PRODUCT_NODES = {
    "experiment_frequency",
    "time_to_customer_value",
    "product_reliability",
    "product_learning_rate",
    "customer_value",
}
COMMERCIAL_NODES = {
    "customer_adoption",
    "customer_retention",
    "revenue",
    "engineering_cost",
    "cost_to_serve",
    "gross_margin",
    "commercial_success",
}
DELIVERY_NODES = {
    "lead_time",
    "deployment_frequency",
    "change_failure_rate",
    "recovery_time",
    "deployment_rework_rate",
}
INPUT_NODES = {
    "agent_access",
    "agent_capability",
    "agent_tool_access",
    "agent_autonomy_policy",
}
AGENT_NODES = {
    "agent_interface_quality",
    "agent_context_relevance",
    "agent_context_freshness",
    "agent_context_volume",
    "agent_task_success",
    "agent_usage_intensity",
    "realised_agent_autonomy",
    "agentic_task_share",
    "agent_value",
}

TASK_NODES = {"task_familiarity", "task_complexity", "task_scope"}
SYSTEM_NODES = TASK_NODES | {
    "domain_experience",
    "software_delivery_skill",
    "team_stability",
    "review_capacity",
    "modularity",
    "coupling",
    "documentation_quality",
    "testability",
    "test_feedback_coverage",
    "type_constraint_coverage",
    "static_analysis_coverage",
    "architecture_constraint_coverage",
    "contract_test_coverage",
    "policy_automation_coverage",
    "deployment_automation",
    "observability_quality",
    "ci_execution_latency",
    "ci_queue_latency",
    "ci_flakiness",
    "ci_diagnostic_quality",
    "environment_provisioning_latency",
}


def stage_for(node: str) -> Stage:
    if node in COMMERCIAL_NODES:
        return Stage.COMMERCIAL
    if node in PRODUCT_NODES:
        return Stage.PRODUCT
    if node in DELIVERY_NODES:
        return Stage.DELIVERY
    if node in INPUT_NODES:
        return Stage.INPUTS
    if node in AGENT_NODES:
        return Stage.AGENT
    if node in SYSTEM_NODES:
        return Stage.SYSTEM
    return Stage.FLOW


OVERVIEW_NODES = {
    "agent_access",
    "agent_capability",
    "agent_interface_quality",
    "agent_context_relevance",
    "agent_task_success",
    "agentic_task_share",
    "agent_value",
    "task_familiarity",
    "task_complexity",
    "modularity",
    "coupling",
    "change_diffusion",
    "automated_verification",
    "implementation_effort",
    "implementation_capacity",
    "change_rate",
    "batch_size",
    "wip",
    "lead_time",
    "deployment_frequency",
    "change_failure_rate",
    "recovery_time",
    "deployment_rework_rate",
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
}


@dataclass(frozen=True)
class PositionedNode:
    id: str
    label: str
    stage: Stage
    x: int
    y: int
    focused: bool
    target: bool
    muted: bool


@dataclass(frozen=True)
class PositionedEdge:
    edge: Edge
    path: str
    muted: bool
    focused: bool


@dataclass(frozen=True)
class GraphView:
    nodes: tuple[PositionedNode, ...]
    edges: tuple[PositionedEdge, ...]
    width: int
    height: int
    focus: str | None
    target: str
    view: str


NODE_W = 180
NODE_H = 50
PADDING = 90
DEPTH_SPACING = 78.0
SIM_ITERATIONS = 320
SIM_SEED = 7
REPULSION_SCALE = 45.0
"""Repulsion range / initial scatter width grow as REPULSION_SCALE * sqrt(node_count), so a
crowded causal-depth tier (typically many source/input nodes at the bottom) gets
proportionally more room instead of every view starting from the same fixed-width band."""

# ---- readability optimisation on top of the sim ----------------------------------------
# The force sim above produces good *candidate* positions; it does not itself minimise
# crossings, overlapping edges, or hub pile-up. SEEDS gives several deterministic starting
# points, each refined by simulated annealing (_local_search) against the same objective
# used to score them (layout_metrics.compute_metrics); the best-scoring candidate wins.
SEEDS = (7, 13, 29, 41, 53)
LOCAL_SEARCH_ITER_PER_NODE = 40
ANNEAL_T0 = 500.0
ANNEAL_T_MIN = 1.0
ANNEAL_STEP0 = 40.0
ANNEAL_STEP_MIN = 4.0
WEIGHT_DEPTH_DEVIATION = 0.05
SWAP_MOVE_PROB = 0.1
JUMP_MOVE_PROB = 0.1

MIN_ATTACH_SEP = math.radians(10)
MAX_BEND = 60.0


def _nodes_for_view(view: str) -> set[str]:
    nodes = set(graph().nodes)
    if view == "overview":
        return nodes & OVERVIEW_NODES
    return nodes


def _relevant_to_focus(dag: nx.DiGraph, focus: str | None, target: str) -> set[str]:
    if focus is None or focus not in dag:
        return set(dag.nodes)
    related = {focus}
    related |= nx.ancestors(dag, focus)
    related |= nx.descendants(dag, focus)
    if target in dag and nx.has_path(dag, focus, target):
        for path in nx.all_simple_paths(dag, focus, target, cutoff=12):
            related.update(path)
    return related


def _clip_to_box(cx: float, cy: float, half_w: float, half_h: float, tx: float, ty: float) -> tuple[float, float]:
    """Point where the ray from (cx,cy) toward (tx,ty) exits the axis-aligned box centered at (cx,cy)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    candidates = []
    if dx != 0:
        candidates.append(half_w / abs(dx))
    if dy != 0:
        candidates.append(half_h / abs(dy))
    t = min(candidates)
    return cx + dx * t, cy + dy * t


def _causal_depth(dag: nx.DiGraph) -> dict[str, int]:
    """Longest path from a source, per node - every edge strictly increases depth."""
    depth: dict[str, int] = {}
    for node in nx.topological_sort(dag):
        preds = list(dag.predecessors(node))
        depth[node] = 0 if not preds else max(depth[p] for p in preds) + 1
    return depth


def _resolve_overlaps(
    positions: dict[str, tuple[float, float]], gap_x: float, gap_y: float, iterations: int = 300
) -> None:
    """Push overlapping node boxes apart until none overlap. Mutates positions in place."""
    nodes = list(positions)
    for _ in range(iterations):
        moved = False
        for i in range(len(nodes)):
            a = nodes[i]
            ax, ay = positions[a]
            for j in range(i + 1, len(nodes)):
                b = nodes[j]
                bx, by = positions[b]
                dx, dy = bx - ax, by - ay
                ox, oy = gap_x - abs(dx), gap_y - abs(dy)
                if ox <= 0 or oy <= 0:
                    continue
                moved = True
                if ox < oy:
                    push = ox / 2 + 0.5
                    sign = 1.0 if dx >= 0 else -1.0
                    ax, bx = ax - sign * push, bx + sign * push
                else:
                    push = oy / 2 + 0.5
                    sign = 1.0 if dy >= 0 else -1.0
                    ay, by = ay - sign * push, by + sign * push
                positions[a] = (ax, ay)
                positions[b] = (bx, by)
            positions[a] = (ax, ay)
        if not moved:
            break


def _flow_positions(dag: nx.DiGraph, seed: int = SIM_SEED) -> dict[str, tuple[float, float]]:
    """A real physics simulation (springs along edges + mutual repulsion), gently biased
    bottom-to-top by causal depth so the story still reads inputs (bottom) -> commercial
    success (top), without pinning every node to a rigid column/lane grid.

    This produces a *candidate* layout only - readability (crossings, overlaps, hub
    pile-up, space usage) is optimised afterwards by `_local_search` against the objective
    in `layout_metrics.compute_metrics`, not by the physics itself."""
    nodes = list(dag.nodes)
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: (0.0, 0.0)}

    depth = _causal_depth(dag)
    idx = {node: i for i, node in enumerate(nodes)}
    # SVG y grows downward, so rising causal depth needs decreasing y to read bottom -> top.
    target_y = np.array([-depth[node] * DEPTH_SPACING for node in nodes], dtype=float)

    # Scatter width and repulsion range both grow with node count so a crowded tier (e.g.
    # the many source/input nodes sharing the lowest causal depth) gets proportionally more
    # room to spread into, instead of every view starting from the same fixed-width band.
    scatter = REPULSION_SCALE * math.sqrt(n)
    rng = np.random.default_rng(seed)
    pos = np.stack([rng.uniform(-scatter, scatter, size=n), target_y], axis=1)
    pos[:, 1] += rng.uniform(-20, 20, size=n)

    edge_pairs = [(idx[u], idx[v]) for u, v in dag.edges if u in idx and v in idx]
    eu = np.array([p[0] for p in edge_pairs], dtype=int)
    ev = np.array([p[1] for p in edge_pairs], dtype=int)

    ideal_edge = 210.0
    min_sep = REPULSION_SCALE * math.sqrt(n)
    for _ in range(SIM_ITERATIONS):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((delta**2).sum(-1))
        np.fill_diagonal(dist, np.inf)
        push = np.clip(min_sep - dist, 0, None) * 0.08
        repulse = (delta / dist[..., None] * push[..., None]).sum(axis=1)

        attract = np.zeros_like(pos)
        if len(eu):
            d = pos[ev] - pos[eu]
            dist_e = np.sqrt((d**2).sum(-1)) + 1e-6
            f = (dist_e - ideal_edge) * 0.02
            fvec = d / dist_e[:, None] * f[:, None]
            np.add.at(attract, eu, fvec)
            np.add.at(attract, ev, -fvec)

        gravity_y = (target_y - pos[:, 1]) * 0.03

        pos[:, 0] += repulse[:, 0] + attract[:, 0]
        pos[:, 1] += repulse[:, 1] + attract[:, 1] + gravity_y

    return {node: (float(pos[i, 0]), float(pos[i, 1])) for node, i in idx.items()}


def _node_hub_score(node: str, positions: dict[str, tuple[float, float]], incident_edges: list[tuple[str, str]]) -> float:
    """Penalty for edges leaving/entering `node` at nearly the same angle - same rule as
    layout_metrics.find_hub_angle_conflicts, evaluated for one node so the local-search
    loop can recompute just the handful of nodes actually affected by a move."""
    if len(incident_edges) < 3:
        return 0.0
    ncx, ncy = positions[node]
    angles = []
    for u, v in incident_edges:
        other = v if u == node else u
        ocx, ocy = positions[other]
        angles.append(math.atan2(ocy - ncy, ocx - ncx))
    angles.sort()
    m = len(angles)
    score = 0.0
    for i in range(m):
        gap = abs(angles[i] - angles[(i + 1) % m]) % (2 * math.pi)
        gap = min(gap, 2 * math.pi - gap)
        if gap < HUB_ANGLE_THRESH:
            score += HUB_ANGLE_THRESH - gap
    return score


def _local_search(
    positions: dict[str, tuple[float, float]],
    dag: nx.DiGraph,
    target_y: dict[str, float],
    *,
    rng: np.random.Generator,
) -> dict[str, tuple[float, float]]:
    """Simulated annealing directly against the readability objective. The force sim above
    gives a reasonable starting layout; this nudges (or occasionally jumps/swaps) one node
    at a time and keeps the move only when it doesn't make things worse. Node overlap is a
    hard constraint: a move that increases it is rejected outright, independent of
    temperature, so "no node overlaps" can be a strict guarantee on the final output.

    Only the terms that a single node's position actually affects are scored per move
    (edges incident to it, the nodes it might now overlap, the hub angles at it and its
    neighbours) - global terms like bounding-box aspect ratio and viewport utilisation are
    evaluated once per candidate layout in `_best_layout`, not on every micro-move."""
    nodes = list(dag.nodes)
    n = len(nodes)
    if n < 2:
        return dict(positions)

    edges = list(dag.edges)
    incident: dict[str, list[tuple[str, str]]] = {node: [] for node in nodes}
    neighbors: dict[str, set[str]] = {node: set() for node in nodes}
    for u, v in edges:
        incident[u].append((u, v))
        incident[v].append((u, v))
        neighbors[u].add(v)
        neighbors[v].add(u)

    gap_thresh = NODE_H * 0.6
    half_w, half_h = NODE_W / 2, NODE_H / 2

    def moved_score(moved: list[str], pos: dict[str, tuple[float, float]]) -> tuple[float, int]:
        overlap = 0
        for node in moved:
            ncx, ncy = pos[node]
            for other in nodes:
                if other == node:
                    continue
                ocx, ocy = pos[other]
                if abs(ncx - ocx) < NODE_W and abs(ncy - ocy) < NODE_H:
                    overlap += 1
        score = METRIC_WEIGHTS["node_overlap"] * overlap

        seen_edges: set[tuple[str, str]] = set()
        for node in moved:
            for edge in incident[node]:
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                p1, p2 = pos[edge[0]], pos[edge[1]]
                length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                score += METRIC_WEIGHTS["edge_length_excess"] * max(0.0, length - IDEAL_EDGE_LENGTH)
                for other_node in nodes:
                    if other_node in edge:
                        continue
                    ocx, ocy = pos[other_node]
                    if segment_intersects_rect(p1, p2, ocx, ocy, half_w, half_h):
                        score += METRIC_WEIGHTS["edge_node_intersection"]
                for other_edge in edges:
                    if other_edge == edge or edge[0] in other_edge or edge[1] in other_edge:
                        continue
                    p3, p4 = pos[other_edge[0]], pos[other_edge[1]]
                    if segments_intersect(p1, p2, p3, p4):
                        score += METRIC_WEIGHTS["edge_crossing"]
                    weight = pair_parallel_weight(p1, p2, p3, p4, gap_thresh=gap_thresh)
                    if weight:
                        score += METRIC_WEIGHTS["edge_overlap"] * weight

        # Edges not incident to a moved node may now pass through its (moved) rectangle.
        for node in moved:
            ncx, ncy = pos[node]
            for edge in edges:
                if node in edge:
                    continue
                p1, p2 = pos[edge[0]], pos[edge[1]]
                if segment_intersects_rect(p1, p2, ncx, ncy, half_w, half_h):
                    score += METRIC_WEIGHTS["edge_node_intersection"]

        hub_nodes: set[str] = set(moved)
        for node in moved:
            hub_nodes.update(neighbors[node])
        hub_score = sum(_node_hub_score(node, pos, incident[node]) for node in hub_nodes)
        score += METRIC_WEIGHTS["hub_bunching"] * hub_score

        for node in moved:
            dy = pos[node][1] - target_y[node]
            score += WEIGHT_DEPTH_DEVIATION * dy * dy

        return score, overlap

    positions = dict(positions)
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    x_lo, x_hi = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)

    total_iterations = max(1, LOCAL_SEARCH_ITER_PER_NODE * n)
    for i in range(total_iterations):
        t = i / total_iterations
        temperature = ANNEAL_T0 * (ANNEAL_T_MIN / ANNEAL_T0) ** t
        step = ANNEAL_STEP0 * (ANNEAL_STEP_MIN / ANNEAL_STEP0) ** t

        roll = rng.random()
        if roll < SWAP_MOVE_PROB:
            i1, i2 = rng.choice(n, size=2, replace=False)
            u, v = nodes[int(i1)], nodes[int(i2)]
            moved = [u, v]
            before, overlap_before = moved_score(moved, positions)
            proposal = dict(positions)
            proposal[u], proposal[v] = positions[v], positions[u]
        else:
            u = nodes[int(rng.integers(0, n))]
            moved = [u]
            before, overlap_before = moved_score(moved, positions)
            proposal = dict(positions)
            if roll < SWAP_MOVE_PROB + JUMP_MOVE_PROB:
                proposal[u] = (float(rng.uniform(x_lo, x_hi)), float(rng.uniform(y_lo, y_hi)))
            else:
                dx, dy = rng.normal(0.0, step, size=2)
                ux, uy = positions[u]
                proposal[u] = (ux + float(dx), uy + float(dy))

        after, overlap_after = moved_score(moved, proposal)
        if overlap_after > overlap_before:
            continue  # hard constraint: never let node overlap get worse

        delta = after - before
        if delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-6)):
            positions = proposal

    return positions


def _best_layout(dag: nx.DiGraph) -> tuple[dict[str, tuple[float, float]], LayoutMetrics, int]:
    """Run several deterministic candidates (sim -> hard overlap resolution -> local search)
    and keep the one that scores best on the full readability objective, including the
    softer viewport/aspect-ratio terms that local search itself doesn't optimise move by
    move."""
    depth = _causal_depth(dag)
    target_y = {node: -depth[node] * DEPTH_SPACING for node in dag.nodes}
    dag_edges = list(dag.edges)

    best_positions: dict[str, tuple[float, float]] | None = None
    best_metrics: LayoutMetrics | None = None
    best_seed: int | None = None
    for seed in SEEDS:
        positions = _flow_positions(dag, seed=seed)
        _resolve_overlaps(positions, NODE_W + 40, NODE_H + 34)
        positions = _local_search(positions, dag, target_y, rng=np.random.default_rng(seed + 1))
        metrics = compute_metrics(positions, dag_edges, node_w=NODE_W, node_h=NODE_H)
        if best_metrics is None or metrics.score < best_metrics.score:
            best_positions, best_metrics, best_seed = positions, metrics, seed

    assert best_positions is not None and best_metrics is not None and best_seed is not None
    return best_positions, best_metrics, best_seed


TWO_PI = 2 * math.pi


def _spread_angles(angles: list[float], min_sep: float = MIN_ATTACH_SEP) -> list[float]:
    """Push a set of angles (radians) apart on a circle so no two are closer than `min_sep`,
    preserving their relative order. Same push-until-stable spirit as `_resolve_overlaps`,
    but solved directly: cut the circle at its largest existing gap (so nothing has to wrap
    around), then enforce minimum spacing left-to-right along that unrolled line."""
    n = len(angles)
    if n < 2:
        return list(angles)
    sep = min(min_sep, (TWO_PI / n) * 0.9)
    normalized = [a % TWO_PI for a in angles]
    order = sorted(range(n), key=lambda i: normalized[i])
    sorted_vals = [normalized[i] for i in order]

    gaps = [(sorted_vals[(k + 1) % n] - sorted_vals[k]) % TWO_PI for k in range(n)]
    start = (gaps.index(max(gaps)) + 1) % n

    rotated = [sorted_vals[(start + i) % n] + (TWO_PI if (start + i) % n < start else 0.0) for i in range(n)]
    for i in range(1, n):
        if rotated[i] - rotated[i - 1] < sep:
            rotated[i] = rotated[i - 1] + sep

    result = [0.0] * n
    for i in range(n):
        result[order[(start + i) % n]] = rotated[i] % TWO_PI
    return result


def _attachment_points(
    positions: dict[str, tuple[float, float]], dag: nx.DiGraph
) -> dict[tuple[str, str], tuple[float, float]]:
    """For every directed edge (u, v), the point on u's rectangle perimeter where that edge
    leaves u (and, symmetrically, on v's perimeter where it arrives). Each node spreads the
    angles of *all* its own incident edges independently of how busy the far end is, using
    `_clip_to_box` at the adjusted angle instead of literally toward the other node's
    centre - this is what breaks up pile-up at high-degree hubs."""
    half_w, half_h = NODE_W / 2, NODE_H / 2
    result: dict[tuple[str, str], tuple[float, float]] = {}
    for node in dag.nodes:
        ncx, ncy = positions[node]
        neighbor_edges = [(node, v) for v in dag.successors(node)] + [(u, node) for u in dag.predecessors(node)]
        if not neighbor_edges:
            continue
        raw_angles = []
        for u, v in neighbor_edges:
            other = v if u == node else u
            ocx, ocy = positions[other]
            raw_angles.append(math.atan2(ocy - ncy, ocx - ncx))
        adjusted = _spread_angles(raw_angles)
        for (u, v), angle in zip(neighbor_edges, adjusted):
            other = v if u == node else u
            far = (ncx + math.cos(angle) * 1e5, ncy + math.sin(angle) * 1e5)
            result[(node, other)] = _clip_to_box(ncx, ncy, half_w, half_h, *far)
    return result


def _route_edges(
    positions: dict[str, tuple[float, float]],
    attachment: dict[tuple[str, str], tuple[float, float]],
    dag: nx.DiGraph,
) -> dict[tuple[str, str], str]:
    """Straight lines by default. A quadratic-Bezier bend is added only for edges flagged,
    against their *actual* routed (attachment-point) segments, as passing through an
    unrelated node or as bundled together with another edge running nearly the same route -
    not decoration, a fix for a specific detected problem. Single pass, not iterative: rare
    residual conflicts on a graph this size are an accepted trade-off (verified visually)."""
    edge_list = list(dag.edges)
    segments = {
        (u, v): (attachment.get((u, v), positions[u]), attachment.get((v, u), positions[v])) for u, v in edge_list
    }

    node_hits = find_edge_node_intersections(segments, positions, NODE_W, NODE_H)
    blocked_by: dict[tuple[str, str], str] = {}
    for edge_id, node in node_hits:
        blocked_by.setdefault(edge_id, node)

    gap_thresh = NODE_H * 0.6
    bundles = find_parallel_bundles(segments, gap_thresh=gap_thresh)

    parent: dict[tuple[str, str], tuple[str, str]] = {e: e for e in edge_list}

    def find(e: tuple[str, str]) -> tuple[str, str]:
        while parent[e] != e:
            parent[e] = parent[parent[e]]
            e = parent[e]
        return e

    for a, b, _weight in bundles:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    bundle_members: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for edge_id in edge_list:
        if edge_id in blocked_by:
            continue  # blocked edges bend around the node instead of lane-offsetting
        bundle_members.setdefault(find(edge_id), []).append(edge_id)

    paths: dict[tuple[str, str], str] = {}
    for edge_id in edge_list:
        p1, p2 = segments[edge_id]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy) or 1.0
        perp = (-dy / length, dx / length)
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2

        offset = 0.0
        if edge_id in blocked_by:
            bcx, bcy = positions[blocked_by[edge_id]]
            side = 1.0 if (perp[0] * (bcx - mx) + perp[1] * (bcy - my)) < 0 else -1.0
            offset = min(MAX_BEND, math.hypot(NODE_W, NODE_H) / 2 + 20.0) * side
        else:
            members = sorted(bundle_members.get(find(edge_id), [edge_id]))
            if len(members) > 1:
                lane = members.index(edge_id) - (len(members) - 1) / 2
                offset = max(-MAX_BEND, min(MAX_BEND, lane * gap_thresh))

        if offset == 0.0:
            paths[edge_id] = f"M {p1[0]:.1f} {p1[1]:.1f} L {p2[0]:.1f} {p2[1]:.1f}"
        else:
            cx, cy = mx + perp[0] * offset, my + perp[1] * offset
            paths[edge_id] = f"M {p1[0]:.1f} {p1[1]:.1f} Q {cx:.1f} {cy:.1f} {p2[0]:.1f} {p2[1]:.1f}"

    return paths


@dataclass(frozen=True)
class _LayoutResult:
    positions: tuple[tuple[str, float, float], ...]
    edge_paths: tuple[tuple[str, str, str], ...]
    metrics: LayoutMetrics
    seed: int


def _build_dag(view: str, target: str) -> nx.DiGraph:
    all_dag = graph()
    included = set(_nodes_for_view(view))
    if target not in included and target in all_dag and view == "full":
        included.add(target)

    # Build a fresh graph with an explicitly sorted node/edge order rather than using
    # nx.DiGraph.subgraph(): that returns a filtered *view* whose own iteration order is
    # not stable across process restarts (unlike a real graph's dict-backed insertion
    # order), which would silently break the "same seed -> same layout" guarantee, since
    # _flow_positions matches nodes to RNG draws by iteration order.
    dag = nx.DiGraph()
    dag.add_nodes_from(sorted(included))
    dag.add_edges_from(sorted((u, v) for u, v in all_dag.edges if u in included and v in included))
    return dag


@lru_cache(maxsize=64)
def _compute_layout(view: str, target: str) -> _LayoutResult:
    """The expensive part - multi-seed sim + local search + routing - run once per
    (view, target) and cached, since positions never depend on `focus` (focus only toggles
    which already-placed nodes/edges are shown as muted/highlighted)."""
    dag = _build_dag(view, target)

    raw_positions, metrics, seed = _best_layout(dag)
    xs = [p[0] for p in raw_positions.values()]
    ys = [p[1] for p in raw_positions.values()]
    shift_x = PADDING - min(xs, default=0)
    shift_y = PADDING - min(ys, default=0)
    positions = {node: (x + shift_x, y + shift_y) for node, (x, y) in raw_positions.items()}

    attachment = _attachment_points(positions, dag)
    routed = _route_edges(positions, attachment, dag)

    return _LayoutResult(
        positions=tuple((node, x, y) for node, (x, y) in positions.items()),
        edge_paths=tuple((u, v, routed[(u, v)]) for u, v in dag.edges),
        metrics=metrics,
        seed=seed,
    )


def layout(view: str = "overview", focus: str | None = None, target: str = "commercial_success") -> GraphView:
    dag = _build_dag(view, target)
    result = _compute_layout(view, target)
    positions = {node: (x, y) for node, x, y in result.positions}
    paths = {(u, v): path for u, v, path in result.edge_paths}

    related = _relevant_to_focus(dag, focus, target)
    positioned_nodes = tuple(
        PositionedNode(
            id=node,
            label=node.replace("_", " "),
            stage=stage_for(node),
            x=round(positions[node][0]),
            y=round(positions[node][1]),
            focused=node == focus,
            target=node == target,
            muted=focus is not None and node not in related,
        )
        for node in dag.nodes
    )

    positioned_edges = []
    for edge in EDGES:
        if edge.cause not in dag or edge.effect not in dag:
            continue
        positioned_edges.append(
            PositionedEdge(
                edge=edge,
                path=paths[(edge.cause, edge.effect)],
                muted=focus is not None and (edge.cause not in related or edge.effect not in related),
                focused=focus in {edge.cause, edge.effect},
            )
        )

    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    width = round(max(xs, default=0) + NODE_W / 2 + PADDING)
    height = round(max(ys, default=0) + NODE_H / 2 + PADDING)

    return GraphView(
        nodes=positioned_nodes,
        edges=tuple(positioned_edges),
        width=width,
        height=height,
        focus=focus,
        target=target,
        view=view,
    )
