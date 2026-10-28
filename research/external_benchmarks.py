"""Classic JSP benchmark adapter and a bounded-cost random-key simulated annealing comparator.
JSP variants: all releases=0; no material gates, outages or due dates. Makespan only.
All instances manually transcribed from the cited JSPLIB raw instance files; see provenance.
"""
from pathlib import Path
import csv, math, random, statistics, time, json, hashlib
from dataclasses import dataclass
ROOT=Path(__file__).resolve().parent.parent
OPT={'ft06':55,'la01':666,'la02':655,'la03':597,'la04':590,'la05':593}

@dataclass(frozen=True)
class Op:
    job:int
    stage:int
    machine:int
    start:float
    end:float

def load_instance(name):
    assert name in OPT
    path=ROOT/'benchmarks'/f'{name}.txt'
    ls=[x for x in path.read_text().splitlines() if x.strip() and not x.startswith('#')]
    nj,nm=map(int,ls[0].split());assert len(ls)==nj+1
    jobs=[]
    for row in ls[1:]:
        items=list(map(int,row.split()));assert len(items)==2*nm
        route=list(zip(items[::2],items[1::2]))
        assert set(m for m,_ in route)==set(range(nm)) and all(d>0 for _,d in route)
        jobs.append(tuple(route))
    return jobs,nm

def setup_gap(previous_job,next_job,setup_hours):
    return setup_hours if previous_job is not None and previous_job%3 != next_job%3 else 0.0

def greedy(jobs,nm,rule='FIFO',keys=None,setup_hours=0):
    n=len(jobs); positions=[0]*n; ready=[0.0]*n; machines=[0.0]*nm; lastjob=[None]*nm; ops=[]
    rem=[[0]*(len(j)+1) for j in jobs]
    for j,steps in enumerate(jobs):
        for k in range(len(steps)-1,-1,-1):rem[j][k]=rem[j][k+1]+steps[k][1]
    while len(ops)<sum(map(len,jobs)):
        cands=[]
        for j,steps in enumerate(jobs):
            k=positions[j]
            if k>=len(steps):continue
            m,p=steps[k]; earliest=max(ready[j],machines[m]+setup_gap(lastjob[m],j,setup_hours))
            if rule=='FIFO':priority=(j,k)
            elif rule=='SPT':priority=(p,j)
            elif rule=='MWKR':priority=(-rem[j][k],j)
            elif rule=='ARK':priority=(keys[j][k],j)
            else:raise ValueError(rule)
            cands.append((earliest,priority,j,k,m,p))
        t,_,j,k,m,p=min(cands)
        ops.append(Op(j,k,m,t,t+p));positions[j]+=1;ready[j]=t+p;machines[m]=t+p;lastjob[m]=j
    check(jobs,nm,ops,setup_hours=setup_hours)
    return ops

def check(jobs,nm,ops,setup_hours=0):
    assert len(ops)==sum(map(len,jobs));seen=set();byj={j:[] for j in range(len(jobs))};bym={m:[] for m in range(nm)}
    for op in ops:
        assert (op.job,op.stage) not in seen
        seen.add((op.job,op.stage))
        m,d=jobs[op.job][op.stage]
        assert m==op.machine and abs(op.end-op.start-d)<1e-8 and op.start>=0
        byj[op.job].append(op);bym[op.machine].append(op)
    for j,xs in byj.items():
        xs.sort(key=lambda x:x.stage)
        assert len(xs)==len(jobs[j]) and all(op.stage==k for k,op in enumerate(xs))
        for a,b in zip(xs,xs[1:]):assert a.end<=b.start+1e-8
    for m,xs in bym.items():
        xs.sort(key=lambda x:x.start)
        for a,b in zip(xs,xs[1:]):assert a.end+setup_gap(a.job,b.job,setup_hours)<=b.start+1e-8
    return True

def quality(ops):return max(x.end for x in ops)

