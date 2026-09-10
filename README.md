# causal-coding

A causal workbench for understanding when agentic coding creates **commercial value**, and when it merely moves bottlenecks around the software-delivery system.

The repository is still deliberately **pre-estimation**. It contains a causal theory, falsifiable hypotheses, measurement definitions, ingestion contracts, and literature evidence. It does not manufacture observations or report synthetic ATE/CATE values.

## Run the workbench

```bash
uv sync
uv run ccw
```

Open <http://127.0.0.1:8000>.

The UI is **FastAPI + Jinja + HTMX**. There is no SPA framework and no generic force-directed graph renderer. The causal model stays plain Python; FastAPI exposes server-rendered graph, node and evidence views; HTMX swaps those partials in place.

## The question is commercial, not merely technical

The graph now has an explicit causal spine:

```text
Agent → Task & context → Codebase & team → Engineering flow
      → Delivery → Product → Commercial
```

`commercial_success` is the default target. Revenue, gross margin and retention feed it. The DORA-style delivery measures — lead time, deployment frequency, change failure rate, recovery time and deployment rework — are **intermediate mechanisms**, not the objective.

This makes competing paths visible. An agent can reduce implementation effort and engineering cost, increase experiment frequency and product learning, or increase change volume, failures, recovery burden and cost-to-serve. The workbench exists to make those hypotheses explicit and testable.

The new product/commercial edges are intentionally marked as hypotheses pending the next literature pass; they are not presented as established causal facts.

## Explore the model

The default **Focus view** starts at commercial success and shows only its direct causes and effects. Select a variable in the diagram or the details panel to explore its neighborhood. **Key pathways** provides a curated overview; **Full model** shows all 70 variables.

Use the search box (or press `/`) to find any variable. Drag the background to pan, scroll or pinch to zoom, and press `0` to fit the graph. Graph nodes and links support keyboard focus and Enter/Space activation. The URL preserves the selected view, focus and source mode for refreshes and sharing.

The graph uses deterministic layered placement. A separate, scrollable details panel keeps the diagram unobstructed. Selecting a link opens its rationale and supporting/contradicting literature. Slow DoWhy identification runs only when requested from the advanced section. Assets are served locally; the workbench does not need a CDN or external fonts.

Evidence is visually distinguished as:

- literature supported;
- mixed / contradictory;
- mechanistic;
- untested hypothesis.

## Model size

The current model contains 70 variables and 91 causal links. All graph variables have measurement definitions. The commercial extension adds candidate observations for experimentation, time-to-customer-value, product reliability, learning, customer value, adoption, retention, revenue, engineering cost, cost-to-serve, gross margin and commercial success.

`commercial_success` is deliberately a **decision target / latent utility**, not a canonical metric. The component outcomes should stay separate when we eventually estimate effects.

## Evidence model

Every edge can reference multiple literature records. Evidence preserves study design and disagreement rather than collapsing everything into a confidence score:

```python
LiteratureEvidence(
    citation=...,
    evidence_type="randomized_experiment",
    relation="supports",       # contradicts / mixed / adjacent
    directness="direct",       # mediated / analogous
    population=...,
    intervention=...,
    outcome=...,
    finding=...,
)
```

For example, the AI-productivity portion retains both Peng et al.'s positive controlled result and Becker et al./METR's negative result for experienced maintainers. The graph therefore models agent value as heterogeneous across task and repository context.

Run the evidence backlog with:

```bash
uv run causal-coding-evidence
```

## Measurement and ingestion

`measurements.py` maps every causal variable to candidate measurements with source, grain, observability, raw input fields, derivation and caveats.

`events.py` contains validated SQLModel ingestion contracts for engineering telemetry. Product analytics and finance are explicit data sources because a delivery-only dataset cannot answer the commercial question.

### Live inputs versus source previews

**Data sources → Apply source preview** asks which variables the selected categories could potentially support. **Clear all** means no sources; **Use live data** is a separate action.

