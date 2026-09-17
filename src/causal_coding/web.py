from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from .evidence import LITERATURE
from .identifiability import edge_estimability_detail
from .measurements import Source, measurement_for
from .model import EDGES, Edge, graph
from .store import StoreConfig, all_sources_summary, engine_from_config, observed_variables
from .store.coverage import SourceSummary, VariableDataSummary, variable_summaries
from .strategy import net_influence
from .workbench import NODE_H, NODE_W, _compute_layout, layout, stage_for

PACKAGE = Path(__file__).parent
app = FastAPI(title="Causal Coding Workbench")
app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE / "templates")
templates.env.globals["query"] = urlencode
logger = logging.getLogger(__name__)
View = Literal["neighborhood", "overview", "full"]
CONNECTED = "connected"

try:
    _store_engine = engine_from_config(StoreConfig.from_env())
    _store_configuration_error = False
except RuntimeError:
    _store_engine = None
    _store_configuration_error = False
except (ValueError, SQLAlchemyError):
    _store_engine = None
    _store_configuration_error = True


@dataclass(frozen=True)
class StoreState:
    connected: bool
    message: str
    sources: tuple[SourceSummary, ...]
    variables: dict[str, VariableDataSummary]


def store_state() -> StoreState:
    empty = all_sources_summary(None)
    if _store_engine is None:
        message = "Store configuration needs attention" if _store_configuration_error else "No data store connected"
        return StoreState(False, message, empty, {})
    try:
        columns = {column["name"] for column in inspect(_store_engine).get_columns("ingested_pull_requests")}
        if "commit_shas" not in columns:
            return StoreState(False, "Store schema needs an upgrade", empty, {})
        return StoreState(True, "Live store connected", all_sources_summary(_store_engine), variable_summaries(_store_engine))
    except SQLAlchemyError as error:
        logger.warning("Store unavailable: %s", type(error).__name__)
        return StoreState(False, "Data store unavailable", empty, {})


def parse_sources_param(raw: str) -> frozenset[Source] | None:
    """Only the explicit connected sentinel uses live data; empty means none."""
    if raw == CONNECTED:
        return None
    return frozenset(source for source in Source if source.value in raw.split(","))


def sources_csv(raw: str) -> str:
    custom = parse_sources_param(raw)
    return CONNECTED if custom is None else ",".join(sorted(source.value for source in custom)) or "none"


def edge_by_id(edge_id: str) -> Edge:
    matches = [edge for edge in EDGES if edge.hypothesis == edge_id]
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="Unknown causal edge")
    return matches[0]


def context(request: Request, *, view: str, focus: str | None, target: str, sources: str) -> dict:
    dag = graph()
    if target not in dag:
        raise HTTPException(status_code=404, detail="Unknown target")
    if focus is not None and focus not in dag:
        raise HTTPException(status_code=404, detail="Unknown causal variable")
    if view == "neighborhood" and focus is None:
        focus = target
    state = store_state()
    custom = parse_sources_param(sources)
    selected = frozenset(Source(source.source) for source in state.sources if source.connected) if custom is None else custom
    available = (
        frozenset(variable for variable, summary in state.variables.items() if summary.inputs_available)
        if custom is None else observed_variables(custom)
    )
    return {
        "request": request,
        "graph_view": layout(view=view, focus=focus, target=target, observed=available),
        "view": view, "focus": focus, "target": target,
        "node_count": len(dag), "edge_count": len(EDGES),
        "evidence_count": sum(bool(edge.evidence_ids) for edge in EDGES),
        "store_connected": state.connected, "store_message": state.message,
        "sources_summary": state.sources,
        "selected_source_values": {source.value for source in selected},
        "sources_csv": sources_csv(sources),
        "is_connected_mode": custom is None,
        "available_variables": available,
        "available_count": len(available),
        "variables": state.variables,
        "node_w": NODE_W, "node_h": NODE_H,
        "search_nodes": tuple({"id": node, "label": node.replace("_", " ").capitalize(), "stage": stage_for(node).value} for node in sorted(dag)),
    }


def add_node_detail(data: dict, node_id: str) -> None:
    dag = graph()
    data.update(
        measurement=measurement_for(node_id), node_id=node_id,
        data_summary=data["variables"].get(node_id),
        parents=sorted(dag.predecessors(node_id)), children=sorted(dag.successors(node_id)),
        net_effect=net_influence(node_id, data["target"]),
    )


def graph_response(request: Request, template: str, data: dict) -> HTMLResponse:
    parameters = {key: data[key] for key in ("view", "target", "sources_csv")}
    parameters["sources"] = parameters.pop("sources_csv")
    if data["focus"]:
        parameters["focus"] = data["focus"]
    return templates.TemplateResponse(
        request, template, data, headers={"HX-Push-Url": "/?" + urlencode(parameters)},
    )


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request, view: View = "neighborhood", focus: str | None = None,
    target: str = "commercial_success", sources: str = CONNECTED,
):
    data = context(request, view=view, focus=focus, target=target, sources=sources)
    if data["focus"]:
        add_node_detail(data, data["focus"])
    return templates.TemplateResponse(request, "index.html", data)


@app.get("/graph", response_class=HTMLResponse)
def graph_partial(
    request: Request, view: View = "neighborhood", focus: str | None = None,
    target: str = "commercial_success", sources: str = CONNECTED, keep_panel: bool = False,
):
    data = context(request, view=view, focus=focus, target=target, sources=sources)
    data["keep_panel"] = keep_panel
    if data["focus"]:
        add_node_detail(data, data["focus"])
    return graph_response(request, "_graph_reset.html", data)


@app.get("/focus/{node_id}", response_class=HTMLResponse)
def focus_node(
    request: Request, node_id: str, view: View = "neighborhood",
    target: str = "commercial_success", sources: str = CONNECTED,
):
    data = context(request, view=view, focus=node_id, target=target, sources=sources)
    add_node_detail(data, node_id)
    return graph_response(request, "_focus.html", data)


@app.get("/sources", response_class=HTMLResponse)
def sources_panel(
    request: Request, view: View = "neighborhood", focus: str | None = None,
    target: str = "commercial_success", sources: str = CONNECTED,
):
    data = context(request, view=view, focus=focus, target=target, sources=sources)
    return templates.TemplateResponse(request, "_sources.html", data)


@app.get("/graph/metrics")
def graph_metrics(
    view: View = "neighborhood", target: str = "commercial_success", focus: str | None = None,
) -> dict:
    if target not in graph() or (focus is not None and focus not in graph()):
        raise HTTPException(status_code=404, detail="Unknown causal variable")
    result = _compute_layout(view, target, focus if view == "neighborhood" else None)
    return {
        "view": view, "target": target, "nodes": len(result.positions),
        "edges": len(result.edge_paths), "selected_seed": result.seed, **asdict(result.metrics),
    }


@app.get("/edge/{edge_id}", response_class=HTMLResponse)
def edge_detail(
    request: Request, edge_id: str, view: View = "neighborhood",
    target: str = "commercial_success", sources: str = CONNECTED,
    identify: bool = Query(False),
):
    edge = edge_by_id(edge_id)
    data = context(request, view=view, focus=None, target=target, sources=sources)
    data.update(
        edge=edge,
        evidence=[LITERATURE[evidence_id] for evidence_id in edge.evidence_ids],
        estimability=edge_estimability_detail(edge, data["available_variables"], identify=identify),
        identification_requested=identify,
    )
    return templates.TemplateResponse(request, "_edge_detail.html", data)


def main() -> None:
    import uvicorn

    uvicorn.run("causal_coding.web:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
