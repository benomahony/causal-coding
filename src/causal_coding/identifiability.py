"""Structural adjustment checks under the supplied causal DAG.

These functions assume the caller supplies observed graph variables. They do
not establish that a dataset exists, that proxies observe latent constructs,
or that measurements align by scope and time. Parent adjustment is a
conservative sufficient criterion for a total effect, not a direct-edge
estimate. The web workbench uses it only as a collection checklist.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from functools import cache

import pandas as pd
from dowhy import CausalModel

from .model import EDGES, Edge, graph


def is_estimable(cause: str, effect: str, observed: frozenset[str]) -> bool:
    """Fast path: no DoWhy call, just Pearl's parent-adjustment rule. Safe to run for
    every edge on every request."""
    dag = graph()
    observed = observed & frozenset(dag.nodes)  # defensive: ignore anything not a graph node
    if cause not in observed or effect not in observed:
        return False
    return set(dag.predecessors(cause)) <= observed


@dataclass(frozen=True)
class EdgeEstimability:
    hypothesis: str
    cause: str
    effect: str
    estimable: bool


def graph_estimability(observed: frozenset[str]) -> tuple[EdgeEstimability, ...]:
    """One fast pass over every edge -- the shape the graph UI renders from."""
    return tuple(
        EdgeEstimability(hypothesis=edge.hypothesis, cause=edge.cause, effect=edge.effect, estimable=is_estimable(edge.cause, edge.effect, observed))
        for edge in EDGES
    )


def coverage(observed: frozenset[str]) -> tuple[int, int]:
    results = graph_estimability(observed)
    return sum(r.estimable for r in results), len(results)


@dataclass(frozen=True)
class Identification:
    """DoWhy's formal identification for one edge, independent of what data exists."""

    hypothesis: str
    cause: str
    effect: str
    backdoor_variables: tuple[str, ...]


@cache
def _identify(cause: str, effect: str) -> tuple[str, ...]:
    dag = graph()
    data = pd.DataFrame(columns=sorted(dag.nodes))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = CausalModel(data=data, treatment=cause, outcome=effect, graph=dag, missing_nodes_as_confounders=True)
        estimand = model.identify_effect(proceed_when_unidentifiable=True)
    return tuple(sorted(estimand.get_backdoor_variables()))


def identify_edge(edge: Edge) -> Identification:
    """DoWhy's formal identification for one edge. Slow (multi-second) -- call for a
    single edge on demand (e.g. an edge-detail view), never in a bulk graph pass."""
    return Identification(hypothesis=edge.hypothesis, cause=edge.cause, effect=edge.effect, backdoor_variables=_identify(edge.cause, edge.effect))


@dataclass(frozen=True)
class VariableStatus:
    variable: str
    observed: bool


@dataclass(frozen=True)
class EstimabilityDetail:
    hypothesis: str
    cause: str
    effect: str
    cause_status: VariableStatus
    effect_status: VariableStatus
    # The actual basis for `estimable`: cause's direct parents (Pearl's parent-adjustment
    # theorem), each with its observed/missing status. `estimable` is computed FROM this
    # list, not separately, so the two can never contradict each other in the UI.
    required_parents: tuple[VariableStatus, ...]
    # A second, separately-computed valid adjustment set from DoWhy's own search --
    # informational only. It can legitimately differ from `required_parents` (DoWhy may
    # find a different, not-necessarily-minimal valid set); shown for transparency, not
    # used to decide `estimable`.
    dowhy_adjustment_set: tuple[str, ...]

    @property
    def estimable(self) -> bool:
        return self.cause_status.observed and self.effect_status.observed and all(p.observed for p in self.required_parents)

    @property
    def missing_variables(self) -> tuple[str, ...]:
        missing = [s.variable for s in (self.cause_status, self.effect_status, *self.required_parents) if not s.observed]
        return tuple(dict.fromkeys(missing))


def edge_estimability_detail(
    edge: Edge, observed: frozenset[str], *, identify: bool = True,
) -> EstimabilityDetail:
    """Return a parent-adjustment checklist, optionally running DoWhy identification.

    Pass identify=False for interactive views unless the user requests the slower
    structural calculation. Neither result establishes that a usable dataset exists.
    """
    dag = graph()
    parents = tuple(sorted(dag.predecessors(edge.cause)))
    return EstimabilityDetail(
        hypothesis=edge.hypothesis,
        cause=edge.cause,
        effect=edge.effect,
        cause_status=VariableStatus(variable=edge.cause, observed=edge.cause in observed),
        effect_status=VariableStatus(variable=edge.effect, observed=edge.effect in observed),
        required_parents=tuple(VariableStatus(variable=p, observed=p in observed) for p in parents),
        dowhy_adjustment_set=_identify(edge.cause, edge.effect) if identify else (),
    )