Live coverage checks per-metric tables and required fields. A revenue record cannot unlock cost records or gross margin. Proxy-only constructs and latent targets are never counted as directly observed. Missing instrumentation and measurements requiring joins remain explicit gaps. Rows marked `source_system="fixtures"` are reported separately and excluded from live coverage.

Even complete raw inputs are **not an estimation-ready dataset**. Derivations, scope and time alignment, sample size, overlap and causal assumptions must still be validated. The graph's collection checklist and hypothetical source coverage make no claim that an effect is estimable. Formal identification concerns total effects under the specified DAG, not necessarily the direct arrow alone.

### Initialise or upgrade the store

The workbench works without a database. To persist events locally:

```bash
docker compose up -d postgres
export CAUSAL_STORE_DB_HOST=127.0.0.1
export CAUSAL_STORE_DB_PORT=5433
export CAUSAL_STORE_DB_USER=causal_coding
export CAUSAL_STORE_DB_PASSWORD=causal_coding
export CAUSAL_STORE_DB_NAME=causal_coding
uv run ccdb
uv run ccw
```

`ccdb` creates or upgrades this project's tables only. The upgrade preserves event history, adds PR commit linkage, and makes unavailable PR/CI fields nullable. Legacy DevLake sizes and draft/required-check flags that were inferred are cleared once; re-ingest to populate trustworthy values. PostgreSQL and SQLite upgrades are supported. It never migrates the external DevLake database.

`uv run ccs` optionally adds deterministic test fixtures. Fixtures do not establish real input coverage. Missing tables, unavailable databases and invalid connection settings leave theory exploration and source previews usable.

The Compose database binds only to `127.0.0.1`. Its example credentials are for local development, not a shared deployment. Keep real credentials in your shell environment or an ignored `.env` file; the application does not automatically load `.env` files.

### DevLake as a concrete SCM/CI/CD/issue-tracker source

