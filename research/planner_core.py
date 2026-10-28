"""Reference prototype for constraint-gated production scheduling research.
Fully standard-library; synthetic experiments, NOT a production ERP or LLM connector.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Tuple
import random, re, math

MACHINES = ('CUT','CNC','ASM','QC')
POLICIES = ('FIFO','SPT','EDD')

class PlanningError(ValueError):
    pass

@dataclass(frozen=True)
class Step:
    machine: str
    hours_per_unit: float

@dataclass(frozen=True)
class Order:
    id: str
    quantity: int
    release: float
    due: float
    material_ready: float
    route: Tuple[Step, ...]

@dataclass(frozen=True)
class Operation:
    order: str
    stage: int
    machine: str
    start: float
    end: float
    duration: float


def validate_orders(orders, outages=None):
    if not isinstance(orders, (list,tuple)) or not orders:
        raise PlanningError('at least one order is required')
    used=set()
    for job in orders:
        if not isinstance(job, Order): raise PlanningError('unexpected order schema')
        if not re.fullmatch(r'[A-Z0-9-]{2,30}',job.id): raise PlanningError('invalid order identifier')
        if job.id in used: raise PlanningError('duplicate order identifier')
        used.add(job.id)
        if not isinstance(job.quantity,int) or isinstance(job.quantity,bool) or not (1<=job.quantity<=1000):
            raise PlanningError('quantity must be a positive integer <= 1000')
        for name,x in [('release',job.release),('due',job.due),('material_ready',job.material_ready)]:
            if not isinstance(x,(int,float)) or not math.isfinite(x) or x<0:
                raise PlanningError(f'invalid {name}')
        if not job.route or len(job.route)>20: raise PlanningError('invalid or missing routing')
        for s in job.route:
            if s.machine not in MACHINES: raise PlanningError('unknown machine')
            if not isinstance(s.hours_per_unit,(int,float)) or not math.isfinite(s.hours_per_unit) or s.hours_per_unit<=0:
                raise PlanningError('invalid processing time')
    for machine, blocks in (outages or {}).items():
        if machine not in MACHINES: raise PlanningError('unknown outage machine')
        ordered=sorted(blocks)
        for i,(a,b) in enumerate(ordered):
            if not (math.isfinite(a) and math.isfinite(b) and 0<=a<b):
                raise PlanningError('invalid outage interval')
            if i and a < ordered[i-1][1]: raise PlanningError('overlapping outages')
    return True


def parse_order(text):
    """Narrow, deliberately non-generative English command grammar.
    Unknown or incomplete commands are rejected; no values are guessed.
    Durations are hours PER UNIT at each operation.
    """
    normalized=' '.join(text.strip().upper().split())
    pat=(r'^PLAN ORDER ([A-Z0-9-]{2,30}),?\s+(\d+) UNITS?,?\s+'
         r'RELEASE (\d+(?:\.\d+)?),?\s+DUE (\d+(?:\.\d+)?),?\s+'
         r'MATERIAL READY (\d+(?:\.\d+)?),?\s+ROUTE\s+(.+)$')
    m=re.fullmatch(pat,normalized)
    if not m: raise PlanningError('unsupported or incomplete order command: provide ID, units, release, due, material ready, and route')
    oid,qty,release,due,ready,route_raw=m.groups()
    pieces=route_raw.split('>')
    if not pieces or len(pieces)>20: raise PlanningError('route must contain 1-20 steps')
    route=[]
    for piece in pieces:
        k=re.fullmatch(r'\s*([A-Z]+)\s*:\s*(\d+(?:\.\d+)?)\s*',piece)
        if not k: raise PlanningError('route step must be MACHINE:hours_per_unit')
        route.append(Step(k.group(1),float(k.group(2))))
    job=Order(oid,int(qty),float(release),float(due),float(ready),tuple(route))
    validate_orders([job])
    return job


def find_slot(t,duration,blocks):
    # Earliest nonpreemptive placement in machine calendar.
    t=float(t)
    for a,b in sorted(blocks):
        if t >= b: continue
        if t+duration<=a+1e-9: return t
        if t < b and t+duration>a:
            t=b
    return t


def schedule(orders,policy='EDD',outages=None,processing_factors=None):
    orders=tuple(orders)
    outages=outages or {}
    validate_orders(orders,outages)
    if policy not in POLICIES: raise PlanningError('unknown dispatch policy')
    machine_available={m:0.0 for m in MACHINES}
    pos={job.id:0 for job in orders}
    ready={job.id:max(job.release,job.material_ready) for job in orders}
    ops=[]
    total=sum(len(j.route) for j in orders)
    while len(ops)<total:
        options=[]
        for job in orders:
            i=pos[job.id]
            if i>=len(job.route): continue
            step=job.route[i]
            fac=1.0 if processing_factors is None else processing_factors[(job.id,i)]
            if not 0.5<=fac<=2.0: raise PlanningError('stochastic factor out of permitted bounds')
            duration=job.quantity*step.hours_per_unit*fac
            begin=find_slot(max(machine_available[step.machine],ready[job.id]),duration,outages.get(step.machine,()))
            if policy=='FIFO': prio=(ready[job.id],job.id)
            elif policy=='SPT': prio=(duration,job.id)
            else: prio=(job.due,job.id)
            options.append((begin,prio,job.id,job,step,duration,i))
        begin,_,_,job,step,duration,i=min(options,key=lambda x:(x[0],x[1],x[2]))
        end=begin+duration
        ops.append(Operation(job.id,i,step.machine,begin,end,duration))
        ready[job.id]=end
        machine_available[step.machine]=end
        pos[job.id]+=1
    verify_schedule(orders,ops,outages,processing_factors=processing_factors)
    return ops


def verify_schedule(orders,ops,outages=None,processing_factors=None):
    """Separate post-scheduling inspection. Shares model schema/units, not dispatch logic.
    If fixed processing factors are supplied, validate expected input-derived durations.
    """
    outages=outages or {}
    n=sum(len(j.route) for j in orders)
    if len(ops)!=n: raise AssertionError('missing or surplus operation')
    by_order={j.id:[] for j in orders}
    by_machine={m:[] for m in MACHINES}
    jobs={j.id:j for j in orders}
    seen=set()
    for op in ops:
        key=(op.order,op.stage)
        if key in seen: raise AssertionError('duplicate operation')
        seen.add(key)
        job=jobs[op.order]
        if op.stage>=len(job.route) or job.route[op.stage].machine!=op.machine:
            raise AssertionError('wrong routing')
        if op.start < -1e-9 or op.end <= op.start: raise AssertionError('invalid time')
        if abs((op.end-op.start)-op.duration)>1e-8: raise AssertionError('processing time mismatch')
        if processing_factors is not None:
            fac=processing_factors[(op.order,op.stage)]
            expected=job.quantity*job.route[op.stage].hours_per_unit*fac
            if abs(op.duration-expected)>1e-8 * max(1,expected):
                raise AssertionError('scheduled duration differs from contracted processing requirement')
        by_order[op.order].append(op)
        by_machine[op.machine].append(op)
        for a,b in outages.get(op.machine,()):
            if op.start < b-1e-9 and op.end > a+1e-9:
                raise AssertionError('operation overlaps outage')
    for job in orders:
        runs=sorted(by_order[job.id],key=lambda x:x.stage)
        if len(runs)!=len(job.route) or any(o.stage!=i for i,o in enumerate(runs)):
            raise AssertionError('route incompleteness')
        if runs[0].start+1e-9<max(job.release,job.material_ready):
            raise AssertionError('started before order/material released')
        for a,b in zip(runs,runs[1:]):
            if b.start+1e-9<a.end: raise AssertionError('precedence violated')
    for mach,runs in by_machine.items():
        ordered=sorted(runs,key=lambda o:o.start)
        for a,b in zip(ordered,ordered[1:]):
            if b.start+1e-9<a.end: raise AssertionError('machine overlap')
    return True


def metrics(orders,ops):
    completed={job.id:max(o.end for o in ops if o.order==job.id) for job in orders}
    tard=[max(0,completed[job.id]-job.due) for job in orders]
    late=[completed[job.id]-job.due for job in orders]
    horizon=max(completed.values())
    busy={m:sum(o.duration for o in ops if o.machine==m) for m in MACHINES}
    return {
        'mean_tardiness':sum(tard)/len(tard),
        'on_time_pct':100*sum(t<1e-9 for t in tard)/len(tard),
        'max_lateness':max(late),
        'mean_flow_time':sum(completed[j.id]-j.release for j in orders)/len(orders),
        'makespan':horizon,
        'utilization_pct':{k:100*v/horizon for k,v in busy.items()}
    }


def synthetic_orders(seed=410, count=32, scenario='baseline'):
    if scenario not in ('baseline','material_delay','machine_disruption'):
        raise PlanningError('unknown scenario')
    rng=random.Random(seed)
    routes=[('CUT','CNC','QC'),('CUT','ASM','QC'),('CNC','ASM','QC'),('CUT','CNC','ASM','QC')]
    jobs=[]
    for i in range(count):
        flow=routes[i%len(routes)]
        q=rng.randint(1,4)
        release=float(rng.randint(0,35))
        mat_lag=rng.uniform(4,22) if scenario=='material_delay' else rng.uniform(0,4)
        # Due dates held fixed across scenarios for paired disruption analysis.
        due=release+rng.uniform(62,148)
        steps=tuple(Step(m,round(rng.uniform(*{
            'CUT':(0.8,1.5),'CNC':(1.2,2.6),'ASM':(0.9,1.9),'QC':(0.3,0.8)
        }[m]),3)) for m in flow)
        jobs.append(Order(f'J{i+1:03}',q,release,round(due,3),round(release+mat_lag,3),steps))
    return jobs


def scenario_outages(scenario):
    return {'CNC':[(72.0,104.0)],'ASM':[(112.0,134.0)]} if scenario=='machine_disruption' else {}


def processing_noise(orders,seed):
    rng=random.Random(10_000+seed)
    return {(job.id,i):rng.triangular(.80,1.20,1.0) for job in orders for i in range(len(job.route))}


def experiment(seed,scenario,policy,count=32):
    jobs=synthetic_orders(seed,count,scenario)
    ops=schedule(jobs,policy,scenario_outages(scenario),processing_noise(jobs,seed))
    return metrics(jobs,ops)
