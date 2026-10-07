"""Independent comparison to the previously frozen, separately computed source audit.

Does not import the adapter or a numerical module; does not re-audit production.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

REFERENCE = 'outputs/review-20260925/20261007-86304-radiation-source-check.json'
REF_SIZE = 80888
REF_SHA = '268e14b59e4ef7ad6efc503bff233d23e5b9fb63130fee3feb8aff8fb76b5db4'


def exact_json(path, size, sha):
    p=Path(path)
    if p.suffix!='.json' or any(x.is_symlink() for x in (p,*p.parents)) or size>8*1024**2:
        raise ValueError('read scope')
    with p.open('rb') as f:
        b=f.read(size+1)
    if len(b)!=size or hashlib.sha256(b).hexdigest()!=sha:raise ValueError('size/SHA')
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate key')
            d[k]=v
        return d
    def reject(x):raise ValueError('nonfinite JSON')
    return json.loads(b,object_pairs_hook=pairs,parse_constant=reject)


def review(result, root=Path('.')):
    prior=exact_json(root/REFERENCE,REF_SIZE,REF_SHA)
    ignored={'handoff/evidence/20261006-x20-85889-final-review.json'}
    ignored.update('outputs/review-20260925/x20-85875-matched-85889-received/'+b+'/config.json' for b in ('accelerated','historical'))
    expected=[c for c in prior['checked_sources'] if c['path'] not in ignored]
    if len(expected)!=len({c['path'] for c in expected}):raise ValueError('prior duplicate')
    received=result['checked_sources']
    if len(received)!=len(expected) or {c['path']:c for c in received}!={c['path']:c for c in expected}:raise ValueError('source inventory')
    expected_result=dict(version='86304-json-binding-v1',job_id=86304,
        numerical_commit='fbfe81fb7ec4e9714e256ec460b483130db5c254',
        fields=prior['fields'],seeds=prior['seeds'],map_receipts=304,
        trial_arrays_reloaded=False,large_field_bytes_read=0,large_field_sha_refreshed=False,
        live_native_recomputed=False,submission_ready=False,new_production_authorized=False)
    other={k:v for k,v in result.items() if k!='checked_sources'}
    # JSON textual comparison distinguishes bool from integer and rejects extra fields.
    if json.dumps(other,sort_keys=True,allow_nan=False)!=json.dumps(expected_result,sort_keys=True,allow_nan=False):raise ValueError('identity/result')
    for c in expected:exact_json(root/c['path'],c['size_bytes'],c['sha256'])
    return dict(verified=True,scope='independent frozen prior audit comparison and all selected source bytes',
        checked_sources=len(expected),field_claims=6,reference_sha256=REF_SHA,
        large_field_bytes_read=0,submission_ready=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    b=a.input.read_bytes();result=exact_json(a.input,len(b),hashlib.sha256(b).hexdigest())
    with a.output.open('x') as f:json.dump(review(result),f,indent=2);f.write('\n')
