"""Current native inputs/code and archive identity; no radiation-field reads."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import numpy as np
from operations import x20_85889_chord_binding as b
from operations import x20_85889_chord_scan as core


def check_native_arrays(trial, material, context):
    for field,parent in (('density_g_cm3','density_parent'),('temperature_k','temperature_parent'),
                         ('hydrogen_fraction','hydrogen_parent'),('helium_fraction','helium_parent')):
        expected=np.concatenate((trial[field],trial[field][::-1]),axis=0)
        actual=material[parent]
        if actual.dtype!=expected.dtype or actual.shape!=expected.shape or actual.tobytes()!=expected.tobytes():
            raise ValueError('live native mirrored trial differs: '+field)
    if context['phase']!=1367 or context['duration_s']!=889.419892762322:
        raise ValueError('live native physical phase/dt')
    if len(context['blocks'])!=76 or len(context['mu'])!=32 or len(context['beta'])!=4096:
        raise ValueError('live native production geometry')
    expected=0
    for block in context['blocks']:
        if block.core_group_start!=expected or block.core_group_stop<=expected:
            raise ValueError('live native group ownership')
        expected=block.core_group_stop
    if expected!=9632:raise ValueError('live native full group coverage')


def merge_claims(rows):
    out={}
    for c in rows:
        b.relative_path(c["path"])
        if c["path"] in out and out[c["path"]]!=c:
            raise ValueError("conflicting dependency claims")
        out[c["path"]]=c
    return out


def live_check(repo,bound,guard):
    repo=Path(repo).resolve()
    # 新审阅工具独立添加；原801份实现必须仍逐字节等于9555a78的声明。
    for c in bound['source_code']:
        guard.check();b.small_bytes(repo/c['path'],c['sha256'],c['size_bytes'])
    declaration=json.loads((repo/b.RUN/'declaration.json').read_text())
    configs=[]
    for branch in ('accelerated','historical'):
        c=next(c for c in bound['small_sources'] if c['path']==branch+'/config.json')
        raw=b.small_bytes(repo/b.RUN/c['path'],c['sha256'],c['size_bytes'])
        configs.append(json.loads(raw))
    # 顶层declaration不含所有runtime模板；按已认证的两支config.sources闭合。
    known=merge_claims(declaration['claims']+declaration['code']+
                       [c for cfg in configs for c in cfg['sources']])
    dependency_claims={}
    def pinned(path,claim=None):
        c=known[path] if claim is None else claim
        if c['path']!=path:raise ValueError('dependency claim path')
        if 'size_bytes' not in c:
            full=known[path]
            if any(full.get(k)!=v for k,v in c.items()):raise ValueError('legacy dependency claim differs')
            c=full
        guard.check();raw=b.small_bytes(repo/b.relative_path(path),c['sha256'],c['size_bytes'])
        dependency_claims[path]=c
        return raw
    fixed_path='outputs/phase7b9dh_fixed_material_radiation_worker_template.json'
    fixed=json.loads(pinned(fixed_path))
    template_claim=fixed['sources']['phase7b7i_template_protocol']
    template=json.loads(pinned(template_claim['path'],template_claim))
    for name in ('phase7b4r_material','phase7b5p_master_input'):
        c=template['sources'][name];pinned(c['path'],c)
    branch_inputs=[]
    for branch in ('accelerated','historical'):
        rel=f'{b.RUN}/{branch}'
        # 已由绑定器按85889清单核验config/trial，重复读取前再次绑定实际字节。
        cfg_claim=next(c for c in bound['small_sources'] if c['path']==branch+'/config.json')
        raw=b.small_bytes(repo/rel/'config.json',cfg_claim['sha256'],cfg_claim['size_bytes'])
        cfg=json.loads(raw)
        tc=next(c for c in bound['small_sources'] if c['path']==branch+'/trial_material.npz')
        tc=dict(tc,path=rel+'/trial_material.npz');pinned(tc['path'],tc)
        branch_inputs.append((cfg,tc))
    active=[False];seen=set();environment_reads=set()
    environment_root=Path(sys.prefix).resolve()
    def audit(event,args):
        if active[0] and event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(args[0])).absolute()
            if path.suffix=='.dat':raise RuntimeError('native audit must not open radiation fields')
            if path.is_relative_to(environment_root):
                if path.suffix in ('.npz','.npy','.json'):environment_reads.add(str(path))
                return
            if path.is_relative_to(repo) and path.suffix in ('.npz','.npy','.json'):
                rel=path.relative_to(repo).as_posix()
                if rel not in dependency_claims:raise RuntimeError('unverified live native dependency: '+rel)
                seen.add(rel)
    sys.addaudithook(audit)
    saved=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    try:
        active[0]=True
        from hpc import pipeline
        if pipeline.ROOT.resolve()!=repo:raise ValueError('native imported from different repository')
        for cfg,tc in branch_inputs:
            guard.check()
            trial=b.load_arrays(repo/tc['path'])
            native,fixed_live,template_live,context=pipeline.configure_native(cfg,repo/cfg['warm_seed']['path'])
            check_native_arrays(trial,native.base.phase7b7i._second_full_material(template_live),context)
            if fixed_live['sources']['current_material_state']!=tc:raise ValueError('native trial source claim')
    finally:
        active[0]=False;sys.dont_write_bytecode=saved
    for c in dependency_claims.values():pinned(c['path'],c)
    archive=dict(bound['source_archive'],path=str(repo/bound['source_archive']['path']))
    initial=[core.checked_stat(archive)];archive_sha=core.hash_pass([archive],initial,guard)[0]
    import scipy
    env_data=[]
    for name in sorted(environment_reads):
        path=Path(name)
        if path.exists():
            if path.is_symlink() or not path.is_file() or path.stat().st_size>32*1024**2:
                raise ValueError('environment metadata budget/type')
            raw=path.read_bytes()
            env_data.append(dict(path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        else:env_data.append(dict(path=name,exists=False))
    guard.check()
    return dict(live_native_recomputed=True,trial_mirrored_arrays_bitwise=True,phase=1367,dt=889.419892762322,
        groups=9632,directions=32,depths=4096,blocks=76,live_original_code_files=len(bound['source_code']),
        live_dependencies=list(dependency_claims.values()),native_opened_data_paths=sorted(seen),
        archive_payload_rehashed=True,archive_sha256=archive_sha,archive_bytes_read=archive['size_bytes'],
        archive_stat=initial[0],radiation_field_bytes_read=0,
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,machine=platform.machine()),

        environment_metadata_reads=env_data,
        physical_validation=False,strict_error_bound=False)