def annealed_random_keys(jobs,nm,seed=2100,steps=1500,setup_hours=0):
    rng=random.Random(seed)
    n=len(jobs)
    base=[[rng.random() for _ in row] for row in jobs]
    # Greedy upper bounds are admissible initializer (i.e. verified, never claimed optimal).
    starts=[greedy(jobs,nm,rule,setup_hours=setup_hours) for rule in ['FIFO','SPT','MWKR']]
    best_ops=min(starts,key=quality);best_m=quality(best_ops)
    cur=[x[:] for x in base];cur_m=quality(greedy(jobs,nm,'ARK',cur,setup_hours=setup_hours))
    accepted=0
    for it in range(steps):
        # Bounded random-key annealing; always use same configured compute budget.
        new=[x[:] for x in cur]
        j=rng.randrange(n);k=rng.randrange(len(jobs[j]));new[j][k]=rng.random()
        if rng.random()<0.10:
            j=rng.randrange(n);k=rng.randrange(len(jobs[j]));new[j][k]=rng.random()
        new_ops=greedy(jobs,nm,'ARK',new,setup_hours=setup_hours)
        nv=quality(new_ops)
        temp=max(.35, (.04*cur_m)*(1.0-(it/steps)))
        if nv<=cur_m or rng.random()<math.exp(min(0.0,(cur_m-nv)/temp)):
            cur=new;cur_m=nv;accepted+=1
        if nv<best_m:best_m=nv;best_ops=new_ops
    return best_ops,accepted

def main():
    tic=time.perf_counter();out=[];schedules={}
    for ix,name in enumerate(OPT):
        jobs,nm=load_instance(name);nops=sum(map(len,jobs));b=OPT[name]
        for rule in ('FIFO','SPT','MWKR'):
            oo=greedy(jobs,nm,rule)
            value=quality(oo)
            out.append({'instance':name,'jobs':len(jobs),'machines':nm,'operations':nops,'method':rule,
                        'makespan':value,'published_optimum':b,'gap_pct':100*(value-b)/b,
                        'solver_status':'verified feasible; not optimality claim','iterations':1})
            schedules[(name,rule)]=oo
        oo,accept=annealed_random_keys(jobs,nm,seed=60000+ix,steps=1500)
        value=quality(oo)
        out.append({'instance':name,'jobs':len(jobs),'machines':nm,'operations':nops,'method':'ARK1500',
                    'makespan':value,'published_optimum':b,'gap_pct':100*(value-b)/b,
                    'solver_status':'verified feasible; randomized search, single seed','iterations':1500})
        schedules[(name,'ARK1500')]=oo
        assert value>=b
    dat=ROOT/'data';dat.mkdir(exist_ok=True)
    with (dat/'external_jobshop_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=out[0].keys());writer.writeheader();writer.writerows(out)
    with (dat/'external_jobshop_schedules.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['instance','method','job','stage','machine','start','end']);writer.writeheader()
        for (name,method),ops in schedules.items():
            for x in ops:writer.writerow({'instance':name,'method':method,**x.__dict__})
    setups=[]
    for name in OPT:
        jobs,nm=load_instance(name)
        for method in ('FIFO','SPT','MWKR'):
            v=quality(greedy(jobs,nm,method,setup_hours=5))
            no=next(r['makespan'] for r in out if r['instance']==name and r['method']==method)
            setups.append({'instance':name,'method':method,'setup_hours_if_family_changes':5,
                            'setup_family_rule':'job_index modulo 3','makespan_with_setups':v,
                            'makespan_without_setups':no,'delta_makespan':v-no,
                            'published_optimum_comparable':'NO - modified benchmark objective'})
    with (dat/'setup_stress_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=setups[0].keys());w.writeheader();w.writerows(setups)
    # Mutation proof: a schedule ignoring setup rules must fail the enriched checker for at least one instance.
    invalid=0
    for name in OPT:
        jobs,nm=load_instance(name)
        bare=greedy(jobs,nm,'FIFO')
        try:check(jobs,nm,bare,setup_hours=5)
        except AssertionError: invalid+=1
    assert invalid==len(OPT)
    (dat/'external_jobshop_metadata.json').write_text(json.dumps({'source':'https://github.com/tamy0612/JSPLIB (published Lawrence and Fisher-Thompson instances); transcribed unchanged','source_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'benchmarks').glob('*.txt'))},'published_known_optima':OPT,'objective':'makespan; no releases, material delays, outages or due dates','random_key_annealing_steps':1500,'setup_stress':'5 time units on cross-family transitions, family=job_index modulo 3; 6 instances x 3 methods; no claim against published no-setup optimum','random_seed_per_instance':'60000 + instance index (0-based)','elapsed_seconds':round(time.perf_counter()-tic,3)},indent=2))
    print('External JSP scores (published best-known OPT)')
    for name in OPT:
        print(name,'optimal',OPT[name],[(z['method'],z['makespan'],round(z['gap_pct'],1)) for z in out if z['instance']==name])
    print('Setup-incompatibility mutation checks rejected:',invalid,'of',len(OPT))
    print('wall',round(time.perf_counter()-tic,3))
if __name__=='__main__':main()
