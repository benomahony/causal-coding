from __future__ import annotations

import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from causal_coding.evidence import LITERATURE
from causal_coding.workbench import NODE_H, NODE_W, layout


def render(path: str | Path = "causal-coding-graph.html", *, view: str = "overview") -> Path:
    """Export a standalone SVG workbench with no optional rendering dependency."""
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(),
    )
    output = Path(path)
    output.write_text(environment.get_template("export.html").render(
        graph_view=layout(view), node_w=NODE_W, node_h=NODE_H, literature=LITERATURE,
    ), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the causal model as standalone HTML.")
    parser.add_argument("--output", default="causal-coding-graph.html")
    parser.add_argument("--view", choices=("overview", "full"), default="overview")
    arguments = parser.parse_args()
    print(render(arguments.output, view=arguments.view).resolve())


if __name__ == "__main__":
    main()
