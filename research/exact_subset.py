"""MIP makespan comparison for tractable 6-job two-operation subsets of the original synthetic generator.
Nonpreemptive disjunctive MILP; no outages. Exact optimality claimed only on status 0.
"""
from pathlib import Path
import csv, json, hashlib, time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix
from planner_core import synthetic_orders, processing_noise, Order, schedule, metrics, verify_schedule, Operation
ROOT=Path(__file__).resolve().parent
SEEDS=list(range(202600,202612))

def choose_subset(seed):
    jobs=synthetic_orders(seed,32,'baseline')[:6]
    # exactly two operations per order, original machines, quantity, material gate and noise.
    jobs=[Order(j.id,j.quantity,j.release,j.due,j.material_ready,j.route[:2]) for j in jobs]
    factors=processing_noise(jobs,seed)
    return jobs,factors

def solve_exact(jobs,factors,limit=7):
    pairs=[(j.id,k,j.route[k].machine,j.quantity*j.route[k].hours_per_unit*factors[(j.id,k)]) for j in jobs for k in range(len(j.route))]
    n=len(pairs);groups={}
    for i,p in enumerate(pairs):groups.setdefault(p[2],[]).append(i)
    disj=[(i,k) for group in groups.values() for a,i in enumerate(group) for k in group[a+1:]]
    y0=n+1;V=y0+len(disj);c=np.zeros(V);c[n]=1
    pval=[p[3] for p in pairs]
    H=max(max(j.release,j.material_ready) for j in jobs)+sum(pval)+10
    low=np.zeros(V);high=np.full(V,H);high[y0:]=1
    for j in jobs:
        i=next(i for i,p in enumerate(pairs) if p[0]==j.id)
        low[i]=max(j.release,j.material_ready)
    rows=[];upp=[];lowb=[]
    def add(coefs,lo=-np.inf,hi=np.inf):rows.append(coefs);upp.append(hi);lowb.append(lo)
    for j in jobs:
        ids=[i for i,p in enumerate(pairs) if p[0]==j.id]
        for i,k in zip(ids,ids[1:]):add({i:1,k:-1},hi=-pval[i])
        add({ids[-1]:1,n:-1},hi=-pval[ids[-1]])
    for z,(i,k) in enumerate(disj):
        yi=y0+z
        # if y=1: operation i precedes k. Else: k precedes i.
        add({i:1,k:-1,yi:H},hi=H-pval[i])
        add({k:1,i:-1,yi:-H},hi=-pval[k])
    mat=lil_matrix((len(rows),V))
    for ir,row in enumerate(rows):
        for idx,val in row.items():mat[ir,idx]=val
    intg=np.zeros(V,dtype=int);intg[y0:]=1
    result=milp(c=c,integrality=intg,bounds=Bounds(low,high),constraints=LinearConstraint(mat.tocsc(),lowb,upp),options={'time_limit':limit,'mip_rel_gap':0.000001,'presolve':True})
    if result.x is not None:
        ops=[]
        for i,(job,stage,m,d) in enumerate(pairs):
            start=float(result.x[i]);ops.append(Operation(job,stage,m,start,start+d,float(d)))
        # MILP numerical feasibility tolerance may allow ~1e-6 hour gaps.
        # Construct the same machine/job topological order with exact right-shifting,
        # then apply the strict independent check to the repaired integer-order plan.
        pred={ (o.order,o.stage):[] for o in ops }
        opmap={(o.order,o.stage):o for o in ops}
        for j in jobs:
            for k in range(1,len(j.route)):
                pred[(j.id,k)].append((j.id,k-1))
        for machine in {o.machine for o in ops}:
            xs=sorted((o for o in ops if o.machine==machine),key=lambda o:(o.start,o.order,o.stage))
            for a,b in zip(xs,xs[1:]):pred[(b.order,b.stage)].append((a.order,a.stage))
        repaired={};remaining=set(pred)
        while remaining:
            eligible=sorted((node for node in remaining if all(p in repaired for p in pred[node])))
            if not eligible: raise AssertionError('MILP ordering contains cycle')
            node=eligible[0];old=opmap[node];j=next(j for j in jobs if j.id==old.order)
            t=max([max(j.release,j.material_ready) if old.stage==0 else 0]+[repaired[q].end for q in pred[node]])
            repaired[node]=Operation(old.order,old.stage,old.machine,t,t+old.duration,old.duration)
            remaining.remove(node)
        feasible=list(repaired.values())
        verify_schedule(jobs,feasible,processing_factors=factors)
        if max(o.end for o in feasible) > result.fun + 0.0001:
            raise AssertionError('numerical right shift exceeds MILP tolerance')
    return result

def main():
    tic=time.perf_counter();rows=[]
    for seed in SEEDS:
        jobs,factors=choose_subset(seed)
        heur={}
        for method in ('FIFO','SPT','EDD'):
            ops=schedule(jobs,method,{},factors)
            heur[method]=metrics(jobs,ops)['makespan']
        st=time.perf_counter();result=solve_exact(jobs,factors)
        status=['optimal','time/iteration limit','infeasible','unbounded','other'][result.status]
        ref=float(result.fun) if result.fun is not None else float('nan')
        for policy,ms in heur.items():
            rows.append({'seed':seed,'jobs':len(jobs),'operations':sum(map(lambda x:len(x.route),jobs)),
                         'objective':'makespan','method':policy,'makespan':round(ms,8),'milp_best_primal':round(ref,8),
                         'milp_status':status,'milp_lower_bound':round(float(result.mip_dual_bound),8) if result.mip_dual_bound is not None else '',
                         'milp_reported_gap':float(result.mip_gap) if result.mip_gap is not None else '',
                         'relative_gap_to_certified_opt_pct':round(100*(ms-ref)/ref,5) if result.status==0 else '',
                         'milp_elapsed_seconds':round(time.perf_counter()-st,3)})
        print(seed,status,'MILP',round(ref,3),'heuristic', {k:round(v,3) for k,v in heur.items()},'time',round(time.perf_counter()-st,2))
    p=ROOT/'data'/'milp_subset_results.csv';p.parent.mkdir(exist_ok=True)
    with p.open('w',newline='') as f: writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    (ROOT/'data'/'milp_subset_metadata.json').write_text(json.dumps({'subset':'first six orders and first two operations per order from baseline seed (202600-202611)','objective':'makespan','comparability':'not full 32-order objective, only 6x2 subproblem','time_limit_seconds_per_milp':7,'scipy_version':__import__('scipy').__version__,'elapsed_seconds':round(time.perf_counter()-tic,3)},indent=2))
    print('DONE',round(time.perf_counter()-tic,2),'optimal seeds',sum(1 for r in rows[::3] if r['milp_status']=='optimal'))
if __name__=='__main__':main()
