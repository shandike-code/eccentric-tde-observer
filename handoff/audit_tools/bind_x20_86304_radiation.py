"""JSON-only 86304 identity adapter; no field, NPZ, native or scheduler access."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat

ROOT = Path('outputs/review-20260925')
RUN = 'outputs/hpc/x20-85889-relaxed-feedback-20261007'
OLD_RUN = 'outputs/hpc/x20-85875-matched-feedback-20261006'
COMMIT = 'fbfe81fb7ec4e9714e256ec460b483130db5c254'
TRIAL = '36434a29123e2387195b77713baffaecd046f7d6c0297a5d0d95a74319e22eda'
BRANCHES = ('accelerated', 'historical')
ENDS = ('previous', 'final', 'mapped_final')
LIMIT = 8 * 1024**2


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path, size, sha):
    """Bounded immutable-buffer read; authenticate those exact parsed bytes."""
    p = Path(path)
    require(p.suffix == '.json' and type(size) is int and 0 <= size <= LIMIT, 'JSON scope')
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink')
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == size, 'size/type')
        raw = f.read(size + 1)
        require(signature(before) == signature(os.fstat(f.fileno())) == signature(p.stat()), 'changed source')
    require(len(raw) == size and hashlib.sha256(raw).hexdigest() == sha, 'SHA')
    def unique(pairs):
        d = {}
        for k, v in pairs:
            require(k not in d, 'duplicate JSON key')
            d[k] = v
        return d
    def finite(value):
        if isinstance(value, float):
            require(math.isfinite(value), 'nonfinite JSON')
        elif isinstance(value, dict):
            for v in value.values(): finite(v)
        elif isinstance(value, list):
            for v in value: finite(v)
    d = json.loads(raw, object_pairs_hook=unique,
                   parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    finite(d)
    return d


def validate_branch(branch, state, config, manifest, protocol, seed, old_m, receipts):
    """Pure identity/ownership checks, suitable for adversarial small fixtures."""
    require(branch in BRANCHES, 'branch')
    require(config['run'] == f'{RUN}/{branch}' and config['maximum_maps'] == 8
            and type(config['maximum_maps']) is int, 'run/map budget')
    require(config['shape'] == [9632, 32, 4096]
            and all(type(n) is int for n in config['shape']), 'shape')
    require(seed == old_m == config['warm_seed'], 'seed mismatch')
    require(seed['path'] == f'{OLD_RUN}/{branch}/endpoints-map16/mapped_final.dat', 'old M path')
    require(seed['size_bytes'] == 10099884032 and type(seed['size_bytes']) is int, 'seed size')
    require(state['trial_sha256'] == TRIAL, 'trial')
    h = state['history']
    require(len(h) == 8 and state['active_map'] is None, 'unsettled history')
    require(all(type(r['iteration']) is int and r['iteration'] == i+1 for i,r in enumerate(h)), 'iterations')
    require(h[0]['input_sha256'] == seed['sha256'], 'initial seed')
    require(all(a['output_sha256'] == b['input_sha256'] for a,b in zip(h,h[1:])), 'broken chain')
    require(type(manifest['new_map_count']) is int and manifest['new_map_count'] == 8
            and manifest['history_rows'] == h[-2:], 'retained history')
    e = manifest['endpoints']
    require(set(e) == set(ENDS), 'endpoint set')
    for k in ENDS:
        c = e[k]
        require(c['path'] == f'{RUN}/{branch}/endpoints-map08/{k}.dat', 'endpoint path')
        require(type(c['size_bytes']) is int and c['size_bytes'] == 10099884032, 'field size')
    require([e[k]['sha256'] for k in ENDS] == [h[6]['input_sha256'],h[6]['output_sha256'],h[7]['output_sha256']], 'P/F/M')
    require(state['current_sha256'] == e['mapped_final']['sha256'], 'current field')
    for k in ENDS[:2]:
        require(protocol['sources'][k+'_radiation'] == e[k], 'feedback P/F')
    require(set(receipts) == {7,8}, 'receipt maps')
    for n, rows in receipts.items():
        require(len(rows) == 76, 'receipt count')
        cursor = 0
        for i, row in enumerate(rows):
            require(all(type(row[k]) is int for k in ('block_index','core_group_start','core_group_stop')), 'ownership types')
            require(row['block_index'] == i and row['core_group_start'] == cursor
                    and row['core_group_stop'] == min((i+1)*128,9632), 'ownership')
            cursor = row['core_group_stop']
            require(row['input_state_sha256'] == h[n-1]['input_sha256']
                    and row['protocol_sha256'] == state['config_sha256'], 'receipt input/config')
        require(cursor == 9632, 'coverage')
    return e


def bind(root=Path('.')):
    checked = []
    def load(p,size,sha):
        d=read_json(root/p,size,sha)
        checked.append(dict(path=str(p),size_bytes=size,sha256=sha))
        return d
    def archive(folder, size, sha):
        base=ROOT/folder
        m=load(base/'ARCHIVE_MANIFEST.json',size,sha)
        claims={c['path']:c for c in m['files']}
        require(len(claims)==len(m['files']), 'duplicate member')
        def get(rel):
            c=claims[rel];return load(base/rel,c['size_bytes'],c['sha256'])
        return claims,get
    old,ol=archive('x20-85875-matched-85889-received',1623461,'ed219eef3121dea9cd23e3e328bdd2de72811e7a51ec4af897855046b82cf99f')
    new,nl=archive('x20-relaxed-feedback-86304-final-received',813404,'cd05603f84054c987f73270cc23f32076e41c2d9b8e8f9f0c8645f458faf96ae')
    audit=load(Path('handoff/evidence/20261007-x20-86304-final-review.json'),57263,'7e680adf4f4f0908f51f8a88b690731955a6493319f795b0e653e5902dadf840')
    require(type(audit['job_id']) is int and audit['job_id']==86304
            and audit['numerical_artifacts_complete'] is True and audit['scheduler_terminal_verified'] is True, 'job identity')
    seeds=nl('seed-claims.json');decl=nl('declaration.json');summary=nl('summary.json')
    require(decl['git_commit']==summary['git_commit_after']==COMMIT and seeds==decl['seeds'], 'commit/seeds')
    fields={};configs=[]
    for b in BRANCHES:
        s=nl(f'{b}/state.json');c=nl(f'{b}/config.json');configs.append(c)
        require(s['config_sha256']==new[f'{b}/config.json']['sha256'], 'config SHA')
        require(new[f'{b}/trial_material.npz']['sha256']==old[f'{b}/trial_material.npz']['sha256']==s['trial_sha256'], 'trial declaration')
        m=nl(f'{b}/endpoints-map08/manifest.json');p=nl(f'{b}/pair08/feedback_protocol.json')
        om=ol(f'{b}/endpoints-map16/manifest.json')['endpoints']['mapped_final']
        receipts={n:[nl(f'{b}/map{n:04d}/block{i:02d}.json') for i in range(76)] for n in (7,8)}
        fields[b]=validate_branch(b,s,c,m,p,seeds[b],om,receipts)
    ignore={'run','sources','warm_seed'}
    require({k:v for k,v in configs[0].items() if k not in ignore}=={k:v for k,v in configs[1].items() if k not in ignore}, 'operator config')
    for c in checked: read_json(root/c['path'],c['size_bytes'],c['sha256'])
    return dict(version='86304-json-binding-v1',job_id=86304,numerical_commit=COMMIT,
                fields=fields,seeds=seeds,checked_sources=checked,map_receipts=304,
                trial_arrays_reloaded=False,large_field_bytes_read=0,large_field_sha_refreshed=False,
                live_native_recomputed=False,submission_ready=False,new_production_authorized=False)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    result=bind()
    with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(output=str(args.output),sources=len(result['checked_sources']))))
