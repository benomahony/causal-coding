from __future__ import annotations

from collections import defaultdict

from causal_coding.measurements import MEASUREMENTS, Observability, Source
from causal_coding.model import graph


def missing_measurements() -> set[str]:
    measured = {measurement.variable for measurement in MEASUREMENTS}
    return set(graph().nodes) - measured


def sources_by_variable() -> dict[str, tuple[Source, ...]]:
    return {
        measurement.variable: tuple(dict.fromkeys(metric.source for metric in measurement.candidates))
        for measurement in MEASUREMENTS
    }


def variables_by_source() -> dict[Source, tuple[str, ...]]:
    grouped: dict[Source, list[str]] = defaultdict(list)
    for measurement in MEASUREMENTS:
        for source in dict.fromkeys(metric.source for metric in measurement.candidates):
            grouped[source].append(measurement.variable)
    return {source: tuple(sorted(variables)) for source, variables in grouped.items()}


def collection_priorities() -> tuple[str, ...]:
    return (
        "agent session↔person↔task↔PR linkage",
        "agent execution steps and explicit human intervention/approval/takeover events",
        "agent edit attribution before commit",
        "agent available-tools and permissions snapshots per session",
        "context items supplied/retrieved and their age per session",
        "review request/start/submission timestamps",
        "component and ownership maps versioned over time",
        "required CI check category, trigger, completion and failure classification",
        "environment request↔ready timestamps",
        "commit/PR↔production deployment linkage",
        "deployment↔rollback/hotfix/incident attribution",
        "service observability capability snapshots",
    )


def proxy_only_variables() -> tuple[str, ...]:
    result = []
    for measurement in MEASUREMENTS:
        if measurement.candidates and all(metric.observability == Observability.PROXY for metric in measurement.candidates):
            result.append(measurement.variable)
    return tuple(result)


def render_report() -> str:
    lines = ["CAUSAL-CODING DATA REQUIREMENTS", ""]
    for measurement in MEASUREMENTS:
        lines.append(measurement.variable)
        lines.append(f"  construct: {measurement.construct_definition}")
        lines.append(f"  preferred: {measurement.preferred_metric or 'none — triangulate/retain as construct'}")
        for metric in measurement.candidates:
            lines.append(f"  - {metric.name}: {metric.observability.value}; {metric.source.value}; {metric.grain.value}; {metric.unit}")
            lines.append(f"      definition: {metric.definition}")
            lines.append(f"      inputs: {', '.join(metric.raw_inputs)}")
            if metric.aggregation:
                lines.append(f"      derive: {metric.aggregation}")
            if metric.caveat:
                lines.append(f"      caveat: {metric.caveat}")
        lines.append("")

    lines.extend(["COLLECT NOW (NOT RELIABLY RECONSTRUCTABLE LATER)", ""])
    lines.extend(f"  - {item}" for item in collection_priorities())
    lines.extend(["", "PROXY-ONLY CONSTRUCTS NEED BETTER INSTRUMENTATION OR TRIANGULATION", ""])
    lines.extend(f"  - {item}" for item in proxy_only_variables())
    return "\n".join(lines)