`devlake/` is a real ingestion pipeline against [Apache DevLake](https://devlake.apache.org/)'s domain-layer MySQL database — DevLake exposes no query API for collected data, so this reads the domain layer directly, the same way Grafana and DevLake's own dashboards do.

- `devlake/tables.py` — read-only SQLModel mappings onto DevLake's `pull_requests`, `commits`, `cicd_tasks`, `cicd_deployments`, `issues`, `incidents` and related tables.
- `devlake/ingest.py` — reads PR-level additions/deletions and draft state from the current domain schema (requires DevLake's July 2024 PR migrations). It preserves historical PR commit associations and merge SHAs. Commit churn is never summed into final PR size; unavailable final file paths, required-check flags and deployment attribution remain unknown.
- `devlake/config.py` — connection settings from `DEVLAKE_DB_HOST` / `DEVLAKE_DB_PORT` / `DEVLAKE_DB_USER` / `DEVLAKE_DB_PASSWORD` / `DEVLAKE_DB_NAME`, and `load_team_map` for a repo/project → `team_id` mapping maintained outside DevLake (the domain layer has no team concept).

Records whose repo/project isn't in the team map are dropped rather than attributed to a guessed team; `Ingested.unmapped_scope_keys` reports what was skipped so gaps in the mapping are visible instead of silently wrong. `tests/test_devlake_ingest.py` exercises every mapping function against an in-memory SQLite database shaped like DevLake's schema, so the mapping logic is verified without a live DevLake instance.

For PRs, CI runs, deployments and incidents, `since` is an inclusive **update watermark**. Creation, update and completion timestamps are considered; records without update metadata are conservatively refreshed. `observed_at` records snapshot collection time and can be supplied explicitly by the caller. Capture the next watermark before reading; overlapping snapshots are expected in the append-only store.

`store/joins.py:deployed_changes()` joins the latest real PR and deployment snapshots by persisted commit identity, prefers merge SHAs, requires matching source/team and successful production delivery, and avoids double-counting redeployments. Historical PR associations can include rebased commits, so fallback attribution and the earliest linked commit still need validation against the source repository.

Prospective instrumentation remains particularly important for:

- agent session ↔ engineer ↔ task ↔ PR linkage;
- human intervention / approval / takeover events;
- context supplied to agents and its freshness;
- review active time versus queue time;
- deployment ↔ incident / rollback attribution;
- product decision ↔ deployment ↔ customer-value linkage;
- finance/product scope identifiers allowing engineering changes to join to commercial outcomes.

## Structure

```text
src/causal_coding/
├── model.py              # causal DAG and evidence-bearing edges
├── workbench.py          # semantic stages + deterministic graph layout
├── web.py                # FastAPI/HTMX workbench routes
├── templates/            # server-rendered graph and inspector partials
├── static/               # workbench presentation
├── hypotheses.py         # falsifiable higher-level hypotheses
├── evidence.py           # literature records and evidence taxonomy
├── evidence_report.py    # literature coverage / research backlog
├── measurements.py       # causal variables -> observations
├── events.py             # normalised engineering event contracts
├── devlake/              # DevLake domain-layer ingestion (SCM, CI, CD, issue tracker)
├── data_requirements.py  # collection requirements
└── dowhy_model.py        # DoWhy representation for later causal work
```

## Tests

```bash
uv run pytest
```

The suite checks DAG validity, measurement coverage, evidence referential integrity, contradictory-evidence semantics, structural decompositions, the commercial-success paths, workbench routes, HTMX partials and semantic graph layout.

Install the test tools with `uv sync --extra dev`. Run `uv run ruff check src tests` for lint. Regression tests cover sparse data, unknown fields, fixture exclusion, database failure, credential escaping, incremental updates, joins and legacy schema upgrades.

To also exercise the PostgreSQL migration, set `CAUSAL_TEST_DB_URL` to a disposable PostgreSQL database URL before running `uv run pytest tests/test_postgres.py`. This test creates and removes a uniquely named schema; the database user needs permission to create schemas. Without the setting, it is skipped.

The browser smoke test covers search, navigation, source previews, refresh/history, keyboard controls, mobile layout, offline assets and failed requests. With the workbench running and Node.js installed:

```bash
npm install --prefix /tmp/causal-browser-check playwright
/tmp/causal-browser-check/node_modules/.bin/playwright install chromium
WORKBENCH_URL=http://127.0.0.1:8000 node tests/browser_smoke.cjs /tmp/causal-browser-check/node_modules/playwright
```

`PLAYWRIGHT_BROWSER_PATH` can select an existing Chromium executable. Browser screenshots are saved to `/tmp/causal-coding-desktop.png` and `/tmp/causal-coding-mobile.png`.

Export a standalone HTML/SVG model without optional plotting packages:

```bash
uv run causal-coding-graph --view full --output /tmp/causal-model.html
```

The original `causal-coding-workbench` and `causal-coding-evidence` command names remain supported aliases for `ccw` and `cce`.

## Before pushing

```bash
uv sync --locked --extra dev
uv run --locked pytest
uv run --locked ruff check src tests
uv build
git diff --check
git diff --cached --check
git status --short
```

Commit the source, templates, static assets, tests and `uv.lock` together. Keep secrets, local databases, bytecode, test reports and generated graph exports out of Git. `.gitignore` covers these artifacts but does not untrack files that were already committed. Review both staged and unstaged changes before committing; new regression tests must be included alongside their fixes.

## Still not claimed

A citation does not make an edge universally causal. Randomised experiments, observational associations, DORA predictive relationships, queueing mechanisms and adjacent evidence remain distinguishable.

Likewise, the new commercial layer is a set of explicit causal hypotheses. The next literature pass should attack those links rather than quietly treating familiar business intuitions as established evidence.
