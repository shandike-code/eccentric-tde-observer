"""Current 86304 source interface. No initialization, mapping, feedback or ODE.

The externally reviewed manifest is prepared separately; this module never creates
it or upgrades synthetic evidence into production source qualification.
"""
import hashlib
import io
import os
from pathlib import Path
import sys
import numpy as np
from operations import x20_86304_radiation_contract as c
from handoff.audit_tools import bind_x20_86304_radiation as adapter

PHYSICAL={'physical_old_time_level':'33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455',
          'outer_base_material':'36434a29123e2387195b77713baffaecd046f7d6c0297a5d0d95a74319e22eda',
          'base_residual':'b6f337ce30d323acada31ea9f3e1772ccb2be1075753f432ab13a8e299ee2a45'}
ARCHIVES=[(303877902,'f20c313bc92af5730a16d7a9c604793873719bd710b53d0fc763813349cd120c'),(154064839,'595a01a5373980afd28acdb7224cd74321561da005892297e0995f5c9207a0b8')]

def relative(path):
    p=Path(path)
    if type(path) is not str or p.is_absolute() or '..' in p.parts or not p.parts: raise ValueError('source relative path')
    return p

def validate_manifest(m):
    if m['schema']!='86304-live-sources-v1' or m['source_job']!=86304 or type(m['source_job']) is not int: raise ValueError('live source identity')
    c.check_binding(m['binding'])
    rows=m['files']; paths=[x['path'] for x in rows]
    if not rows or len(set(paths))!=len(paths): raise ValueError('unique explicit sources')
    for x in rows:
        p=relative(x['path']); n=x['size_bytes']
        if type(n) is not int or not 0<=n<=32*1024**2 or p.suffix not in ('.json','.npz','.npy','.py'): raise ValueError('bounded source type')
        if p.suffix=='.npz' and n>=1024**2 and (n,x['sha256'])!=(17159976,PHYSICAL['physical_old_time_level']): raise ValueError('NPZ limit')
        if len(x['sha256'])!=64 or any(y not in '0123456789abcdef' for y in x['sha256']): raise ValueError('source SHA')
    known={x['path']:x for x in rows}
    for row in m['binding']['checked_sources']:
        if not c.exact(row,known.get(row['path'])): raise ValueError('missing authenticated JSON source')
    for role,sha in PHYSICAL.items():
        if known[m['roles'][role]]['sha256']!=sha: raise ValueError('physical identity')
    for branch in ('accelerated','historical'):
        roles=m['branches'][branch]
        for key in ('config','trial','native_trial_audit','initialized_identity'):
            if roles[key] not in known: raise ValueError('missing branch input')
        if roles['config']!=f'{c.RUN}/{branch}/config.json' or roles['trial']!=f'{c.RUN}/{branch}/trial_material.npz': raise ValueError('current branch path')
        if known[roles['trial']]['sha256']!=PHYSICAL['outer_base_material']: raise ValueError('current trial SHA')
    if [(x['size_bytes'],x['sha256']) for x in m['archives']]!=ARCHIVES: raise ValueError('both authenticated archives')
    for x in m['archives']:
        relative(x['path'])
        if not x['path'].endswith('.tar.gz'): raise ValueError('archive suffix')
    # 本数值是显式前后认证读取；native自行打开的来源另有审计记录，不能称设备I/O。
    expected=2*sum(x['size_bytes'] for x in rows)+sum(x[0] for x in ARCHIVES)
    if type(m['payload_bytes_per_check']) is not int or m['payload_bytes_per_check']!=expected: raise ValueError('source payload contract')
    if not m['expected_native'] or not m['expected_opened_paths']: raise ValueError('independently frozen native/runtime required')
    if any(p not in known for p in m['expected_opened_paths']): raise ValueError('unbound native input')

def array_fingerprint(a):
    a=np.asarray(a)
    if a.dtype.hasobject or (a.dtype.kind in 'fc' and not np.isfinite(a).all()): raise ValueError('nonfinite/object physical array')
    return dict(dtype=a.dtype.str,shape=list(a.shape),sha256=hashlib.sha256(a.tobytes()).hexdigest())

