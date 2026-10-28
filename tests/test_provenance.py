from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]

def test_provenance_metadata_matches_bundled_data():
    result = client.get('/api/research/provenance')
    assert result.status_code == 200
    data = result.json()
    assert len(data['benchmarks']) == 6
    import hashlib
    for b in data['benchmarks']:
        path = ROOT / 'benchmarks' / f"{b['instance']}.txt"
        assert b['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert b['published_optimum'] > 0
        assert b['jobs'] > 0 and b['machines'] > 0
    assert 'permissions' in data['dataset_status']

def test_provenance_navigation_is_internal_and_attribution_preserved():
    html = client.get('/').text
    assert 'data-page="provenance"' in html
    assert 'page-provenance' in html
    assert 'JSPLIB provenance <span>' not in html
    assert 'https://github.com/tamy0612/JSPLIB' in html
    assert 'Fisher and Thompson' in html and 'Lawrence' in html
    js = client.get('/assets/app.js').text
    assert 'provenance:' in js and 'refreshProvenance' in js

def test_benchmark_result_has_dataset_fingerprint():
    result = client.post('/api/benchmark', json={'instance':'ft06','method':'SPT','iterations':10})
    assert result.status_code == 200, result.text
    sha = result.json()['benchmark_sha256']
    assert len(sha)==64
    assert sha == next(x['sha256'] for x in client.get('/api/research/provenance').json()['benchmarks'] if x['instance']=='ft06')

def test_every_benchmark_instance_and_heuristic_is_feasible():
    from research.external_benchmarks import load_instance, greedy, annealed_random_keys, check, OPT, quality
    for instance, optimum in OPT.items():
        jobs, machines = load_instance(instance)
        for method in ('FIFO', 'SPT', 'MWKR'):
            operations = greedy(jobs, machines, method)
            assert check(jobs, machines, operations)
            assert quality(operations) >= optimum
        operations, accepted_moves = annealed_random_keys(jobs, machines, seed=2100, steps=20)
        assert check(jobs, machines, operations)
        assert quality(operations) >= optimum
        assert 0 <= accepted_moves <= 20

def test_research_release_warnings_visible_in_docs():
    doc = (ROOT/'docs/EXTERNAL_RELEASE_CHECKLIST.md').read_text()
    assert 'NOT YET APPROVED' in doc
    assert 'Third-party data rights' in doc
    assert 'authentication' in doc
    assert 'Software license' in doc
