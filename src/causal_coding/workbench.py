from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

import networkx as nx

from .identifiability import coverage, is_estimable
from .layout_metrics import (
    LayoutMetrics,
    compute_metrics,
    find_edge_node_intersections,
    find_parallel_bundles,
)
from .model import EDGES, Edge, graph


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
    label_lines: tuple[str, ...]
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
    estimable: bool


@dataclass(frozen=True)
class GraphView:
    nodes: tuple[PositionedNode, ...]
    edges: tuple[PositionedEdge, ...]
    width: int
    height: int
    focus: str | None
    target: str
    view: str
    estimable_count: int
    total_edges: int


NODE_W = 250
NODE_H = 88
PADDING = 150  # must clear NODE_W/2 and NODE_H/2, or the outermost nodes go off-canvas
DEPTH_SPACING = 78.0
LABEL_MAX_CHARS_PER_LINE = 17
LABEL_MAX_LINES = 3

# ---- layered (Sugiyama-style) layout -----------------------------------------------
# Nodes are columned by causal depth -- the model's own topological ordering (every edge
# strictly increases it) -- not by force simulation. A force-directed hairball is the wrong
# tool for a graph that already has a real causal ordering; laying it out left-to-right by
# that ordering is what makes a 70-node DAG legible instead of an organic tangle.
# COLUMN_WIDTH/ROW_HEIGHT comfortably clear NODE_W/NODE_H, so the grid placement has no
# node overlaps by construction -- no separate overlap-resolution pass is needed.
COLUMN_WIDTH = 400.0
ROW_HEIGHT = 130.0
BARYCENTER_PASSES = 4


def _wrap_label(label: str, *, max_chars: int = LABEL_MAX_CHARS_PER_LINE, max_lines: int = LABEL_MAX_LINES) -> tuple[str, ...]:
    """Greedy word-wrap for node labels. Many variable names are 3 words / 20-30 characters
    (e.g. "architecture constraint coverage") -- a fixed "first two words, rest on line two"
    split (the previous approach) overflows the node box for exactly the longest labels,
    which most need to wrap correctly. Once max_lines is reached, everything remaining is
    appended to the last line rather than dropped -- overflowing text beats silently
    truncated content."""
    words = label.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or len(candidate) <= max_chars or len(lines) == max_lines - 1:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return tuple(lines)


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


