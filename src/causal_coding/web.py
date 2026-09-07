from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .evidence import LITERATURE
from .measurements import measurement_for
from .model import EDGES, Edge, graph
from .workbench import _compute_layout, layout

PACKAGE = Path(__file__).parent
app = FastAPI(title="Causal Coding Workbench")
app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE / "templates")


def edge_by_id(edge_id: str) -> Edge:
    matches = [edge for edge in EDGES if edge.hypothesis == edge_id]
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="Unknown causal edge")
    return matches[0]


def context(request: Request, *, view: str, focus: str | None, target: str) -> dict:
    return {
        "request": request,
        "graph_view": layout(view=view, focus=focus, target=target),
        "view": view,
        "focus": focus,
        "target": target,
        "node_count": len(graph().nodes),
        "edge_count": len(EDGES),
        "evidence_count": sum(bool(edge.evidence_ids) for edge in EDGES),
    }


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    view: str = Query("overview", pattern="^(overview|full)$"),
    focus: str | None = None,
    target: str = "commercial_success",
):
    return templates.TemplateResponse(request, "index.html", context(request, view=view, focus=focus, target=target))


@app.get("/graph", response_class=HTMLResponse)
def graph_partial(
    request: Request,
    view: str = Query("overview", pattern="^(overview|full)$"),
    focus: str | None = None,
    target: str = "commercial_success",
):
    return templates.TemplateResponse(
        request, "_graph_reset.html", context(request, view=view, focus=focus, target=target)
    )


@app.get("/focus/{node_id}", response_class=HTMLResponse)
def focus_node(request: Request, node_id: str, view: str = "overview", target: str = "commercial_success"):
    if node_id not in graph():
        raise HTTPException(status_code=404, detail="Unknown causal variable")
    data = context(request, view=view, focus=node_id, target=target)
    data["measurement"] = measurement_for(node_id)
    data["node_id"] = node_id
    return templates.TemplateResponse(request, "_focus.html", data)


@app.get("/graph/metrics")
def graph_metrics(
    view: str = Query("overview", pattern="^(overview|full)$"),
    target: str = "commercial_success",
) -> dict:
    """Layout readability diagnostics for development/debugging - not linked from any page.
    Same underlying cached computation as the normal graph render, just exposed as JSON."""
    result = _compute_layout(view, target)
    return {
        "view": view,
        "target": target,
        "nodes": len(result.positions),
        "edges": len(result.edge_paths),
        "selected_seed": result.seed,
        **asdict(result.metrics),
    }


@app.get("/edge/{edge_id}", response_class=HTMLResponse)
def edge_detail(
    request: Request,
    edge_id: str,
    view: str = Query("overview", pattern="^(overview|full)$"),
    target: str = "commercial_success",
):
    edge = edge_by_id(edge_id)
    evidence = [LITERATURE[evidence_id] for evidence_id in edge.evidence_ids]
    return templates.TemplateResponse(
        request,
        "_edge_detail.html",
        {"request": request, "edge": edge, "evidence": evidence, "view": view, "target": target},
    )


def main() -> None:
    import uvicorn

    uvicorn.run("causal_coding.web:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
