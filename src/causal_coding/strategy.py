"""Qualitative strategy reasoning over the signed causal DAG, without data.

This is a Qualitative Probabilistic Network (Wellman 1990) layer on top of the
`sign` already carried by every edge. It answers structural strategy questions
that the numeric causal tools cannot answer before observations exist:

- What is the *net* qualitative sign of one variable's total effect on another,
  combining every directed path? When positive and negative paths compete the
  honest answer is "ambiguous", and that ambiguity is the finding.
- Which heterogeneous / unknown edges are the reason a verdict is ambiguous, so
  that measurement effort can be pointed at them first?
- Which intermediate variables gate a benefit, i.e. lie on *every* directed path
  from cause to effect, so downstream gains are throttled until they move?

Everything here is qualitative and structural. It establishes no magnitude and
no threshold. A gate says "improving this is necessary for the path to carry
value", never "no value until this metric is below N". Quantitative arrow
strength or intrinsic influence belongs to the later estimation phase (e.g.
dowhy.gcm), which requires fitted mechanisms and real data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import reduce
from itertools import pairwise

import networkx as nx

from .model import EDGES, Edge, graph


class Sign(StrEnum):
    POSITIVE = "+"
    NEGATIVE = "-"
    ZERO = "0"
    AMBIGUOUS = "?"


_EDGE_SIGN = {
    "positive": Sign.POSITIVE,
    "negative": Sign.NEGATIVE,
    "heterogeneous": Sign.AMBIGUOUS,
    "unknown": Sign.AMBIGUOUS,
}

_EDGE = {(edge.cause, edge.effect): edge for edge in EDGES}


def _times(a: Sign, b: Sign) -> Sign:
    """Sign product along a path: composing two influences in series."""
    if a is Sign.ZERO or b is Sign.ZERO:
        return Sign.ZERO
    if a is Sign.AMBIGUOUS or b is Sign.AMBIGUOUS:
        return Sign.AMBIGUOUS
    return Sign.POSITIVE if a is b else Sign.NEGATIVE


def _plus(a: Sign, b: Sign) -> Sign:
    """Sign sum across parallel paths: a positive path meeting a negative path is
    the ambiguity at the heart of the 'agents just move the bottleneck' thesis."""
    if a is b:
        return a
    if a is Sign.ZERO:
        return b
    if b is Sign.ZERO:
        return a
    return Sign.AMBIGUOUS


def edge_sign(cause: str, effect: str) -> Sign:
    return _EDGE_SIGN[_EDGE[(cause, effect)].sign]


@dataclass(frozen=True)
class Path:
    nodes: tuple[str, ...]
    hypotheses: tuple[str, ...]
    sign: Sign


def directed_paths(cause: str, effect: str) -> tuple[Path, ...]:
    """Every directed path from cause to effect, each with its composed sign.

    Enumeration is exponential in the worst case; the current model is small
    enough that this is cheap. Use `net_influence` for a verdict that never
    enumerates."""
    dag = graph()
    if cause not in dag or effect not in dag:
        return ()
    paths = []
    for nodes in nx.all_simple_paths(dag, cause, effect):
        steps = tuple(pairwise(nodes))
        sign = reduce(_times, (edge_sign(u, v) for u, v in steps), Sign.POSITIVE)
        paths.append(
            Path(
                nodes=tuple(nodes),
                hypotheses=tuple(_EDGE[step].hypothesis for step in steps),
                sign=sign,
            )
        )
    return tuple(paths)


@dataclass(frozen=True)
class NetInfluence:
    cause: str
    effect: str
    sign: Sign

    @property
    def determinate(self) -> bool:
        """The theory commits to a verdict. A positive, negative or ZERO (no
        directed influence) sign is committed; only AMBIGUOUS is an open question."""
        return self.sign is not Sign.AMBIGUOUS


def net_influence(cause: str, effect: str) -> NetInfluence:
    """Net qualitative sign of the total effect of cause on effect over all
    directed paths, by topological dynamic programming (no path enumeration).

    An AMBIGUOUS result means the theory as it stands does not commit to a
    direction: either an edge on some path is itself sign-ambiguous, or a
    positive and a negative path cancel. Either way the sign is an open empirical
    question, not a defect."""
    dag = graph()
    if cause not in dag or effect not in dag or not nx.has_path(dag, cause, effect):
        return NetInfluence(cause=cause, effect=effect, sign=Sign.ZERO)
    net: dict[str, Sign] = {cause: Sign.POSITIVE}
    for node in nx.topological_sort(dag):
        if node not in net:
            continue
        upstream = net[node]
        for successor in dag.successors(node):
            contribution = _times(upstream, edge_sign(node, successor))
            net[successor] = _plus(net.get(successor, Sign.ZERO), contribution)
    return NetInfluence(cause=cause, effect=effect, sign=net.get(effect, Sign.ZERO))


def ambiguity_sources(cause: str, effect: str) -> tuple[Edge, ...]:
    """The heterogeneous / unknown edges that lie on some directed path from cause
    to effect. Resolving these is what would let `net_influence` reach a verdict,
    so they are the priority targets for measurement."""
    dag = graph()
    if cause not in dag or effect not in dag:
        return ()
    from_cause = nx.descendants(dag, cause) | {cause}
    to_effect = nx.ancestors(dag, effect) | {effect}
    return tuple(
        edge
        for edge in EDGES
        if edge.cause in from_cause
        and edge.effect in to_effect
        and _EDGE_SIGN[edge.sign] is Sign.AMBIGUOUS
    )


def gating_variables(cause: str, effect: str) -> tuple[str, ...]:
    """Intermediate variables on *every* directed path from cause to effect:
    removing one disconnects them. These are the Theory-of-Constraints gates. A
    benefit routed through the graph cannot exceed what its gates allow, so a gate
    is a necessary (never sufficient, never quantified) condition for the effect."""
    dag = graph()
    if cause not in dag or effect not in dag or not nx.has_path(dag, cause, effect):
        return ()
    order = {node: i for i, node in enumerate(nx.topological_sort(dag))}
    gates = []
    for node in dag.nodes:
        if node in (cause, effect):
            continue
        reduced = dag.copy()
        reduced.remove_node(node)
        if not nx.has_path(reduced, cause, effect):
            gates.append(node)
    return tuple(sorted(gates, key=order.__getitem__))
