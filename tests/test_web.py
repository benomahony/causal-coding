from fastapi.testclient import TestClient

from causal_coding.web import app
from causal_coding.workbench import OVERVIEW_NODES, layout


client = TestClient(app)


def test_workbench_home_makes_commercial_goal_explicit() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Does agentic coding create commercial value?" in response.text
    assert "Commercial success" in response.text
    assert "Commercial pathways" in response.text


def test_graph_partial_is_htmx_swappable() -> None:
    response = client.get("/graph?view=overview")
    assert response.status_code == 200
    assert 'id="graph-panel"' in response.text
    assert "commercial success" in response.text


def test_node_focus_returns_graph_and_oob_inspector() -> None:
    response = client.get("/focus/agentic_task_share?view=overview")
    assert response.status_code == 200
    assert 'hx-swap-oob="innerHTML"' in response.text
    assert "agentic task share" in response.text


def test_edge_detail_exposes_evidence() -> None:
    response = client.get("/edge/K6")
    assert response.status_code == 200
    assert "Peng et al." in response.text
    assert "Becker et al." in response.text
    assert "heterogeneous" in response.text


def test_overview_is_smaller_than_full_model() -> None:
    overview = layout("overview")
    full = layout("full")
    assert len(overview.nodes) == len(OVERVIEW_NODES)
    assert len(overview.nodes) < len(full.nodes)


def test_commercial_success_is_in_rightmost_stage() -> None:
    view = layout("overview")
    target = next(node for node in view.nodes if node.id == "commercial_success")
    assert target.target is True
    assert target.stage.value == "Commercial"
