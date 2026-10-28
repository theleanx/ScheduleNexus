# ScheduleNexus Lab

**Contract-first production scheduling, optimization benchmarking, and separate feasibility verification.**

ScheduleNexus is a research web application based on the *Contract-First Production Scheduling* Version 7 computational artifact. It exposes the real Python research algorithms through a FastAPI backend and a responsive, dependency-free browser interface. It is **not** a plant-validated planning system, ERP/MES connector, or LLM application.

## What works

- **Schedule Workbench:** seeded synthetic scenarios; FIFO, SPT and EDD; release dates, material readiness, machine outages; strict bounded-English order command; interactive operation-level Gantt; downloadable JSON.
- **Custom scheduling API:** submit fully specified orders, routes, and downtime calendars; fail-closed Pydantic input validation and separate duration/routing/capacity checks.
- **Algorithm comparison:** three production policies on exactly the same synthetic workload and processing factors; CSV export.
- **Benchmark Lab:** six published FT/LA classical JSP benchmark instances; FIFO (job-index), SPT, MWKR and fixed-budget ARK; makespan, published optimum, gap, verification and Gantt; CSV export.
- **Experiment Studio:** paired multi-seed experiments, aggregate performance, seed-level CSV and evidence JSON.
- **External candidate verification:** submit an operation allocation to `POST /api/verify` and receive a fail-closed result after the separate schedule checker runs.
- **Evidence:** deterministic input SHA-256 hash, run ID, UTC stamp, version, verified result, optional SQLite metadata-only audit log.
- **Research & Provenance:** first-party research page with benchmark citations, upstream attribution, integrity fingerprints and rights disclosures.
- **Reproducibility:** Dockerfile, Compose, API schema/docs, CI and automated regression tests.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
python -m pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 or API documentation at http://127.0.0.1:8000/api/docs.

With Docker:

```bash
docker compose up --build
```

The supplied Compose configuration binds to **127.0.0.1 only**. Do not expose a publicly accessible service without a TLS reverse proxy, authentication, external rate limiting, request and concurrency quotas, central logs and deployment-specific security testing. The API key setting is intended for an authenticated gateway; the default unauthenticated browser is a local demo.

## API routes

| Route | Purpose |
|---|---|
| `GET /api/health`, `/api/catalog`, `/api/example` | Health, supported models, validated example input |
| `POST /api/synthetic` | Seeded synthetic production schedule |
| `POST /api/schedule` | User-specified, typed production schedule |
| `POST /api/verify` | Validate an externally supplied candidate schedule |
| `POST /api/commands/parse` | Bounded-English parsing, no inferred values |
| `POST /api/compare` | Paired FIFO/SPT/EDD schedule comparisons |
| `POST /api/batch` | Bounded multi-seed experiment |
| `POST /api/benchmark` | One classical JSP policy/instance |
| `POST /api/benchmark/compare` | Four classical JSP policies |
| `GET /api/runs`, `/api/research/disclosure` | Audit and model disclosures |
| `GET /api/research/provenance` | Benchmark source attribution, reference optima, local SHA-256 fingerprints and rights status |

## Important model distinctions

**Production model:** one each of CUT/CNC/ASM/QC, material and order release times, fixed routing, nonpreemptive scheduling, and outage calendars. The production track's FIFO is *ready-time priority*. Workloads are synthetic or explicitly entered by the user. `parse_order` is a strict grammar, **not** an LLM.

**Classical JSP model:** FT06 and Lawrence LA01–LA05 with job-index FIFO, SPT, MWKR and bounded annealed random-key (`ARK1500` family), no releases, due dates, material gates or outages. Only the original no-setup case is comparable with published optima. One stochastic seed is not a statistically characterized search comparison. Original ARK parameter-tuning independence could not be documented.

**Verification:** the production scheduler and verifier use separate code paths, but share schema and time/resource modeling assumptions. Feasibility is checked for supported modeled constraints. This does not establish industrial suitability or general optimality.

## Provenance and attribution

Core algorithms are adapted without reimplementing the logic from the Version 7 research artifact supplied for ScheduleNexus. Benchmark instances were transcribed in that artifact from the [JSPLIB repository](https://github.com/tamy0612/JSPLIB). Their original sources include Fisher & Thompson (1963) and Lawrence (1984). Benchmark data redistribution rights should be reviewed by the repository owner before licensing and public release; attribution is not a substitute for permission. The original research manuscript/source figures are intentionally not bundled in this code distribution.

See [research provenance](docs/RESEARCH_PROVENANCE.md), [researcher guide](docs/RESEARCHER_GUIDE.md), [external release checklist](docs/EXTERNAL_RELEASE_CHECKLIST.md) and [security policy](SECURITY.md). Third-party links live on the internal **Research & Provenance** page, not in the application sidebar.

## License & release readiness

No software license is asserted here pending the author's explicit license selection and third-party benchmark-data review. Without a license, users cannot assume rights to reuse, modify, or redistribute the software. To make this genuinely open source, choose an OSI-approved license, complete the benchmark review, and archive a tagged release at Zenodo or an equivalent persistent repository. **No DOI or live public deployment is claimed.** Review the mandatory gates in `docs/EXTERNAL_RELEASE_CHECKLIST.md` before soliciting unrestricted external use. A public repository is not automatically an open-source release or secure multi-user service.

## Production-hardening limitations

The current runnable reference service uses bounded synchronous optimization, in-process rate limiting and a local SQLite audit. It does **not** yet provide multi-tenant identity, background queues, distributed quotas, asynchronous cancellation, external observability, penetration testing, or cloud load-test evidence. These must be added for an unrestricted public launch.

## Reproduce the paper's extended computations

The `research/` directory also includes the original Version 7 stand-alone experiment scripts (synthetic, sensitivity, external benchmark, fault-injection, subset MILP, holdout, multi-seed ARK and figure generator). These are **separate, heavier** research reproductions and not all run through the synchronous demo API. Install the optional analysis dependencies and run:

```bash
pip install -r requirements-research.txt
bash scripts/reproduce_paper.sh
```

The scripts write computed artifacts under `research/data/` and figures in `research/figures/` (intentionally gitignored). Long-running commands are not executed automatically by the website. Existing paper numeric claims must be validated against the specific version, seeds, inputs, and solver environment listed in the manuscript.