def arrays(raw):
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        out={k:z[k] for k in z.files}
    for a in out.values(): array_fingerprint(a)
    return out

def same(a,b):
    if set(a)!=set(b) or any(array_fingerprint(a[k])!=array_fingerprint(b[k]) for k in a): raise ValueError('full trial arrays differ')

def native_facts(trial,material,context):
    facts={}
    for field,parent in (('density_g_cm3','density_parent'),('temperature_k','temperature_parent'),('hydrogen_fraction','hydrogen_parent'),('helium_fraction','helium_parent')):
        expected=np.concatenate((trial[field],trial[field][::-1]),axis=0)
        facts[parent]=array_fingerprint(material[parent])
        if facts[parent]!=array_fingerprint(expected): raise ValueError('native mirror '+field)
    if type(context['phase']) is not int or context['phase']!=1367 or context['duration_s']!=889.419892762322: raise ValueError('phase/dt')
    if len(context['mu'])!=32 or len(context['beta'])!=4096 or len(context['blocks'])!=76: raise ValueError('native geometry')
    for i,b in enumerate(context['blocks']):
        if type(b.core_group_start) is not int or type(b.core_group_stop) is not int or b.core_group_start!=i*128 or b.core_group_stop!=min((i+1)*128,9632): raise ValueError('native ownership')
    return facts

def validate_archived_chain(blobs,m):
    base='outputs/review-20260925/x20-relaxed-feedback-86304-final-received/'
    oldbase='outputs/review-20260925/x20-85875-matched-85889-received/'
    get=lambda name:c.loads(blobs[base+name])
    seeds=get('seed-claims.json'); decl=get('declaration.json')
    if not c.exact(seeds,decl['seeds']) or not c.exact(seeds,m['binding']['seeds']): raise ValueError('seed declaration')
    for branch in ('accelerated','historical'):
        state=get(branch+'/state.json'); cfg=get(branch+'/config.json')
        live_cfg=c.loads(blobs[m['branches'][branch]['config']])
        if not c.exact(cfg,live_cfg): raise ValueError('live versus archived config')
        old=c.loads(blobs[oldbase+branch+'/endpoints-map16/manifest.json'])['endpoints']['mapped_final']
        receipts={n:[get(f'{branch}/map{n:04d}/block{i:02d}.json') for i in range(76)] for n in (7,8)}
        found=adapter.validate_branch(branch,state,cfg,get(branch+'/endpoints-map08/manifest.json'),get(branch+'/pair08/feedback_protocol.json'),seeds[branch],old,receipts)
        if not c.exact(found,m['binding']['fields'][branch]): raise ValueError('binding endpoint disagreement')


