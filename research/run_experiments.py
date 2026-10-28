"""Reproducible synthetic benchmarks (100 paired replications per scenario/policy)."""
import csv, random, statistics, json, hashlib, platform, time
from collections import defaultdict
from pathlib import Path
from planner_core import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
SEEDS=list(range(202600,202700))
SCENARIOS=['baseline','material_delay','machine_disruption']
POLICIES=['FIFO','SPT','EDD']
KPI=['mean_tardiness','on_time_pct','mean_flow_time','makespan','max_lateness']

def ci(values):
    rng=random.Random(393919)
    vals=list(values); n=len(vals)
    boots=sorted(sum(vals[rng.randrange(n)] for _ in range(n))/n for _ in range(4000))
    return (boots[99],boots[3899])

def main():
    tic=time.perf_counter()
    raw=[]
    for sc in SCENARIOS:
        for seed in SEEDS:
            orders=synthetic_orders(seed,32,sc)
            factors=processing_noise(orders,seed)
            for p in POLICIES:
                ops=schedule(orders,p,scenario_outages(sc),factors)
                row={'scenario':sc,'seed':seed,'policy':p,'orders':len(orders),'operations':len(ops),**{k:v for k,v in metrics(orders,ops).items() if k!='utilization_pct'}}
                raw.append(row)
    with (ROOT/'data'/'replications.csv').open('w',newline='') as f:
        out=csv.DictWriter(f,fieldnames=list(raw[0])); out.writeheader(); out.writerows(raw)
    summ=[]
    for sc in SCENARIOS:
        for p in POLICIES:
            d=[r for r in raw if r['scenario']==sc and r['policy']==p]
            z={'scenario':sc,'policy':p,'n':len(d)}
            for k in KPI:
                ar=[r[k] for r in d]; lo,hi=ci(ar)
                z[k+'_mean']=round(statistics.mean(ar),4)
                z[k+'_sd']=round(statistics.stdev(ar),4)
                z[k+'_ci_low']=round(lo,4); z[k+'_ci_high']=round(hi,4)
            summ.append(z)
    with (ROOT/'data'/'summary.csv').open('w',newline='') as f:
        out=csv.DictWriter(f,fieldnames=list(summ[0])); out.writeheader(); out.writerows(summ)
    paired=[]
    for sc in SCENARIOS:
        for candidate in ['SPT','EDD']:
            rows_by={(r['seed'],r['policy']):r for r in raw if r['scenario']==sc}
            for k in ['mean_tardiness','on_time_pct','mean_flow_time','makespan']:
                deltas=[rows_by[(seed,candidate)][k]-rows_by[(seed,'FIFO')][k] for seed in SEEDS]
                lo,hi=ci(deltas)
                paired.append({'scenario':sc,'contrast':candidate+' - FIFO','metric':k,
                    'paired_mean_difference':round(statistics.mean(deltas),4),'ci_low':round(lo,4),'ci_high':round(hi,4)})
    with (ROOT/'data'/'paired_comparisons.csv').open('w',newline='') as f:
        out=csv.DictWriter(f,fieldnames=list(paired[0])); out.writeheader(); out.writerows(paired)
    plt.rcParams.update({'font.size':9,'font.family':'DejaVu Sans'})
    fig,axs=plt.subplots(1,2,figsize=(12,4.3))
    for ax,k,label in [(axs[0],'mean_tardiness','Mean tardiness (hours / order)'),
                       (axs[1],'on_time_pct','Orders on time (%)')]:
        xs=range(3)
        colors=['#42566d','#118f86','#e8a344']
        for pi,p in enumerate(POLICIES):
            d=[next(t for t in summ if t['scenario']==sc and t['policy']==p) for sc in SCENARIOS]
            xx=[x+(pi-1)*.23 for x in xs]
            means=[t[k+'_mean'] for t in d]
            errs=[[t[k+'_mean']-t[k+'_ci_low'] for t in d],[t[k+'_ci_high']-t[k+'_mean'] for t in d]]
            ax.bar(xx,means,width=.22,label=p,color=colors[pi],yerr=errs,capsize=2,error_kw={'lw':1})
        ax.set_xticks(list(xs),['Nominal','Material delay','Machine disruption'])
        ax.set_ylabel(label);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    axs[0].legend(loc='upper left',ncol=3,fontsize=8)
    fig.suptitle('Synthetic benchmark: 100 paired replications per scenario',fontsize=13,fontweight='bold')
    fig.tight_layout()
    fig.savefig(ROOT/'figures'/'benchmark_results.png',dpi=210,bbox_inches='tight');plt.close(fig)

    jobs=synthetic_orders(SEEDS[0],24,'machine_disruption')
    runs=schedule(jobs,'EDD',scenario_outages('machine_disruption'),processing_noise(jobs,SEEDS[0]))
    fig,ax=plt.subplots(figsize=(11.4,5.6))
    yy={m:i for i,m in enumerate(MACHINES)}
    for op in runs:
        ax.broken_barh([(op.start,op.end-op.start)],(yy[op.machine]-.3,.59),facecolors='#176f85' if (int(op.order[1:])%2) else '#d0a052',alpha=.9)
    for m, blocks in scenario_outages('machine_disruption').items():
        for a,b in blocks:
            ax.broken_barh([(a,b-a)],(yy[m]-.34,.67),facecolors='#c94b50',alpha=.8)
    ax.set_yticks(range(4),MACHINES);ax.set_xlabel('Simulated hours');ax.set_xlim(0,max(o.end for o in runs)*1.02)
    ax.set_title('Executable schedule: machine capacity and disruption windows (seed 202600)')
    ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor='#176f85',label='Orders (odd ID)'),Patch(facecolor='#d0a052',label='Orders (even ID)'),Patch(facecolor='#c94b50',label='Planned outage')],loc='lower right',fontsize=8)
    fig.tight_layout();fig.savefig(ROOT/'figures'/'schedule_gantt.png',dpi=210);plt.close(fig)

    # Original contract-first system diagram.
    fig,ax=plt.subplots(figsize=(13,3.9));ax.axis('off')
    labels=[('1. Bounded natural\nlanguage command','Reject missing values'),
        ('2. Contract / provenance\nvalidation','Typed order, routing, time'),
        ('3. Deterministic\nfinite-capacity scheduler','FIFO / SPT / EDD'),
        ('4. Separate post-schedule\nverifier','Capacity, materials, outages'),
        ('5. Decision evidence\nand comparison','KPIs, confidence intervals')]
    for i,(a,b) in enumerate(labels):
        x=.015+i*.2
        from matplotlib.patches import FancyBboxPatch
        p=FancyBboxPatch((x,.31),.174,.48,boxstyle='round,pad=.012,rounding_size=.028',facecolor='#e8f2f4',edgecolor='#1d7183',linewidth=1.4,transform=ax.transAxes)
        ax.add_patch(p)
        ax.text(x+.087,.61,a,ha='center',va='center',fontsize=9,fontweight='bold',color='#174052',transform=ax.transAxes)
        ax.text(x+.087,.39,b,ha='center',va='center',fontsize=7.5,color='#546b75',transform=ax.transAxes)
        if i<4: ax.annotate('',xy=(x+.198,.55),xytext=(x+.177,.55),arrowprops={'arrowstyle':'->','lw':1.7,'color':'#b28235'},xycoords='axes fraction')
    ax.text(.5,.1,'Unsupported requests and failed checks are not executed; no LLM-generated values are accepted as operational facts.',ha='center',fontsize=9,color='#8d4545',transform=ax.transAxes)
    fig.savefig(ROOT/'figures'/'architecture.png',dpi=210,bbox_inches='tight');plt.close(fig)

    metadata={'study':'Synthetic computational experiment (NOT field validation)','seeds':[SEEDS[0],SEEDS[-1]],
        'replications_per_scenario_policy':len(SEEDS),'policies':POLICIES,'scenarios':SCENARIOS,'orders_per_replication':32,
        'machine_capacities':{m:1 for m in MACHINES},'processing_variability':'triangular(0.8,1.2,mode 1.0)',
        'ci':'4000-replicate paired/nonpaired percentile bootstrap, deterministic seed 393919',
        'python_version':platform.python_version(),'elapsed_sec':round(time.perf_counter()-tic,3),
        'input_sha256':hashlib.sha256((ROOT/'planner_core.py').read_bytes()).hexdigest(),
        'note':'same seed/workload/noise within scenario for policy pair; due/release/routing maintained across disturbance scenario; no human studies, LLM or ERP integrations'}
    (ROOT/'data'/'run_metadata.json').write_text(json.dumps(metadata,indent=2))
    print('Completed',len(raw),'policy evaluations in',metadata['elapsed_sec'],'s')
    for line in summ: print(line['scenario'],line['policy'],'tardiness',line['mean_tardiness_mean'],'on_time',line['on_time_pct_mean'])
    print('Paired results:')
    for line in paired:
        if line['metric']=='mean_tardiness':print(line)

if __name__=='__main__':main()
