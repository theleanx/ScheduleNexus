"""ScheduleNexus research API.
No user-supplied Python, shell, model code, or remote URL is executed.
Job-shop and production-planning schemas intentionally remain distinct.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from research import planner_core as prod
from research import external_benchmarks as jsp

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
app = FastAPI(title="ScheduleNexus Lab API", version=VERSION, description="Contract-first, verifier-gated scheduling research platform", docs_url="/api/docs", openapi_url="/api/openapi.json")
# Browser UI and API normally share an origin. Restrictive default CORS.
_origins = [o for o in os.getenv("SCHEDULENEXUS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"])

class StepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine: Literal["CUT", "CNC", "ASM", "QC"]
    hours_per_unit: float = Field(gt=0, le=100)

class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9-]+$")
    quantity: int = Field(ge=1, le=1000)
    release: float = Field(ge=0, le=100000)
    due: float = Field(ge=0, le=100000)
    material_ready: float = Field(ge=0, le=100000)
    route: list[StepInput] = Field(min_length=1, max_length=20)

class CalendarInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: float = Field(ge=0, le=100000)
    end: float = Field(gt=0, le=100000)

class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: Literal["FIFO", "SPT", "EDD"] = "EDD"
    orders: list[OrderInput] = Field(min_length=1, max_length=100)
    outages: dict[str, list[CalendarInterval]] = Field(default_factory=dict)

class OperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9-]+$")
    stage: int = Field(ge=0, le=19)
    machine: Literal["CUT", "CNC", "ASM", "QC"]
    start: float = Field(ge=0, le=100000)
    end: float = Field(gt=0, le=100000)
    duration: float = Field(gt=0, le=100000)

class VerifyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orders: list[OrderInput] = Field(min_length=1, max_length=100)
    operations: list[OperationInput] = Field(min_length=1, max_length=2000)
    outages: dict[str, list[CalendarInterval]] = Field(default_factory=dict)

class SyntheticInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["baseline", "material_delay", "machine_disruption"] = "machine_disruption"
    policy: Literal["FIFO", "SPT", "EDD"] = "EDD"
    seed: int = Field(default=202600, ge=0, le=10000000)
    count: int = Field(default=32, ge=2, le=100)
    command: str | None = Field(default=None, max_length=2000)

class CompareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["baseline", "material_delay", "machine_disruption"] = "machine_disruption"
    seed: int = Field(default=202600, ge=0, le=10000000)
    count: int = Field(default=32, ge=2, le=100)

class BatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["baseline", "material_delay", "machine_disruption"] = "machine_disruption"
    first_seed: int = Field(default=300000, ge=0, le=9999990)
    replications: int = Field(default=10, ge=2, le=30)
    count: int = Field(default=32, ge=2, le=64)

class BenchmarkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance: Literal["ft06", "la01", "la02", "la03", "la04", "la05"] = "ft06"
    method: Literal["FIFO", "SPT", "MWKR", "ARK1500"] = "ARK1500"
    seed: int = Field(default=2100, ge=0, le=10000000)
    iterations: int = Field(default=500, ge=10, le=1500)
    setup_hours: float = Field(default=0, ge=0, le=10)

class BenchmarkCompareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance: Literal["ft06", "la01", "la02", "la03", "la04", "la05"] = "ft06"
    seed: int = Field(default=2100, ge=0, le=10000000)
    iterations: int = Field(default=500, ge=10, le=1500)

class ValidateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(min_length=1, max_length=2000)

# Lower operational limits than the original batch research script, suitable for public demonstrations.
# In-memory IP rate limits supplement infrastructure-layer quotas, not replace them.
_recent: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()

def guard(request: Request):
    key = os.getenv("SCHEDULENEXUS_API_KEY", "")
    if key and request.headers.get("X-API-Key", "") != key:
        raise HTTPException(401, "API key required")
    # Do not trust user-supplied forwarded-for headers; reverse proxies must set client correctly.
    peer = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _rate_lock:
        q = _recent[peer]
        while q and now - q[0] > 60: q.popleft()
        if len(q) >= int(os.getenv("SCHEDULENEXUS_RPM", "60")):
            raise HTTPException(429, "Request rate limit reached; retry after 60 seconds")
        q.append(now)

# Read-only provenance log: no raw user orders/commands are written to disk.
_db_lock = threading.Lock()
def db_path() -> Path:
    return Path(os.getenv("SCHEDULENEXUS_DB", str(ROOT / "data" / "runs.db")))

def audit(kind: str, request_data: dict, summary: dict) -> dict:
    stamp = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(json.dumps(request_data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    record = {"id": uuid.uuid4().hex[:14], "timestamp_utc": stamp, "input_sha256": digest,
              "engine_version": VERSION, "kind": kind, "status": "verified"}
    if os.getenv("SCHEDULENEXUS_AUDIT", "1") == "1":
        path = db_path()
        try:
            with _db_lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(path, timeout=3) as conn:
                    conn.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, input_sha256 TEXT NOT NULL, summary_json TEXT NOT NULL)")
                    conn.execute("INSERT INTO runs VALUES (?,?,?,?,?)", (record["id"], stamp, kind, digest, json.dumps(summary, sort_keys=True, allow_nan=False)))
        except (OSError, sqlite3.Error):
            record["audit_persisted"] = False
        else:
            record["audit_persisted"] = True
    else:
        record["audit_persisted"] = False
    return record

def to_orders(items: list[OrderInput]):
    return [prod.Order(j.id, j.quantity, j.release, j.due, j.material_ready,
                       tuple(prod.Step(s.machine, s.hours_per_unit) for s in j.route)) for j in items]

def to_outages(items: dict[str, list[CalendarInterval]]):
    if sum(len(v) for v in items.values()) > 40:
        raise prod.PlanningError("too many outage intervals")
    return {k: [(x.start, x.end) for x in v] for k, v in items.items()}

def as_prod_result(jobs, ops, outages, policy, kind, request_data, scenario=None):
    # Explicit contracted durations: no unspecified stochastic duration substitution.
    if not prod.verify_schedule(jobs, ops, outages):
        raise AssertionError("separate verifier did not pass")
    # Additional duration checking when no noise is used.
    info = prod.metrics(jobs, ops)
    record = audit(kind, request_data, {"mean_tardiness": info["mean_tardiness"], "makespan": info["makespan"], "n_orders": len(jobs)})
    return {"run": record, "model": "production", "scope": "synthetic or user-specified; not plant-validated", "policy": policy,
            "scenario": scenario, "orders": [asdict(x) for x in jobs], "operations": [asdict(x) for x in ops],
            "outages": outages, "metrics": info, "verified": True, "optimality_proven": False}

@app.exception_handler(prod.PlanningError)
async def invalid_plan(request: Request, exc: prod.PlanningError):
    return JSONResponse({"detail": str(exc)}, status_code=422)

@app.exception_handler(AssertionError)
async def invalid_result(request: Request, exc: AssertionError):
    return JSONResponse({"detail": "Schedule failed separate verification", "status": "rejected"}, status_code=422)

@app.get("/")
def index(): return FileResponse(ROOT / "static" / "index.html", media_type="text/html")

@app.get("/assets/styles.css")
def styles(): return FileResponse(ROOT / "static" / "styles.css", media_type="text/css")

@app.get("/assets/app.js")
def script(): return FileResponse(ROOT / "static" / "app.js", media_type="text/javascript")

@app.get("/api/health")
def health(): return {"status": "ok", "name": "ScheduleNexus", "version": VERSION, "research_only": True}

@app.get("/api/catalog")
def catalog():
    return {"name": "ScheduleNexus Lab", "version": VERSION,
            "models": [{"id": "production", "policies": list(prod.POLICIES), "machines": list(prod.MACHINES),
                        "constraints": ["routing precedence", "single machine capacity", "material/release gates", "outages", "processing duration"]},
                       {"id": "jsp", "policies": ["FIFO", "SPT", "MWKR", "ARK1500"], "constraints": ["routing precedence", "single machine capacity", "optional family setups"]}],
            "benchmarks": [{"name": k, "published_optimum": v} for k, v in jsp.OPT.items()],
            "disclosure": "No LLM, ERP/MES or plant calibration. Published JSP instances use a separate model without release dates or outages."}

@app.get("/api/example")
def example():
    orders = prod.synthetic_orders(202600, 8, "baseline")
    return {"policy": "EDD", "orders": [asdict(x) for x in orders], "outages": {}}

@app.post("/api/commands/parse", dependencies=[Depends(guard)])
def parse_command(req: ValidateCommand):
    job = prod.parse_order(req.command)
    return {"valid": True, "order": asdict(job), "source": "strict bounded grammar; no LLM"}

@app.post("/api/schedule", dependencies=[Depends(guard)])
def custom_schedule(req: ScheduleInput):
    jobs = to_orders(req.orders)
    outages = to_outages(req.outages)
    prod.validate_orders(jobs, outages)
    ops = prod.schedule(jobs, req.policy, outages)
    # Contracted duration check is distinct from policy choice.
    factors = {(job.id, i): 1.0 for job in jobs for i in range(len(job.route))}
    prod.verify_schedule(jobs, ops, outages, processing_factors=factors)
    return as_prod_result(jobs, ops, outages, req.policy, "custom_schedule", req.model_dump(mode="json"))

@app.post("/api/verify", dependencies=[Depends(guard)])
def verify_candidate(req: VerifyInput):
    """Validate an external candidate schedule against the supported fixed-route contract.
    Unlike the scheduler, this endpoint accepts user-supplied operation allocations.
    """
    jobs = to_orders(req.orders)
    outages = to_outages(req.outages)
    prod.validate_orders(jobs, outages)
    ids = {j.id for j in jobs}
    for op in req.operations:
        if op.order not in ids:
            raise prod.PlanningError("operation references an unknown order")
    ops = [prod.Operation(o.order, o.stage, o.machine, o.start, o.end, o.duration)
           for o in req.operations]
    factors = {(j.id, i): 1.0 for j in jobs for i in range(len(j.route))}
    prod.verify_schedule(jobs, ops, outages, processing_factors=factors)
    m = prod.metrics(jobs, ops)
    record = audit("external_verify", req.model_dump(mode="json"),
                   {"n_orders": len(jobs), "n_operations": len(ops), "makespan": m["makespan"]})
    return {"run": record, "verified": True, "model": "production",
            "operations_checked": len(ops), "metrics": m,
            "disclosure": "Only contracted production-model constraints were evaluated; this does not verify data provenance or plant suitability"}

@app.post("/api/synthetic", dependencies=[Depends(guard)])
def synthetic(req: SyntheticInput):
    jobs = prod.synthetic_orders(req.seed, req.count, req.scenario)
    if req.command:
        more = prod.parse_order(req.command)
        if any(j.id == more.id for j in jobs): raise prod.PlanningError("duplicate order ID")
        jobs.append(more)
    outages = prod.scenario_outages(req.scenario)
    # Use deterministic, recorded processing factors; verifier rechecks expected durations.
    factors = prod.processing_noise(jobs, req.seed)
    ops = prod.schedule(jobs, req.policy, outages, factors)
    prod.verify_schedule(jobs, ops, outages, factors)
    result = as_prod_result(jobs, ops, outages, req.policy, "synthetic", req.model_dump(mode="json"), req.scenario)
    result["seed"] = req.seed
    result["processing_factors_sha256"] = hashlib.sha256(json.dumps(sorted((k[0],k[1],v) for k,v in factors.items())).encode()).hexdigest()
    return result

@app.post("/api/compare", dependencies=[Depends(guard)])
def compare(req: CompareInput):
    jobs = prod.synthetic_orders(req.seed, req.count, req.scenario)
    outages = prod.scenario_outages(req.scenario)
    factors = prod.processing_noise(jobs, req.seed)
    results = []
    schedules = {}
    for policy in prod.POLICIES:
        ops = prod.schedule(jobs, policy, outages, factors)
        prod.verify_schedule(jobs, ops, outages, factors)
        results.append({"method": policy, **prod.metrics(jobs, ops), "verified": True})
        schedules[policy] = [asdict(x) for x in ops]
    record = audit("compare", req.model_dump(), {"n_orders": req.count, "results": results})
    return {"run": record, "model": "production", "scenario": req.scenario, "seed": req.seed,
            "rows": results, "schedules": schedules, "outages": outages,
            "verified": True, "scope": "synthetic paired workload; no optimization guarantee"}

@app.post("/api/batch", dependencies=[Depends(guard)])
def batch(req: BatchInput):
    rows = []
    for seed in range(req.first_seed, req.first_seed + req.replications):
        jobs = prod.synthetic_orders(seed, req.count, req.scenario)
        outages = prod.scenario_outages(req.scenario)
        factors = prod.processing_noise(jobs, seed)
        for policy in prod.POLICIES:
            ops = prod.schedule(jobs, policy, outages, factors)
            prod.verify_schedule(jobs, ops, outages, factors)
            m = prod.metrics(jobs, ops)
            rows.append({"seed": seed, "method": policy, "mean_tardiness": round(m["mean_tardiness"], 6),
                         "on_time_pct": round(m["on_time_pct"], 6), "makespan": round(m["makespan"], 6),
                         "mean_flow_time": round(m["mean_flow_time"], 6), "verified": True})
    summary = []
    for pol in prod.POLICIES:
        p = [r for r in rows if r["method"] == pol]
        summary.append({"method": pol, **{k: sum(z[k] for z in p)/len(p) for k in ("mean_tardiness", "on_time_pct", "makespan", "mean_flow_time")}})
    paired = [next(r["mean_tardiness"] for r in rows if r["seed"]==s and r["method"]=="EDD")
              - next(r["mean_tardiness"] for r in rows if r["seed"]==s and r["method"]=="FIFO")
              for s in range(req.first_seed, req.first_seed+req.replications)]
    record = audit("batch", req.model_dump(), {"replications": req.replications, "n_records": len(rows)})
    return {"run": record, "rows": rows, "summary": summary, "paired_edd_minus_fifo": paired,
            "n_replications": req.replications, "verified": True, "exploratory": True,
            "disclosure": "Paired synthetic replications; not prospective preregistration or industrial validation"}

def jsp_result(name: str, method: str, seed: int, iterations: int, setup_hours: float):
    jobs, nm = jsp.load_instance(name)
    if method == "ARK1500":
        ops, accepted = jsp.annealed_random_keys(jobs, nm, seed=seed, steps=iterations, setup_hours=setup_hours)
    else:
        ops = jsp.greedy(jobs, nm, method, setup_hours=setup_hours)
        accepted = None
    jsp.check(jobs, nm, ops, setup_hours=setup_hours)
    score = jsp.quality(ops)
    optimal = jsp.OPT[name] if setup_hours == 0 else None
    return {"method": method, "instance": name, "seed": seed if method == "ARK1500" else None,
            "iterations": iterations if method == "ARK1500" else 1,
            "accepted_moves": accepted, "jobs": len(jobs), "machines": nm, "operations_count": len(ops),
            "makespan": score, "published_no_setup_optimum": optimal,
            "gap_pct": 100*(score-optimal)/optimal if optimal is not None else None,
            "setup_hours": setup_hours, "benchmark_sha256": hashlib.sha256((ROOT / "benchmarks" / f"{name}.txt").read_bytes()).hexdigest(), "verified": True, "optimality_proven": optimal is not None and abs(score-optimal)<1e-8,
            "operations": [asdict(o) for o in ops]}

@app.post("/api/benchmark", dependencies=[Depends(guard)])
def benchmark(req: BenchmarkInput):
    r = jsp_result(req.instance, req.method, req.seed, req.iterations, req.setup_hours)
    record = audit("benchmark", req.model_dump(), {"makespan": r["makespan"], "method": req.method, "instance": req.instance})
    return {"run": record, "model": "jsp", "scope": "published synthetic benchmark, not plant data", **r}

@app.post("/api/benchmark/compare", dependencies=[Depends(guard)])
def benchmark_compare(req: BenchmarkCompareInput):
    rows = [jsp_result(req.instance, meth, req.seed, req.iterations, 0) for meth in ("FIFO", "SPT", "MWKR", "ARK1500")]
    record = audit("benchmark_compare", req.model_dump(), {"methods": [r["method"] for r in rows], "instance": req.instance})
    return {"run": record, "model": "jsp", "instance": req.instance, "rows": rows,
            "published_no_setup_optimum": jsp.OPT[req.instance], "verified": True,
            "disclosure": "Single-seed ARK result; not statistically characterized. FIFO means job-index priority, not ready-time FIFO."}

@app.get("/api/runs", dependencies=[Depends(guard)])
def recent_runs(limit: int = 20):
    if not 1 <= limit <= 100: raise HTTPException(422, "limit must be 1–100")
    if os.getenv("SCHEDULENEXUS_AUDIT", "1") != "1" or not db_path().exists(): return {"rows": []}
    with _db_lock, sqlite3.connect(db_path(), timeout=3) as conn:
        rows = conn.execute("SELECT id, created_at, kind, input_sha256, summary_json FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"rows": [{"id": r[0], "timestamp_utc": r[1], "kind": r[2], "input_sha256": r[3], "summary": json.loads(r[4])} for r in rows]}

@app.get("/api/research/provenance")
def research_provenance():
    """Published dataset references and SHA-256 fingerprints for research auditing."""
    names = list(jsp.OPT)
    benchmarks = []
    for name in names:
        path = ROOT / "benchmarks" / f"{name}.txt"
        jobs, machines = jsp.load_instance(name)
        benchmarks.append({"instance": name, "jobs": len(jobs), "machines": machines,
                           "operations": sum(map(len, jobs)), "published_optimum": jsp.OPT[name],
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "upstream_file": f"https://github.com/tamy0612/JSPLIB/blob/master/instances/{name}"})
    return {"platform": "ScheduleNexus Lab", "engine_version": VERSION,
            "source_url": "https://github.com/tamy0612/JSPLIB",
            "research_track": "classical job-shop benchmark, no releases/dues/material outages/setups",
            "benchmarks": benchmarks,
            "dataset_status": "Content numerically compared against upstream JSPLIB instances; redistribution permissions remain under review",
            "code_license_status": "Not yet selected by repository owner",
            "attribution": ["Fisher & Thompson (1963), Industrial Scheduling", "Lawrence (1984), Resource Constrained Project Scheduling"],
            "limitations": ["Not plant validated", "No claimed overall heuristic optimality", "Separate verifier shares model assumptions"]}

@app.get("/api/research/disclosure")
def disclosure():
    return {"papers": "Contract-first production scheduling, research version 7",
            "model_limitations": ["One machine of each production resource type", "Nonpreemptive processing", "Fixed routing", "No labor constraints", "No plant-calibrated data"],
            "security_limitations": ["Local or trusted-network deployment recommended until external security audit", "In-process limits are not distributed quota enforcement"],
            "benchmark_source": "https://github.com/tamy0612/JSPLIB",
            "no_llm": True, "no_erp": True, "not_industrial_validated": True}
