"""Post-review robustness audit for a FIXED previously published ARK1500 configuration.

20 predeclared integer random seeds 61000...61019 per each of six published
JSP instances; 1,500 proposals per seed, same temperature floor 0.35 and
3-way constructive starts as archived in the earlier V5 comparator code.

This is a sensitivity check, NOT a clean out-of-sample hyperparameter tuning
assessment: the original tuning/design provenance is undocumented.
"""
from pathlib import Path
import csv, json, statistics, time
from concurrent.futures import ProcessPoolExecutor
from external_benchmarks import OPT, load_instance, annealed_random_keys, quality, check
ROOT=Path(__file__).resolve().parent
SEEDS=tuple(range(61000,61020))
BUDGET=1500

def run_one(name):
    optimum=OPT[name]
    jobs,nm=load_instance(name)
    records=[]
    for seed in SEEDS:
        ops, acc=annealed_random_keys(jobs,nm,seed=seed,steps=BUDGET)
        assert check(jobs,nm,ops)
        span=quality(ops)
        assert span>=optimum
        records.append({'instance':name,'seed':seed,'method':'ARK1500',
                        'iterations':BUDGET,'makespan':span,'published_optimum':optimum,
                        'gap_pct':100*(span-optimum)/optimum,'accepted_moves':acc,
                        'verified':True})
    vals=[v['makespan'] for v in records]
    gaps=[v['gap_pct'] for v in records]
    summary={'instance':name,'n_seeds':len(SEEDS),'seed_range':f'{SEEDS[0]}-{SEEDS[-1]}',
             'iterations_per_seed':BUDGET,'published_optimum':optimum,
             'best_makespan':min(vals),'mean_makespan':round(statistics.mean(vals),3),
             'worst_makespan':max(vals),'sd_makespan':round(statistics.stdev(vals),3),
             'mean_gap_pct':round(statistics.mean(gaps),3),
             'best_gap_pct':round(min(gaps),3),'worst_gap_pct':round(max(gaps),3),
             'hit_optimum_count':sum(v==optimum for v in vals)}
    return records,summary

def main():
    t0=time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as exe:
        rs=list(exe.map(run_one,OPT.keys()))
    records=[row for rows,_ in rs for row in rows]
    summary=[s for _,s in rs]
    for row in summary: print(row['instance'],'best/mean/worst',row['best_makespan'],row['mean_makespan'],row['worst_makespan'],flush=True)
    data=ROOT/'data'; data.mkdir(exist_ok=True)
    for fn,rows in [('ark_multiseed_replications.csv',records),('ark_multiseed_summary.csv',summary)]:
        with (data/fn).open('w',newline='') as fh:
            writer=csv.DictWriter(fh,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    (data/'ark_multiseed_protocol.json').write_text(json.dumps({
       'study':'post-review robustness audit of frozen V5 configuration',
       'seeds':list(SEEDS),'instance_order':list(OPT),
       'budget_per_instance_seed':BUDGET,'temperature_floor':0.35,
       'constructive_initializers':['FIFO','SPT','MWKR'],
       'total_runs':len(records),
       'tuning_provenance':'No timestamped pre-test configuration record recovered; hyperparameter independence from six tested instances cannot be established; do not treat as tuned on disjoint training cases.',
       'elapsed_seconds':round(time.perf_counter()-t0,2)}, indent=2))
    print('total',len(records),'seconds',round(time.perf_counter()-t0,2),flush=True)

if __name__=='__main__':main()
