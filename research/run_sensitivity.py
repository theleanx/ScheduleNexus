"""Paired robustness experiments for reviewer response. All outcomes computed, not inferred.
Levels modify due offsets relative to release on identical base instances.
Outages are intentional nonpreemptive stress windows; no industrial calibration.
"""
from dataclasses import replace
from pathlib import Path
from collections import defaultdict
import csv, json, hashlib, platform, math, random, statistics, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from planner_core import synthetic_orders, schedule, metrics, processing_noise, scenario_outages

ROOT=Path(__file__).resolve().parent
SEEDS=range(202600,202700)
POLICIES=('FIFO','SPT','EDD')
DUE_MULTIPLIERS=(0.55, 0.75, 1.0, 1.25)
OUTAGE_SETTINGS={
 'early':{'CNC':[(48.,80.)], 'ASM':[(88.,110.)]},
 'standard':scenario_outages('machine_disruption'),
 'late':{'CNC':[(96.,128.)], 'ASM':[(136.,158.)]}}


def ci(vals,B=4000,bootstrap_seed=88443):
    ar=list(vals); n=len(ar)
    rng=random.Random(bootstrap_seed)
    means=sorted(sum(ar[rng.randrange(n)] for _ in range(n))/n for _ in range(B))
    return means[int(.025*B)],means[int(.975*B)-1]


