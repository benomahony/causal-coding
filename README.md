# causal-coding

A causal workbench for understanding when agentic coding creates **commercial value**, and when it merely moves bottlenecks around the software-delivery system.

The repository is still deliberately **pre-estimation**. It contains a causal theory, falsifiable hypotheses, measurement definitions, ingestion contracts, and literature evidence. It does not manufacture observations or report synthetic ATE/CATE values.

## Run the workbench

```bash
uv sync
uv run causal-coding-workbench
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

## Two graph views

The default **Commercial pathways** view is curated for reasoning rather than completeness. It keeps the principal paths to commercial success visible and readable.

**Full causal model** shows every variable and edge.

The primary graph is a force-directed layout, refined by a readability optimisation pass (minimising node overlaps, edge crossings, and overlapping/near-parallel edges) rather than a fixed grid. Selecting a node highlights its causal neighbourhood and opens its measurement definition. Selecting an edge opens its rationale and all attached supporting/contradicting literature.

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

`events.py` contains normalised ingestion contracts for engineering telemetry. Product analytics and finance are now explicit data sources in the measurement model because a delivery-only dataset cannot answer the commercial question.

### DevLake as a concrete SCM/CI/CD/issue-tracker source

`devlake/` is a real ingestion pipeline against [Apache DevLake](https://devlake.apache.org/)'s domain-layer MySQL database — DevLake exposes no query API for collected data, so this reads the domain layer directly, the same way Grafana and DevLake's own dashboards do.

- `devlake/tables.py` — read-only SQLModel mappings onto DevLake's `pull_requests`, `commits`, `cicd_tasks`, `cicd_deployments`, `issues`, `incidents` and related tables.
- `devlake/ingest.py` — `fetch_pull_requests`, `fetch_review_events`, `fetch_ci_runs`, `fetch_deployments`, `fetch_incidents`, `fetch_work_items`, each mapping DevLake rows onto this project's `events.py` contracts. Every function documents what DevLake's domain layer genuinely cannot supply (PR draft state, "required" CI check status, deployment rollback linkage, incident↔deployment attribution) rather than guessing.
- `devlake/config.py` — connection settings from `DEVLAKE_DB_HOST` / `DEVLAKE_DB_PORT` / `DEVLAKE_DB_USER` / `DEVLAKE_DB_PASSWORD` / `DEVLAKE_DB_NAME`, and `load_team_map` for a repo/project → `team_id` mapping maintained outside DevLake (the domain layer has no team concept).

Records whose repo/project isn't in the team map are dropped rather than attributed to a guessed team; `Ingested.unmapped_scope_keys` reports what was skipped so gaps in the mapping are visible instead of silently wrong. `tests/test_devlake_ingest.py` exercises every mapping function against an in-memory SQLite database shaped like DevLake's schema, so the mapping logic is verified without a live DevLake instance.

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

## Still not claimed

A citation does not make an edge universally causal. Randomised experiments, observational associations, DORA predictive relationships, queueing mechanisms and adjacent evidence remain distinguishable.

Likewise, the new commercial layer is a set of explicit causal hypotheses. The next literature pass should attack those links rather than quietly treating familiar business intuitions as established evidence.
