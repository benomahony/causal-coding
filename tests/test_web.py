from fastapi.testclient import TestClient

from causal_coding.measurements import Source
from causal_coding.web import app
from causal_coding.workbench import OVERVIEW_NODES, layout

client = TestClient(app)


def test_workbench_home_makes_commercial_goal_explicit() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "When does agentic coding create value?" in response.text
    assert "Commercial success" in response.text


def test_view_controls_offer_focus_pathways_and_full_graph() -> None:
    response = client.get("/")
    assert all(label in response.text for label in ("Focus view", "Key pathways", "Full model"))


def test_brand_uses_a_local_vector_and_accessible_home_link() -> None:
    response = client.get("/")
    assert 'aria-label="Causal coding home"' in response.text
    assert 'class="brand-wordmark"' in response.text
    assert 'class="brand-mark"' not in response.text
    assert 'rel="icon" type="image/svg+xml"' in response.text
    assert "/static/causal-signal.svg" in response.text
    mark = client.get("/static/causal-signal.svg")
    assert mark.status_code == 200
    assert mark.headers["content-type"].startswith("image/svg+xml")
    assert 'viewBox="0 0 40 40"' in mark.text


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


def test_default_view_is_a_readable_commercial_neighborhood() -> None:
    response = client.get("/")
    assert 'data-view="neighborhood"' in response.text
    assert response.text.count('class="node ') == 4
    assert response.text.count('class="edge ') == 3


DEVLAKE_SOURCES = ",".join(sorted(["scm", "ci", "cd", "issue_tracker", "incident_management"]))
ALL_SOURCES = ",".join(sorted(s.value for s in Source))


def test_custom_source_filter_needs_no_live_store() -> None:
    """An explicit source combination is purely structural -- must work with no store connected."""
    response = client.get(f"/graph?view=full&sources={DEVLAKE_SOURCES}")
    assert response.status_code == 200
    assert 'id="graph-panel"' in response.text
    assert f'data-sources="{DEVLAKE_SOURCES}"' in response.text


def test_graph_partial_oob_updates_the_header_coverage_tag() -> None:
    """The header (with the coverage stat) is never itself swapped by htmx -- /graph must
    ship an out-of-band update for #coverage-tag or switching the source filter leaves the
    header showing a stale number."""
    response = client.get(f"/graph?view=full&sources={DEVLAKE_SOURCES}")
    assert 'id="coverage-tag"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert f'data-sources="{DEVLAKE_SOURCES}"' in response.text
    assert "Hypothetical source preview" in response.text


def test_custom_source_filter_shown_in_header_stat() -> None:
    response = client.get(f"/?sources={DEVLAKE_SOURCES}")
    assert response.status_code == 200
    assert "Hypothetical source preview" in response.text
    assert "scm" in response.text


def test_source_preview_does_not_claim_estimates_are_available() -> None:
    response = client.get(f"/?sources={ALL_SOURCES}")
    assert "Potential coverage only" in response.text
    assert "edges estimable" not in response.text


def test_no_named_presets_remain_in_the_filter_ui() -> None:
    """The filter must be the general Source-combination mechanism, not hardcoded presets."""
    response = client.get("/sources")
    assert "devlake" not in response.text.lower()
    assert 'id="sources-form"' in response.text
    assert 'type="checkbox"' in response.text


def test_sources_panel_renders() -> None:
    response = client.get("/sources")
    assert response.status_code == 200
    assert "DATA SOURCES" in response.text
