"""Additional bootstrap method sensitivity; optional scipy/numpy dependencies."""
import csv, json
from pathlib import Path
import numpy as np
from scipy.stats import bootstrap
P=Path(__file__).resolve().parent
rows=list(csv.DictReader((P/'data'/'replications.csv').open()))
key={(r['scenario'],int(r['seed']),r['policy']):float(r['mean_tardiness']) for r in rows}
res=[]
for scenario in ('baseline','material_delay','machine_disruption'):
    data=np.array([key[(scenario,s,'EDD')]-key[(scenario,s,'FIFO')] for s in range(202600,202700)])
    obj={'scenario':scenario, 'contrast':'EDD - FIFO', 'n':100, 'mean':float(data.mean()),'zero_difference_count':int(np.count_nonzero(np.isclose(data,0)))}
    for meth in ('percentile','BCa'):
        ci=bootstrap((data,),np.mean,vectorized=False,method=meth,n_resamples=10000,
                     confidence_level=.95,random_state=np.random.default_rng(431)).confidence_interval
        obj[meth]={'ci_low':float(ci.low),'ci_high':float(ci.high)}
    res.append(obj)
(P/'data'/'bootstrap_method_diagnostic.json').write_text(json.dumps({
 'definition':'Paired replication-level mean tardiness contrasts (EDD - FIFO)',
 'resamples':10000,'rng_seed':431,'methods':['percentile','BCa'],
 'source':'data/replications.csv','results':res},indent=2))
print(json.dumps(res,indent=2))
