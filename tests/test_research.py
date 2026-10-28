from dataclasses import replace
import pytest
from research import planner_core as p
from research import external_benchmarks as b

def test_original_research_example():
    jobs=p.synthetic_orders(202600,32,'machine_disruption')
    fac=p.processing_noise(jobs,202600)
    for policy in p.POLICIES:
        ops=p.schedule(jobs,policy,p.scenario_outages('machine_disruption'),fac)
        assert p.verify_schedule(jobs,ops,p.scenario_outages('machine_disruption'),fac)

def test_checker_rejects_machine_overlap():
    jobs=[p.Order('A1',1,0,10,0,(p.Step('CUT',1),)),p.Order('B2',1,0,10,0,(p.Step('CUT',1),))]
    bad=[p.Operation('A1',0,'CUT',0,1,1),p.Operation('B2',0,'CUT',0.5,1.5,1)]
    with pytest.raises(AssertionError,match='machine overlap'):
        p.verify_schedule(jobs,bad)

def test_checker_rejects_incorrect_duration():
    jobs=[p.Order('A1',2,0,10,0,(p.Step('CUT',1),))]
    bad=[p.Operation('A1',0,'CUT',0,1,1)]
    with pytest.raises(AssertionError,match='scheduled duration'):
        p.verify_schedule(jobs,bad,processing_factors={('A1',0):1.0})

def test_benchmark_known_optima():
    for name,opt in b.OPT.items():
        jobs,machines=b.load_instance(name)
        assert len(jobs) in [6,10]
        assert b.quality(b.greedy(jobs,machines,'FIFO'))>=opt
        assert b.quality(b.greedy(jobs,machines,'SPT'))>=opt

def test_benchmark_setup_feasibility():
    jobs,machines=b.load_instance('ft06')
    operations=b.greedy(jobs,machines,'MWKR',setup_hours=5)
    assert b.check(jobs,machines,operations,setup_hours=5)