def check(repo,m,guard):
    validate_manifest(m); repo=Path(repo).resolve(); blobs={}
    def read_all():
        for row in m['files']:
            guard.check(); raw=c.bounded_bytes(repo/row['path'],row['size_bytes'])
            if len(raw)!=row['size_bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']: raise ValueError('live source bytes')
            if Path(row['path']).suffix=='.json': c.loads(raw)
            blobs[row['path']]=raw
    read_all()
    validate_archived_chain(blobs,m)
    # 当前JSON适配绑定独立外部清单；实际生产准备必须先审阅这份完整清单。
    for branch in ('accelerated','historical'):
        cfg=c.loads(blobs[m['branches'][branch]['config']])
        if cfg['run']!=f'{c.RUN}/{branch}' or cfg['maximum_maps']!=8 or type(cfg['maximum_maps']) is not int: raise ValueError('current config')
        if not c.exact(cfg['warm_seed'],m['binding']['seeds'][branch]): raise ValueError('old mapped seed')
    base=arrays(blobs[m['roles']['outer_base_material']]); old=arrays(blobs[m['roles']['physical_old_time_level']])
    r20=np.load(io.BytesIO(blobs[m['roles']['base_residual']]),allow_pickle=False)
    for key in ('encoded_state','base_encoded_state','finite_direction','base_residual','relaxation'):
        if key not in base: raise ValueError('five trial arrays required')
    if (array_fingerprint(base['finite_direction'])!=array_fingerprint(r20) or
        array_fingerprint(base['base_residual'])!=array_fingerprint(r20) or
        array_fingerprint(base['encoded_state'])!=array_fingerprint(base['base_encoded_state']) or
        float(base['relaxation'])!=0 or int(base['phase_index'])!=1367 or float(base['step_duration_s'])!=889.419892762322 or
        array_fingerprint(base['density_g_cm3'])!=array_fingerprint(old['density_g_cm3'][1367]) or float(old['step_duration_s'][1367])!=889.419892762322): raise ValueError('x20 old/base/r20')
    active=[False]; seen=set(); opens=[]
    forbidden={'run_pipeline','migrate_trial','initialize','initialize_run','run_worker','run_map','frozen_radiation_material_response','zero_feedback','_run_feedback_state'}
    def profile(frame,event,arg):
        if active[0] and event=='call' and frame.f_code.co_name in forbidden: raise RuntimeError('forbidden production operation in native configuration')
    def audit(event,args):
        if not active[0]: return
        if event in ('subprocess.Popen','os.fork','os.posix_spawn'): raise RuntimeError('no native subprocess')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).absolute()
            if p.suffix=='.dat': raise RuntimeError('native dat forbidden')
            if p.suffix in ('.npz','.npy','.json') and not p.is_relative_to(Path(sys.prefix).resolve()):
                if not p.is_relative_to(repo): raise RuntimeError('foreign native input')
                rel=p.relative_to(repo).as_posix()
                if rel not in blobs: raise RuntimeError('unfrozen native input')
                seen.add(rel); opens.append(rel)
    sys.addaudithook(audit)
    from hpc import pipeline
    if pipeline.ROOT.resolve()!=repo: raise ValueError('native checkout')
    facts={}; saved=sys.dont_write_bytecode; sys.dont_write_bytecode=True
    previous_profile=sys.getprofile()
    try:
        sys.setprofile(profile)
        active[0]=True
        for branch in ('accelerated','historical'):
            guard.check(); roles=m['branches'][branch]; trial=arrays(blobs[roles['trial']]); same(trial,base)
            cfg=c.loads(blobs[roles['config']])
            native,fixed,template,context=pipeline.configure_native(cfg,repo/cfg['warm_seed']['path'])
            from operations.common_step21_directions import exact_trial
            exact_trial(trial,base,r20,old,'control')
            facts[branch]=native_facts(trial,native.base.phase7b7i._second_full_material(template),context)
            facts[branch]['specific_material_energy_erg_g']=array_fingerprint(trial['specific_material_energy_erg_g'])
            current=fixed['sources']['current_material_state']
            row=next(x for x in m['files'] if x['path']==roles['trial'])
            if not c.exact(current,row): raise ValueError('configured trial source')
    finally:
        active[0]=False; sys.setprofile(previous_profile); sys.dont_write_bytecode=saved
    if not c.exact(facts,m['expected_native']) or sorted(seen)!=m['expected_opened_paths']: raise ValueError('independent native/runtime expectation')
    read_all()
    from operations import x20_85889_chord_scan as core
    archive=[dict(x,path=str(repo/x['path'])) for x in m['archives']]
    hashes=core.hash_pass(archive,[core.checked_stat(x) for x in archive],guard)
    return dict(schema='86304-live-proof-v1',source_job=86304,manifest_sha256=c.document_sha(m),native=facts,
        opened_paths=sorted(seen),opened_occurrences=opens,archive_sha256=hashes,
        authenticated_payload_bytes=m['payload_bytes_per_check'],trial_all_arrays_bitwise_equal=True,
        live_native_recomputed=True,radiation_field_bytes_read=0,physical_validation=False,strict_error_bound=False)
