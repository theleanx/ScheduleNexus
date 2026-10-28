# Researcher quick-start and experiment protocol

## 1. Run a local reference server

Python 3.11–3.13:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`; API definitions are at `/api/docs`. The Docker alternative is `docker compose up --build` (binds only to local loopback). Do not put the reference service directly on a public network. Do not upload sensitive plant or customer information to an unfamiliar hosted instance.

## 2. Schedule Workbench (functional demonstration)

Choose Machine disruption, EDD, seed `202600`, 32 orders; leave optional order/custom JSON checkboxes unchecked and click **Run verified schedule**. Check modeled feasibility, operation-level Gantt, four KPIs and JSON download. Repeat unchanged to confirm the operations and KPIs match; timestamps and run IDs will differ.

## 3. Algorithm Comparison (paired single workload)

Run `machine_disruption`, seed `202600`, count `32`. Review all three policies (FIFO/SPT/EDD), their verifier status, mean tardiness, on-time percentage, mean flow time, and makespan. CSV export includes one row per policy. This is **one** paired workload, not a confidence interval or proof of superior performance.

## 4. Classical job-shop benchmark

Choose `ft06`, seed `2100`, 500 proposals for a **smoke test**. Review four methods and confirm the benchmark reference of 55. Record makespan and gap, inspect the best Gantt and CSV evidence. Rerun with 1,500 proposals to use the paper's ARK proposal budget. `ARK1500` is a method family name in the API—even when the preview was run at 500 proposals—and the `iterations` result field records the actual budget. Do not cite a 500-proposal result as a 1,500-proposal result.

## 5. Multi-seed experiment

In Experiment Studio choose the scenario and first seed, number of replications and order count; compare all three policies using the same seed for each replication. Download CSV/JSON evidence. The web studio covers **production track** policies only. The paper's full public benchmark 20-seed ARK audit is reproduced using dedicated research scripts, not via a one-click job-shop browser experiment.

## 6. External schedule verification

In Evidence & Audit, **Load sample**, then **Verify schedule**; alter one operation duration or create an overlap and rerun to confirm fail-closed rejection. This checker evaluates only the documented fixed-route production model.

## 7. Research data and source context

Visit **Research & Provenance** to inspect each benchmark's integrity fingerprint and original citations. Store the full local SHA-256 digest, not only the shortened UI display. For repeatable publications, retain your source commit SHA and versions of Python and installed dependencies; `requirements.txt` specifies compatible ranges, not a byte-for-byte locked environment.

## 8. Report an issue

Open an issue in the [ScheduleNexus repository](https://github.com/theleanx/ScheduleNexus/issues). Include platform/runtime versions, the exact request parameters, expected/actual behavior, and relevant error output. Omit proprietary or personal data. Research results should include declared method names and budgets, not inferred or invented metrics.