def main():
    ts=time.perf_counter()
    rows=[]; checks=0
    for seed in SEEDS:
        orig=synthetic_orders(seed,32,'machine_disruption')
        noise=processing_noise(orig,seed)
        for mult in DUE_MULTIPLIERS:
            jbs=[replace(j,due=round(j.release+(j.due-j.release)*mult,4)) for j in orig]
            for policy in POLICIES:
                ops=schedule(jbs,policy,OUTAGE_SETTINGS['standard'],noise)
                k=metrics(jbs,ops)
                rows.append({'sensitivity':'due_tightness','setting':f'{mult:.2f}x',
                'seed':seed,'policy':policy,'orders':len(jbs),'operations':len(ops),
                'mean_tardiness':k['mean_tardiness'],'on_time_pct':k['on_time_pct'],
                'mean_flow_time':k['mean_flow_time'],'makespan':k['makespan']})
                checks+=1
        for label,outs in OUTAGE_SETTINGS.items():
            if label=='standard': continue
            for policy in POLICIES:
                ops=schedule(orig,policy,outs,noise)
                k=metrics(orig,ops)
                rows.append({'sensitivity':'outage_placement','setting':label,
                'seed':seed,'policy':policy,'orders':len(orig),'operations':len(ops),
                'mean_tardiness':k['mean_tardiness'],'on_time_pct':k['on_time_pct'],
                'mean_flow_time':k['mean_flow_time'],'makespan':k['makespan']})
                checks+=1
    # Reuse standard machine-disruption condition from main experiments to represent common baseline.
    with (ROOT/'data'/'replications.csv').open() as f:
        base=[x for x in csv.DictReader(f) if x['scenario']=='machine_disruption']
    for b in base:
        rows.append({'sensitivity':'outage_placement','setting':'standard',
        'seed':int(b['seed']),'policy':b['policy'],'orders':int(b['orders']),
        'operations':int(b['operations']),'mean_tardiness':float(b['mean_tardiness']),
        'on_time_pct':float(b['on_time_pct']),
        'mean_flow_time':float(b['mean_flow_time']),'makespan':float(b['makespan'])})
    rows.sort(key=lambda r:(r['sensitivity'],r['setting'],r['seed'],r['policy']))
    with (ROOT/'data'/'sensitivity_replications.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    groups=defaultdict(dict)
    for r in rows:
        groups[(r['sensitivity'],r['setting'],r['seed'])][r['policy']]=r
    summary=[]
    for sensitivity in ('due_tightness','outage_placement'):
      settings=[f'{x:.2f}x' for x in DUE_MULTIPLIERS] if sensitivity=='due_tightness' else ['early','standard','late']
      for setting in settings:
        for pol in POLICIES:
            cases=[groups[(sensitivity,setting,seed)][pol] for seed in SEEDS]
            dd=[groups[(sensitivity,setting,seed)]['EDD']['mean_tardiness']-
                groups[(sensitivity,setting,seed)]['FIFO']['mean_tardiness'] for seed in SEEDS]
            e_ci=ci(dd)
            dd_sign=[x for x in dd if abs(x)>1e-9]
            rec={'sensitivity':sensitivity,'setting':setting,'policy':pol,'n':len(cases)}
            for key in ('mean_tardiness','on_time_pct','mean_flow_time','makespan'):
                rec[key+'_mean']=round(statistics.mean(c[key] for c in cases),4)
            if pol=='EDD':
                rec['paired_EDD_minus_FIFO_tardiness_mean']=round(statistics.mean(dd),4)
                rec['paired_EDD_minus_FIFO_ci_lo']=round(e_ci[0],4)
                rec['paired_EDD_minus_FIFO_ci_hi']=round(e_ci[1],4)
                rec['EDD_better_seeds']=sum(x<-1e-9 for x in dd)
                rec['EDD_equal_seeds']=sum(abs(x)<=1e-9 for x in dd)
                rec['EDD_worse_seeds']=sum(x>1e-9 for x in dd)
            summary.append(rec)
    allkeys=[]
    for r in summary:
        for k in r:
            if k not in allkeys:allkeys.append(k)
    with (ROOT/'data'/'sensitivity_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=allkeys);w.writeheader();w.writerows(summary)
    # Render sensitivity figure directly from measured summary.
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9})
    fig, ax=plt.subplots(figsize=(9.2,4.5))
    x=list(range(len(DUE_MULTIPLIERS)))
    for p,co in (('FIFO','#52708c'),('SPT','#19a193'),('EDD','#e2a349')):
        ys=[next(r['mean_tardiness_mean'] for r in summary if r['sensitivity']=='due_tightness' and r['setting']==f'{k:.2f}x' and r['policy']==p) for k in DUE_MULTIPLIERS]
        ax.plot(x,ys,marker='o',label=p,color=co,linewidth=2)
    ax.set_xticks(x,[f'{z:.2f} ×' for z in DUE_MULTIPLIERS]);ax.set_ylabel('Mean tardiness (h / order)')
    ax.set_xlabel('Due-date offset multiplier; 1.00 × is original 62–148 h offset')
    ax.set_title('Measured sensitivity to due-date tightness under fixed standard outages')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(ROOT/'figures'/'sensitivity_due_dates.png',dpi=210);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9.2,4.5))
    for p,co in (('FIFO','#52708c'),('SPT','#19a193'),('EDD','#e2a349')):
        ys=[next(r['mean_tardiness_mean'] for r in summary if r['sensitivity']=='outage_placement' and r['setting']==lab and r['policy']==p) for lab in ['early','standard','late']]
        ax.plot([0,1,2],ys,marker='o',label=p,color=co,linewidth=2)
    ax.set_xticks([0,1,2],['Early [48,80), [88,110)','Standard [72,104), [112,134)','Late [96,128), [136,158)'])
    ax.set_ylabel('Mean tardiness (h / order)');ax.set_title('Measured sensitivity to outage-window placement (CNC / ASM)')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(ROOT/'figures'/'sensitivity_outages.png',dpi=210);plt.close(fig)
    meta={'additional_scheduler_runs':checks,'reused_standard_outage_policy_evaluations':len(base),
      'sensitivity_rows_with_reused_baseline':len(rows),'due_multipliers':DUE_MULTIPLIERS,'outage_settings':OUTAGE_SETTINGS,
      'seeds':'202600-202699','processing_noise':'identical factors within each seed across due and outage sensitivity conditions',
      'ci':'4000 percentile paired bootstrap draws, seed 88443',
      'elapsed_seconds':round(time.perf_counter()-ts,3),
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'note':'synthetic stress testing; exploratory, no industrial calibration'}
    (ROOT/'data'/'sensitivity_metadata.json').write_text(json.dumps(meta,indent=2))
    print('Runs',checks,'seconds',meta['elapsed_seconds'])
    for r in summary:
        if r['policy']=='EDD': print('sensitivity:',r)

if __name__=='__main__':main()
