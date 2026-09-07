from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from pyvis.network import Network

from causal_coding.evidence import LITERATURE
from causal_coding.measurements import measurement_for
from causal_coding.model import EDGES, EdgeStatus, graph


STATUS_COLOR = {
    EdgeStatus.HYPOTHESIS: "#9ca3af",
    EdgeStatus.LITERATURE_SUPPORTED: "#22c55e",
    EdgeStatus.MIXED: "#f59e0b",
    EdgeStatus.MECHANISTIC: "#60a5fa",
}


def _node_title(node: str) -> str:
    measurement = measurement_for(node)
    metrics = "".join(
        f"<li><b>{escape(metric.name)}</b> — {escape(metric.observability.value)}; "
        f"{escape(metric.source.value)} / {escape(metric.grain.value)}</li>"
        for metric in measurement.candidates
    )
    return (
        f"<b>{escape(node)}</b><br>{escape(measurement.construct_definition)}"
        f"<br><br><b>Candidate measurements</b><ul>{metrics}</ul>"
    )


def _edge_title(edge) -> str:
    evidence_html = ""
    if edge.evidence_ids:
        entries = []
        for evidence_id in edge.evidence_ids:
            item = LITERATURE[evidence_id]
            entries.append(
                "<li>"
                f"<b>{escape(item.relation.value.upper())}</b> — "
                f"<a href='{escape(str(item.url))}' target='_blank'>{escape(item.citation)}</a> "
                f"({item.year}; {escape(item.evidence_type.value)}; {escape(item.directness.value)})"
                f"<br>{escape(item.finding)}"
                f"<br><i>Population:</i> {escape(item.population)}"
                "</li>"
            )
        evidence_html = "<br><b>Literature evidence</b><ul>" + "".join(entries) + "</ul>"
    else:
        evidence_html = "<br><b>Literature evidence:</b> none attached yet"
    return (
        f"<b>{escape(edge.hypothesis)}: {escape(edge.cause)} → {escape(edge.effect)}</b>"
        f"<br><b>Expected sign:</b> {escape(edge.sign)}"
        f"<br><b>Status:</b> {escape(edge.status.value)}"
        f"<br>{escape(edge.rationale)}"
        f"{evidence_html}"
    )


def build_network() -> Network:
    network = Network(
        height="900px",
        width="100%",
        directed=True,
        bgcolor="#111827",
        font_color="#f9fafb",
        select_menu=True,
        filter_menu=True,
        cdn_resources="in_line",
    )
    network.barnes_hut(gravity=-18000, central_gravity=0.15, spring_length=180, spring_strength=0.035)

    dag = graph()
    for node in dag.nodes:
        network.add_node(
            node,
            label=node.replace("_", " "),
            title=_node_title(node),
            shape="dot",
            size=16,
        )

    for edge in EDGES:
        network.add_edge(
            edge.cause,
            edge.effect,
            label=edge.hypothesis,
            title=_edge_title(edge),
            color=STATUS_COLOR[edge.status],
            arrows="to",
            width=2 if edge.evidence_ids else 1,
        )

    network.set_options(
        """
        {
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true,
            "tooltipDelay": 80,
            "hideEdgesOnDrag": true
          },
          "nodes": {"font": {"size": 14}},
          "edges": {
            "font": {"size": 10, "align": "middle"},
            "smooth": {"enabled": true, "type": "dynamic"}
          },
          "physics": {"stabilization": {"iterations": 600}}
        }
        """
    )
    return network


def render(path: str | Path = "causal-coding-graph.html") -> Path:
    output = Path(path)
    network = build_network()
    network.write_html(str(output), open_browser=False, notebook=False)
    assert output.exists()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the causal-coding evidence graph.")
    parser.add_argument("--output", default="causal-coding-graph.html")
    args = parser.parse_args()
    output = render(args.output)
    print(output.resolve())


if __name__ == "__main__":
    main()
