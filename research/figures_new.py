from pathlib import Path
import csv, json, statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parent; D=ROOT/'data'; F=ROOT/'figures'
R=list(csv.DictReader((D/'external_jobshop_results.csv').open()))
names=['ft06','la01','la02','la03','la04','la05']
methods=['FIFO','SPT','MWKR','ARK1500']
fig,ax=plt.subplots(figsize=(10.2,4.7));x=np.arange(len(names));width=.19
for k,method in enumerate(methods):
 vals=[float(next(r for r in R if r['instance']==name and r['method']==method)['gap_pct']) for name in names]
 ax.bar(x+(k-1.5)*width,vals,width,label=method if method!='ARK1500' else 'ARK (1,500 iterations)')
ax.set_xticks(x,names);ax.set_ylabel('Makespan gap to published optimum (%)')
ax.set_title('Public JSP benchmarks · 6 instances · lower is better')
ax.legend(ncol=4,fontsize=8,loc='upper right');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.tight_layout();fig.savefig(F/'public_jobshop_optimality_gaps.png',dpi=190);plt.close(fig)
M=list(csv.DictReader((D/'milp_subset_results.csv').open()))
fig,ax=plt.subplots(figsize=(9.0,4.1));groups=['FIFO','SPT','EDD']
for i,g in enumerate(groups):
 vals=[float(r['relative_gap_to_certified_opt_pct']) for r in M if r['method']==g]
 ax.scatter([i]*len(vals),vals,s=32,alpha=.68)
 ax.hlines(statistics.mean(vals),i-.18,i+.18,lw=3)
ax.set_xticks(range(3),groups);ax.set_ylim(-.4,11);ax.set_ylabel('Makespan gap to certified MILP optimum (%)')
ax.set_title('Tractable subset · 12 seeds · 6 jobs × 2 operations · no outages')
ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.tight_layout();fig.savefig(F/'milp_subset_gaps.png',dpi=190);plt.close(fig)
H=list(csv.DictReader((D/'holdout_primary.csv').open()))
d=[float(r['difference_EDD_minus_FIFO']) for r in H]
mu=statistics.mean(d)
fig,ax=plt.subplots(figsize=(10.0,4.2));ax.hist(d,bins=16,edgecolor='white',alpha=.8)
ax.axvline(0,linestyle='--',linewidth=2,label='No policy difference');ax.axvline(mu,linestyle='-',linewidth=2,label=f'Paired mean {mu:.3f} h/order')
ax.set_xlabel('EDD − FIFO mean tardiness (h/order; negative favors EDD)');ax.set_ylabel('Number of paired seeds')
ax.set_title('Held-out synthetic disruption study · 100 paired seeds (202700–202799)')
ax.legend(fontsize=8);fig.tight_layout();fig.savefig(F/'holdout_primary_differences.png',dpi=190);plt.close(fig)
S=list(csv.DictReader((D/'setup_stress_results.csv').open()))
fig,ax=plt.subplots(figsize=(9.5,4.3));wid=.24
for k,g in enumerate(['FIFO','SPT','MWKR']):
 vals=[float(next(r for r in S if r['instance']==n and r['method']==g)['delta_makespan']) for n in names]
 ax.bar(x+(k-1)*wid,vals,wid,label=g)
ax.axhline(0,linewidth=.8);ax.set_xticks(x,names);ax.set_ylabel('Change in makespan (benchmark time units)')
ax.set_title('Synthetic setup-family stress · 5 units for cross-family transition')
ax.legend();ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.tight_layout();fig.savefig(F/'setup_stress.png',dpi=190);plt.close(fig)
print('Generated 4 empirical charts')
# Table 6: repeated-seed robustness summary; underlying numbers read from committed CSV.
ARK=list(csv.DictReader((D/'ark_multiseed_summary.csv').open()))
headers=['Instance','Optimum','Best','Mean','Worst','SD','Mean gap','Optimum hits']
cells=[]
for r in ARK:
    cells.append([r['instance'].upper(),f"{int(r['published_optimum']):,}",
        f"{float(r['best_makespan']):.0f}", f"{float(r['mean_makespan']):.2f}",
        f"{float(r['worst_makespan']):.0f}",f"{float(r['sd_makespan']):.2f}",
        f"{float(r['mean_gap_pct']):.2f}%",f"{r['hit_optimum_count']}/20"])
fig,ax=plt.subplots(figsize=(11.1,3.25));ax.axis('off')
table=ax.table(cellText=cells,colLabels=headers,loc='center',cellLoc='center',
               colWidths=[.115,.115,.09,.10,.09,.08,.13,.16])
table.auto_set_font_size(False);table.set_fontsize(10.2);table.scale(1.0,1.62)
for (row,col),cell in table.get_celld().items():
    cell.set_edgecolor('#D3DEE4');cell.set_linewidth(.5)
    if row==0: cell.set_facecolor('#DFEBF1');cell.set_text_props(weight='bold',color='#193E4B')
    elif row%2==0: cell.set_facecolor('#F7FAFC')
    else: cell.set_facecolor('#FFFFFF')
ax.text(.5,.06,'All durations are benchmark time units; gap = 100 × (makespan − optimum) / optimum',
        transform=ax.transAxes,ha='center',va='bottom',fontsize=9,color='#354B58')
fig.tight_layout(pad=.65);fig.savefig(F/'table_ark_multiseed.png',dpi=220,bbox_inches='tight');plt.close(fig)
print('Generated Table 6 repeated-seed summary')
