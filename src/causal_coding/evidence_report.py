from __future__ import annotations

from collections import Counter

from causal_coding.evidence import LITERATURE
from causal_coding.model import EDGES


def report() -> str:
    with_evidence = [edge for edge in EDGES if edge.evidence_ids]
    relations = Counter(
        LITERATURE[evidence_id].relation.value
        for edge in with_evidence
        for evidence_id in edge.evidence_ids
    )
    lines = [
        f"Edges: {len(EDGES)}",
        f"Edges with literature attached: {len(with_evidence)}",
        f"Edges still awaiting literature: {len(EDGES) - len(with_evidence)}",
        "Evidence relationships: " + ", ".join(f"{k}={v}" for k, v in sorted(relations.items())),
        "",
        "Edges awaiting literature:",
    ]
    lines.extend(f"- {edge.hypothesis}: {edge.cause} -> {edge.effect}" for edge in EDGES if not edge.evidence_ids)
    return "\n".join(lines)


def main() -> None:
    print(report())


if __name__ == "__main__":
    main()
