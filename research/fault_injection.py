"""Checker challenge: deterministic, constraint-violating schedule mutations.
No claim to detect plausible-but-incorrect source data or adversarial model attacks.
"""
from pathlib import Path
from dataclasses import replace
import csv, json
from planner_core import synthetic_orders, schedule, processing_noise, scenario_outages, verify_schedule
ROOT=Path(__file__).resolve().parent
KINDS=['missing_operation','duplicate_operation','wrong_machine','duration_tamper',
       'early_material_start','precedence_collision','outage_overlap']

def mutate(kind,ops,jobs):
    out=ops[:]
    if kind=='missing_operation':return out[1:]
    if kind=='duplicate_operation':return out+[out[0]]
    if kind=='wrong_machine':out[0]=replace(out[0],machine='FAKE');return out
    if kind=='duration_tamper':out[0]=replace(out[0],duration=out[0].duration+1.0,end=out[0].end+1.0);return out
    if kind=='early_material_start':
        id=jobs[0].id;target=next(i for i,x in enumerate(out) if x.order==id and x.stage==0)
        o=out[target];newstart=max(0.0,max(jobs[0].release,jobs[0].material_ready)-1.0)
        out[target]=replace(o,start=newstart,end=newstart+o.duration);return out
    if kind=='precedence_collision':
        job=jobs[0];a=next(x for x in out if x.order==job.id and x.stage==0)
        k=next(i for i,x in enumerate(out) if x.order==job.id and x.stage==1)
        o=out[k];s=a.start+0.1
        out[k]=replace(o,start=s,end=s+o.duration);return out
    if kind=='outage_overlap':
        k=next(i for i,x in enumerate(out) if x.machine=='CNC')
        o=out[k];s=80.0
        out[k]=replace(o,start=s,end=s+o.duration);return out
    raise ValueError(kind)

def main():
    records=[]
    for seed in range(202800,202830):
        jobs=synthetic_orders(seed,32,'machine_disruption')
        factors=processing_noise(jobs,seed);outages=scenario_outages('machine_disruption')
        source=schedule(jobs,'EDD',outages,factors)
        assert verify_schedule(jobs,source,outages,factors)
        for kind in KINDS:
            bad=mutate(kind,source,jobs)
            error='';rejected=False
            try:verify_schedule(jobs,bad,outages,factors)
            except (AssertionError,ValueError,KeyError,IndexError,TypeError) as ex:
                rejected=True;error=type(ex).__name__+': '+str(ex)
            records.append({'seed':seed,'mutation':kind,'rejected':rejected,'diagnostic':error})
    assert len(records)==210
    assert all(r['rejected'] for r in records),[r for r in records if not r['rejected']]
    with (ROOT/'data'/'fault_injection_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
    summary={'valid_schedules_checked':30,'fault_types':KINDS,'faults_injected':len(records),'faults_rejected':sum(x['rejected'] for x in records),
             'scope':'Only injected structural infeasibility in represented constraints; not field truth, malicious input, cybersecurity or model fidelity',
             'test_seed_range':[202800,202829]}
    (ROOT/'data'/'fault_injection_summary.json').write_text(json.dumps(summary,indent=2));print(summary)
if __name__=='__main__':main()
