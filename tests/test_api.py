from __future__ import annotations
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ui_and_health():
    r = client.get('/')
    assert r.status_code == 200 and 'ScheduleNexus Lab' in r.text
    for path in ('/assets/app.js','/assets/styles.css'):
        assert client.get(path).status_code == 200
    assert client.get('/api/health').json()['status'] == 'ok'

def test_catalog_and_example():
    cat = client.get('/api/catalog').json()
    assert len(cat['benchmarks']) == 6
    assert len(cat['models']) == 2
    assert len(client.get('/api/example').json()['orders']) == 8

def test_synthetic_result_verified():
    r=client.post('/api/synthetic',json={'scenario':'machine_disruption','policy':'EDD','count':12,'seed':202600})
    assert r.status_code == 200, r.text
    d=r.json()
    assert d['verified'] and d['model']=='production' and len(d['orders'])==12
    assert len(d['operations'])>=12 and d['run']['input_sha256']

def test_synthetic_repeatable():
    x={'scenario':'material_delay','policy':'FIFO','count':12,'seed':4162}
    a=client.post('/api/synthetic',json=x).json()
    b=client.post('/api/synthetic',json=x).json()
    assert a['operations']==b['operations']
    assert a['metrics']==b['metrics']
    assert a['run']['input_sha256']==b['run']['input_sha256']

def test_custom_schedule_and_contracted_duration():
    payload={'policy':'EDD','orders':[{'id':'ORD-01','quantity':2,'release':0,'due':9,'material_ready':1,'route':[{'machine':'CUT','hours_per_unit':1},{'machine':'QC','hours_per_unit':.5}]}], 'outages':{'CUT':[{'start':0,'end':2}]}}
    r=client.post('/api/schedule',json=payload)
    assert r.status_code==200, r.text
    x=r.json();assert x['operations'][0]['start']==2
    assert x['operations'][0]['duration']==2
    assert x['verified']

def test_outage_and_order_schema_fail_closed():
    payload=client.get('/api/example').json()
    payload['orders'][0]['route'][0]['machine']='BAD'
    assert client.post('/api/schedule',json=payload).status_code==422
    x=client.get('/api/example').json()
    x['outages']={'CUT':[{'start':4,'end':6},{'start':5,'end':8}]}
    assert client.post('/api/schedule',json=x).status_code==422

def test_parse_command_accept_reject():
    good='PLAN ORDER DEMO-77, 3 UNITS RELEASE 5 DUE 95 MATERIAL READY 9 ROUTE CUT:1.5 > CNC:2.0 > QC:0.4'
    a=client.post('/api/commands/parse',json={'command':good})
    assert a.status_code==200 and a.json()['order']['id']=='DEMO-77'
    b=client.post('/api/commands/parse',json={'command':'schedule whenever possible'})
    assert b.status_code==422

def test_compare():
    r=client.post('/api/compare',json={'seed':880,'scenario':'machine_disruption','count':10})
    assert r.status_code==200, r.text
    d=r.json()
    assert [x['method'] for x in d['rows']]==['FIFO','SPT','EDD']
    assert all(x['verified'] for x in d['rows'])

def test_batch():
    r=client.post('/api/batch',json={'first_seed':1288,'replications':3,'count':6,'scenario':'baseline'})
    assert r.status_code==200, r.text
    d=r.json();assert len(d['rows'])==9 and len(d['paired_edd_minus_fifo'])==3

def test_external_benchmark():
    r=client.post('/api/benchmark',json={'instance':'ft06','method':'FIFO','iterations':10})
    assert r.status_code==200, r.text
    d=r.json()
    assert d['verified'] and d['published_no_setup_optimum']==55 and d['makespan']>=55

def test_ark_benchmark_compare():
    r=client.post('/api/benchmark/compare',json={'instance':'ft06','iterations':20,'seed':1200})
    assert r.status_code==200, r.text
    d=r.json();assert len(d['rows'])==4 and all(x['verified'] for x in d['rows'])

def test_api_limits_and_unknown_fields():
    assert client.post('/api/batch',json={'replications':400}).status_code==422
    assert client.post('/api/synthetic',json={'count':10000}).status_code==422
    assert client.post('/api/benchmark',json={'instance':'ft06','iterations':900000}).status_code==422
    assert client.post('/api/synthetic',json={'extra_untrusted':True}).status_code==422

def test_audit_records():
    d=client.get('/api/runs').json()
    assert isinstance(d['rows'],list)
    if d['rows']:
        assert len(d['rows'][0]['input_sha256'])==64


def test_spa_has_all_tabs():
    html=client.get('/').text
    assert all(f'page-{x}' in html for x in ('overview','workbench','compare','benchmarks','batch','evidence'))


def test_external_candidate_verification_and_rejection():
    example=client.get('/api/example').json()
    original=client.post('/api/schedule',json=example)
    assert original.status_code == 200, original.text
    original=original.json()
    payload={'orders':original['orders'],'operations':original['operations'],'outages':original['outages']}
    valid=client.post('/api/verify',json=payload)
    assert valid.status_code == 200 and valid.json()['verified'],valid.text
    payload['operations'][0]['duration'] += 1
    invalid=client.post('/api/verify',json=payload)
    assert invalid.status_code == 422,invalid.text
