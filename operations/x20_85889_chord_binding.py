"""Bind a prospective read-only scan to archived 85889 evidence; never open dat.

这里只重核小来源。真实六场SHA与当前native运行环境仍由生产预检负责。
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

COMMIT = '9555a78a77b9025e30405684dee2669d9e43baee'
RUN = 'outputs/hpc/x20-85875-matched-feedback-20261006'
STEM = 'complete-1791262858167332668'
PINS = {
    'inventory': 'ed219eef3121dea9cd23e3e328bdd2de72811e7a51ec4af897855046b82cf99f',
    'source_review': '3e793eaa6a41bf6846a0dd3f1581bf5e1688cce455d6034d3adf0669cd6bfe95',
    'final_review': '61eaea4db3ba0fb87adce29c13ab42bc1f158068e634e9798b67ddc3d16c2729',
    'terminal': '63b353d4b1ff2650ec8f349b7aea2f52ff529cea71df9c3178a61793065ba58a',
}
PHYSICAL_SHA = {
    'outer_base_material':'36434a29123e2387195b77713baffaecd046f7d6c0297a5d0d95a74319e22eda',
    'base_residual':'b6f337ce30d323acada31ea9f3e1772ccb2be1075753f432ab13a8e299ee2a45',
    'physical_old_time_level':'33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455',
}


def relative_path(value):
    p=Path(value)
    if p.is_absolute() or '..' in p.parts or str(p)!=value or value in ('','.'):
        raise ValueError('noncanonical relative path')
    return p


def small_bytes(path, expected_sha, size=None):
    p=Path(path)
    if p.suffix=='.dat' or p.is_symlink() or not p.is_file():
        raise ValueError('regular non-dat small source required')
    # 预先限制长度；不得意外把巨大场读入内存。
    n=p.stat().st_size
    if n>32*1024**2 or (size is not None and n!=size):
        raise ValueError('small source size')
    with p.open('rb') as f:
        raw=f.read(n+1)
    if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=expected_sha:
        raise ValueError('small source SHA/length mismatch: '+str(p))
    return raw


def unique_claims(rows):
    out={}
    for c in rows:
        relative_path(c['path'])
        if c['path'] in out:raise ValueError('duplicate source claim')
        out[c['path']]=c
    return out


def exact_arrays(a,b):
    if set(a)!=set(b):raise ValueError('trial array keys')
    for k in a:
        if a[k].dtype!=b[k].dtype or a[k].shape!=b[k].shape or a[k].tobytes()!=b[k].tobytes():
            raise ValueError('trial array identity: '+k)


def load_arrays(path):
    with np.load(path,allow_pickle=False) as z:
        out={k:np.array(z[k]) for k in z.files}
    if any(v.dtype.kind not in 'biufUS' or
           (v.dtype.kind in 'biuf' and not np.isfinite(v).all()) for v in out.values()):
        raise ValueError('array dtype/nonfinite')
    return out


def endpoint_chain(manifest,state,branch):
    h=state['history'];r=manifest['history_rows'];e=manifest['endpoints']
    if (manifest['new_map_count']!=16 or len(h)!=16 or state['active_map'] is not None
        or r!=h[-2:] or [x['iteration'] for x in h]!=list(range(1,17))
        or any(a['output_sha256']!=b['input_sha256'] for a,b in zip(h,h[1:]))):
        raise ValueError('map lineage')
    names=('previous','final','mapped_final')
    if set(e)!=set(names):raise ValueError('endpoint names')
    hashes=[r[0]['input_sha256'],r[0]['output_sha256'],r[1]['output_sha256']]
    if r[1]['input_sha256']!=hashes[1] or state['current_sha256']!=hashes[2]:
        raise ValueError('map link')
    for name,sha in zip(names,hashes):
        if e[name]!={'path':f'{RUN}/{branch}/endpoints-map16/{name}.dat',
                     'size_bytes':10099884032,'sha256':sha}:
            raise ValueError('endpoint claim')
    return [e[n] for n in names]


def bind(repo,received,inventory,source_review,physical_paths):
    repo=Path(repo);received=Path(received)
    ix=json.loads(small_bytes(inventory,PINS['inventory']))
    previous=json.loads(small_bytes(source_review,PINS['source_review']))
    final=json.loads(small_bytes(repo/'handoff/evidence/20261006-x20-85889-final-review.json',PINS['final_review']))
    terminal=json.loads(small_bytes(repo/'handoff/evidence/20261006-x20-85889-terminal.json',PINS['terminal']))
    tokens=dict(t.split('=',1) for t in terminal['scontrol'].split() if '=' in t)
    if (final['job_id']!=85889 or final['numerical_commit']!=COMMIT or
        not final['numerical_artifacts_complete'] or not final['scheduler_terminal_verified'] or
        any(tokens.get(k)!=v for k,v in {'JobId':'85889','JobState':'COMPLETED','ExitCode':'0:0'}.items())):
        raise ValueError('source completion')
    claims=unique_claims(ix['files']);checked={}
    def read(rel):
        c=claims[rel];raw=small_bytes(received/relative_path(rel),c['sha256'],c['size_bytes'])
        checked[rel]=c
        return json.loads(raw) if rel.endswith('.json') else raw
    for c in previous['checked_small_sources']:
        if claims[c['path']]['sha256']!=c['sha256']:raise ValueError('previous audit binding')
        read(c['path'])
    declaration=read('declaration.json')
    if declaration['git_commit']!=COMMIT or not declaration['git_clean']:
        raise ValueError('source code declaration')
    field_claims=[];configs=[];trials=[]
    for branch in ('accelerated','historical'):
        state=read(branch+'/state.json');cfg=read(branch+'/config.json')
        fields=endpoint_chain(read(branch+'/endpoints-map16/manifest.json'),state,branch)
        if fields!=[previous['fields'][branch][n] for n in ('previous','final','mapped_final')]:
            raise ValueError('six-field identity')
        field_claims+=fields;configs.append(cfg)
        if claims[branch+'/config.json']['sha256']!=state['config_sha256'] or claims[branch+'/trial_material.npz']['sha256']!=state['trial_sha256']:
            raise ValueError('config/trial state binding')
        t=load_arrays(received/branch/'trial_material.npz');trials.append(t)
        native=read(branch+'/native_trial_audit.json');identity=read(branch+'/initialized_identity.json')
        if (identity['native']!=native or not native['native_mirrored_material_exact'] or
            not native['physical_phase_and_dt_exact'] or native['trial_source']['sha256']!=state['trial_sha256']):
            raise ValueError('archived native identity')
        protocol=read(branch+'/pair16/feedback_protocol.json')
        if any(protocol['sources'][n+'_radiation']!=fields[i] for i,n in enumerate(('previous','final'))):
            raise ValueError('feedback P/F inputs')
        for iteration in (15,16):
            rows=[read(branch+f'/map{iteration:04d}/block{i:02d}.json') for i in range(76)]
            if any(row['block_index']!=i or row['core_group_start']!=i*128 or
                   row['core_group_stop']!=min((i+1)*128,9632) or
                   row['input_state_sha256']!=state['history'][iteration-1]['input_sha256']
                   for i,row in enumerate(rows)):
                raise ValueError('map ownership/input')
    if set(configs[0])!=set(configs[1]) or {k for k in configs[0] if configs[0][k]!=configs[1][k]}!={'run','warm_seed','sources'} or configs[0]['shape']!=[9632,32,4096]:
        raise ValueError('operator config')
    exact_arrays(trials[0],trials[1]);exact_arrays(trials[0],load_arrays(received/'inputs/trial_material.npz'))
    physical={}
    for key,sha in PHYSICAL_SHA.items():
        c=protocol['sources'][key]
        if c['sha256']!=sha:raise ValueError('frozen physical SHA')
        small_bytes(physical_paths[key],sha,c['size_bytes']);physical[key]=dict(c,local_path=str(physical_paths[key]))
    base=load_arrays(physical_paths['outer_base_material']);old=load_arrays(physical_paths['physical_old_time_level'])
    r=np.load(physical_paths['base_residual'],allow_pickle=False)
    exact_arrays(trials[0],base)
    if (not np.array_equal(base['base_residual'],r) or float(base['relaxation'])!=0 or
        not np.array_equal(base['encoded_state'],base['base_encoded_state']) or
        int(base['phase_index'])!=1367 or float(base['step_duration_s'])!=889.419892762322 or
        not np.array_equal(base['density_g_cm3'],old['density_g_cm3'][1367]) or
        float(old['step_duration_s'][1367])!=889.419892762322):
        raise ValueError('frozen physical identity')
    # 保存完整旧源码声明并实际git show核；新驱动的源码冻结另外记录。
    code=unique_claims(declaration['code'])
    for c in code.values():
        raw=subprocess.check_output(['git','show',COMMIT+':'+c['path']],cwd=repo)
        if len(raw)!=c['size_bytes'] or hashlib.sha256(raw).hexdigest()!=c['sha256']:
            raise ValueError('source commit bytes')
    return dict(source_job=85889,source_commit=COMMIT,source_archive=final['archive'],
        evidence_pins=PINS,small_sources=list(checked.values()),source_code=list(code.values()),
        field_claims=field_claims,physical_sources=physical,shape=[9632,32,4096],
        source_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,
        trial_all_arrays_bitwise_equal=True,archived_native_identity_verified=True,
        live_native_recomputed=False,archive_payload_rehashed=False,large_field_sha_refreshed=False,
        production_preflight_complete=False,large_field_bytes_read=0,new_maps=0,new_feedback=0,new_material=0,
        accepted_outer_steps=20,baseline_replaced=False,reference_calibration_eligible=False,strict_error_bound=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--received',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--source-review',type=Path,required=True)
    p.add_argument('--physical-locations',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    result=bind(Path.cwd(),a.received,a.inventory,a.source_review,json.loads(a.physical_locations.read_text()))
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(small_sources=len(result['small_sources']),code=len(result['source_code']),field_claims=6,dat_bytes_read=0)))
