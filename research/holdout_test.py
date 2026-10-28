from pathlib import Path
import csv, json, random, statistics, hashlib, math
from planner_core import synthetic_orders, processing_noise, schedule, metrics, scenario_outages
ROOT=Path(__file__).resolve().parent
SEEDS=list(range(202700,202800));G1=random.Random(7841);G2=random.Random(7842)

def main():
    records=[]
    for seed in SEEDS:
        jobs=synthetic_orders(seed,32,'machine_disruption')
        factors=processing_noise(jobs,seed);o=scenario_outages('machine_disruption')
        v={p:metrics(jobs,schedule(jobs,p,o,factors)) for p in ('EDD','FIFO')}
        records.append({'seed':seed,'EDD_mean_tardiness':v['EDD']['mean_tardiness'],
                        'FIFO_mean_tardiness':v['FIFO']['mean_tardiness'],
                        'difference_EDD_minus_FIFO':v['EDD']['mean_tardiness']-v['FIFO']['mean_tardiness'],
                        'EDD_on_time_pct':v['EDD']['on_time_pct'],'FIFO_on_time_pct':v['FIFO']['on_time_pct'],
                        'EDD_mean_flow_time':v['EDD']['mean_flow_time'],'FIFO_mean_flow_time':v['FIFO']['mean_flow_time']})
    d=[r['difference_EDD_minus_FIFO'] for r in records]
    mu=statistics.mean(d);sd=statistics.stdev(d)
    B=100000;extreme=0
    for _ in range(B):
        signmean=sum(G1.choice((-1,1))*x for x in d)/len(d)
        if abs(signmean)>=abs(mu)-1e-13:extreme+=1
    p=(extreme+1)/(B+1)
    boot=sorted(sum(d[G2.randrange(len(d))] for i in range(len(d)))/len(d) for _ in range(10000))
    summary={'primary_comparison':'EDD - FIFO, mean tardiness under machine disruption','n_paired_seeds':len(d),
          'mean_difference_h_per_order':mu,'paired_sd_h_per_order':sd,'paired_cohens_dz':mu/sd,
          'two_sided_sign_flip_mc_p':p,'sign_flip_draws':B,'extreme_draws':extreme,
          'bootstrap95_percentile_h_per_order':[boot[249],boot[9749]],
          'EDD_better_count':sum(x<0 for x in d),'EDD_worse_count':sum(x>0 for x in d),'ties':sum(x==0 for x in d),
          'EDD_mean_tardiness':statistics.mean(r['EDD_mean_tardiness'] for r in records),
          'FIFO_mean_tardiness':statistics.mean(r['FIFO_mean_tardiness'] for r in records),
          'EDD_mean_flow_time':statistics.mean(r['EDD_mean_flow_time'] for r in records),
          'FIFO_mean_flow_time':statistics.mean(r['FIFO_mean_flow_time'] for r in records),
          'hypothesis_post_exploratory':True,'independently_preregistered':False}
    with (ROOT/'data'/'holdout_primary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=records[0].keys());w.writeheader();w.writerows(records)
    (ROOT/'data'/'holdout_primary_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