def _layered_positions(dag: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Column each node by causal depth (longest path from a source -- every edge strictly
    increases it by construction, so no edge is ever same-column or points backward,
    unlike the coarser Stage grouping: ~48% of edges in the full model connect two nodes
    in the same Stage bucket, which made Stage a poor column key even though it's a fine
    *coloring* key).

    Edges spanning more than one column are expanded into a chain of per-column dummy
    waypoints for the ordering pass (never for rendering -- only real nodes are returned).
    Without this, a "shortcut" edge spanning many columns is invisible to the barycenter
    heuristic in every intermediate column it passes through, which is what actually drove
    crossings *up* in an earlier version of this function that used real predecessors/
    successors directly: most edges in this model skip several depth-columns, so most of
    the graph was invisible to its own ordering pass. Standard Sugiyama-style layered graph
    drawing: the right tool for a DAG with a real causal ordering, instead of force-
    simulating it into an organic hairball and hoping crossings stay low.
    """
    nodes = sorted(dag.nodes)
    if not nodes:
        return {}

    depth = _causal_depth(dag)
    col_of: dict[str, int] = dict(depth)
    predecessors: dict[str, list[str]] = defaultdict(list)
    successors: dict[str, list[str]] = defaultdict(list)

    dummy_counter = 0
    for u, v in dag.edges:
        prev = u
        for ci in range(depth[u] + 1, depth[v]):
            dummy_counter += 1
            dummy_id = f"\0dummy{dummy_counter}"
            col_of[dummy_id] = ci
            successors[prev].append(dummy_id)
            predecessors[dummy_id].append(prev)
            prev = dummy_id
        successors[prev].append(v)
        predecessors[v].append(prev)

    columns: dict[int, list[str]] = defaultdict(list)
    for node_id in sorted(col_of):
        columns[col_of[node_id]].append(node_id)
    col_indices = sorted(columns)

    order: dict[str, int] = {}
    for ci in col_indices:
        for i, node_id in enumerate(columns[ci]):
            order[node_id] = i

    def normalized(node_id: str) -> float:
        column = columns[col_of[node_id]]
        return order[node_id] / max(1, len(column) - 1)

    def barycenter_pass(*, forward: bool) -> None:
        scan = col_indices if forward else list(reversed(col_indices))
        related = predecessors if forward else successors
        for ci in scan:

            def key(node_id: str, related: dict[str, list[str]] = related) -> tuple[float, str]:
                neighbor_positions = [normalized(p) for p in related.get(node_id, ())]
                if not neighbor_positions:
                    return (normalized(node_id), node_id)
                return (sum(neighbor_positions) / len(neighbor_positions), node_id)

            columns[ci].sort(key=key)
            for i, node_id in enumerate(columns[ci]):
                order[node_id] = i

    for _ in range(BARYCENTER_PASSES):
        barycenter_pass(forward=True)
        barycenter_pass(forward=False)

    positions: dict[str, tuple[float, float]] = {}
    for ci in col_indices:
        col_nodes = columns[ci]
        x = ci * COLUMN_WIDTH
        col_span = (len(col_nodes) - 1) * ROW_HEIGHT
        y0 = -col_span / 2.0
        for i, node_id in enumerate(col_nodes):
            positions[node_id] = (x, y0 + i * ROW_HEIGHT)

    return {node: positions[node] for node in nodes}


def _best_layout(dag: nx.DiGraph) -> tuple[dict[str, tuple[float, float]], LayoutMetrics, int]:
    """Deterministic layered layout -- no seed search needed since there's no randomness.
    `seed` in the return is a vestige of the return shape `_compute_layout` expects
    (surfaced by /graph/metrics); it's always 0 now."""
    positions = _layered_positions(dag)
    metrics = compute_metrics(positions, list(dag.edges), node_w=NODE_W, node_h=NODE_H)
    return positions, metrics, 0


TWO_PI = 2 * math.pi


def _spread_angles(angles: list[float], min_sep: float = MIN_ATTACH_SEP) -> list[float]:
    """Push a set of angles (radians) apart on a circle so no two are closer than `min_sep`,
    preserving their relative order: cut the circle at its largest existing gap (so nothing
    has to wrap around), then enforce minimum spacing left-to-right along that unrolled line."""
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


def _build_dag(view: str, target: str, focus: str | None = None) -> nx.DiGraph:
    all_dag = graph()
    included = set(_nodes_for_view(view))
    if view == "neighborhood":
        center = focus if focus in all_dag else target
        included = {center, *all_dag.predecessors(center), *all_dag.successors(center)}
    if target not in included and target in all_dag and view == "full":
        included.add(target)

    # Build a fresh graph with an explicitly sorted node/edge order rather than using
    # nx.DiGraph.subgraph(): that returns a filtered *view* whose own iteration order is
    # not stable across process restarts (unlike a real graph's dict-backed insertion
    # order), which downstream edge-routing tie-breaks (bundle/bend selection) depend on
    # for reproducible output.
    dag = nx.DiGraph()
    dag.add_nodes_from(sorted(included))
    dag.add_edges_from(sorted(
        (cause, effect) for cause, effect in all_dag.edges
        if cause in included and effect in included
        and (view != "neighborhood" or center in {cause, effect})
    ))
    return dag


@lru_cache(maxsize=64)
def _compute_layout(view: str, target: str, focus: str | None = None) -> _LayoutResult:
    """Cache deterministic placement and routing for each displayed subgraph."""
    dag = _build_dag(view, target, focus)

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


def layout(
    view: str = "overview",
    focus: str | None = None,
    target: str = "commercial_success",
    observed: frozenset[str] = frozenset(),
) -> GraphView:
    dag = _build_dag(view, target, focus)
    result = _compute_layout(view, target, focus if view == "neighborhood" else None)
    positions = {node: (x, y) for node, x, y in result.positions}
    paths = {(u, v): path for u, v, path in result.edge_paths}

    related = _relevant_to_focus(dag, focus, target)
    positioned_nodes = tuple(
        PositionedNode(
            id=node,
            label=node.replace("_", " "),
            label_lines=_wrap_label(node.replace("_", " ")),
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
        if not dag.has_edge(edge.cause, edge.effect):
            continue
        positioned_edges.append(
            PositionedEdge(
                edge=edge,
                path=paths[(edge.cause, edge.effect)],
                muted=focus is not None and (edge.cause not in related or edge.effect not in related),
                focused=focus in {edge.cause, edge.effect},
                estimable=is_estimable(edge.cause, edge.effect, observed),
            )
        )
    # Coverage stat is over the *whole* causal model, not just the current view, so it
    # doesn't jump around confusingly when switching between overview and full graph.
    estimable_count, total_edges = coverage(observed)

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
        estimable_count=estimable_count,
        total_edges=total_edges,
    )
