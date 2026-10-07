import copy

import hashlib

import json

import os

from pathlib import Path

import signal

import numpy as np

import pytest

from operations import x20_86304_radiation_resource as d

from operations import x20_86304_radiation_contract as c

from operations import x20_86304_radiation_receipt as receipt

from handoff.audit_tools import review_x20_86304_radiation_resource as review

from tests.test_x20_85889_chord_resource import fixture

def small(tmp_path):
    claims = fixture(tmp_path)
    old = d.v1.probe(claims, [33,2,3], d.core.Guard())
    data = d.authenticated_probe(claims, [33,2,3], d.core.Guard())
    return data, old

def test_explicit_same_buffers_once(tmp_path, monkeypatch):
    claims = fixture(tmp_path); old = d.v1.probe(claims, [33,2,3], d.core.Guard())
    original = d.diagonal.slab_statistics; calls = []
    def kernel(fields, check):
        calls.append(1)
        for field, claim in zip(fields, claims):
            assert not field.flags.writeable
            assert field.tobytes() == Path(claim['path']).read_bytes()[:field.nbytes]
            root = field
            while isinstance(root, np.ndarray): root = root.base
            assert type(root) is bytes
        return original(fields, check)
    monkeypatch.setattr(d.diagonal, 'slab_statistics', kernel)
    monkeypatch.setattr(d.core, 'slab_statistics', lambda *args:pytest.fail('old kernel called'))
    out = d.authenticated_probe(claims, [33,2,3], d.core.Guard())
    assert calls == [1] and out['field_bytes_read'] == 37440
    assert review.review(json.loads(json.dumps(out)))['decimal_precision'] == 80

@pytest.mark.parametrize('raw', ['{"a":1,"a":2}', '{"x":NaN}', '[Infinity]', '[-Infinity]', '[1e999]'])
def test_json_reject(raw):
    with pytest.raises(ValueError): c.loads(raw)

def test_signed_zero_and_bool():
    assert not c.exact(0.0, -0.0) and not c.exact(0, False)
    assert not c.exact('0e+00', '-0e+00')

@pytest.mark.parametrize('change', ['tail_before','after_hash','after_probe'])
def test_source_mutation(tmp_path, change):
    claims = fixture(tmp_path)
    def mutate():
        with open(claims[0]['path'], 'r+b') as f: f.seek(32*2*3*8); f.write(np.array([123.]).tobytes())
    def progress(name, data):
        if (change == 'after_hash' and name == 'field-hash-before') or (change == 'after_probe' and name == 'probe'): mutate()
    if change == 'tail_before': mutate()
    with pytest.raises(ValueError): d.authenticated_probe(claims, [33,2,3], d.core.Guard(), progress=progress)

@pytest.mark.parametrize('change', ['order','overlap','duration','rate','payload','rss','nan','calls','bool'])
def test_phase_or_count_corruption(tmp_path, change):
    data, old = small(tmp_path); row = data['phases'][1]
    if change == 'order': data['phases'].reverse()
    elif change == 'overlap': row['start_s'] = 0
    elif change == 'duration': row['seconds'] += 1
    elif change == 'rate': row['payload_bytes_per_second'] += 1
    elif change == 'payload': row['payload_bytes'] += 1
    elif change == 'rss': row['cumulative_peak_rss_bytes'] = 6442450944
    elif change == 'nan': row['end_s'] = float('nan')
    elif change == 'calls': data['kernel_calls'] = 2
    else: data['kernel_calls'] = True
    with pytest.raises(ValueError): review.review(data)

@pytest.mark.parametrize('kind', ['signal','wall','rss','exception'])
def test_failure_lifecycle(tmp_path, kind):
    def work(guard, out, timeline):
        if kind == 'signal': os.kill(os.getpid(), signal.SIGUSR1)
        if kind == 'wall': guard.seconds = 0
        if kind == 'rss': guard.rss_bytes = 1
        if kind == 'exception': raise ValueError('deliberate fixture error')
        guard.check()
    out = tmp_path/'run'
    assert d.execute(out, work) == 1
    assert (out/'failure.json').exists() and not (out/'finished.json').exists()
    with pytest.raises(ValueError): review.review_evidence(out, '', {}, {}, '123')

def scheduler_fixture():
    result = dict(job_id='123'); started = dict(started_unix=1)
    alloc = dict(job_id='123', observed_unix=2, scontrol='JobId=123 JobState=RUNNING NumCPUs=4 NumTasks=1 NumNodes=1 Partition=Students QOS=qos_stu_default TimeLimit=00:30:00 MinMemoryNode=16G')
    terminal = dict(job_id='123', observed_unix=4, scontrol='JobId=123 JobState=COMPLETED ExitCode=0:0')
    child = dict(job_id='123', child_exit_status=0, recorded_unix=3)
    return result, alloc, terminal, child, '123', started

@pytest.mark.parametrize('change', ['good','oldjob','otherjob','failed','child','childbool','time','node'])
def test_external_terminal(change):
    args = list(scheduler_fixture())
    if change == 'oldjob': args[4] = '86061'
    elif change == 'otherjob': args[4] = '456'
    elif change == 'failed': args[2]['scontrol'] = 'JobId=123 JobState=FAILED ExitCode=1:0'
    elif change == 'child': args[3]['child_exit_status'] = 1
    elif change == 'childbool': args[3]['child_exit_status'] = False
    elif change == 'time': args[2]['observed_unix'] = 1
    elif change == 'node': args[1]['scontrol'] = args[1]['scontrol'].replace('NumNodes=1','NumNodes=2')
    if change == 'good': review.terminal_check(*args)
    else:
        with pytest.raises(ValueError): review.terminal_check(*args)

def test_missing_kernel_code():
    with pytest.raises(ValueError): c.check_code({}, {})

def test_no_scanner_import_in_reviewer():
    import ast
    tree = ast.parse(Path(review.__file__).read_text())
    assert not any(isinstance(n, ast.ImportFrom) and n.module and n.module.startswith('operations.x20_85889_chord_scan') for n in ast.walk(tree))

@pytest.mark.parametrize('change', ['duplicate','shape','sha','boolsize'])
def test_new_driver_claim_gate(tmp_path, change):
    claims = fixture(tmp_path); shape = [33,2,3]
    if change == 'duplicate': claims[-1] = claims[0]
    elif change == 'shape': shape[0] = True
    elif change == 'sha': claims[0]['sha256'] = 'bad'
    else: claims[0]['size_bytes'] = True
    with pytest.raises(ValueError): d.authenticated_probe(claims, shape, d.core.Guard())

@pytest.mark.parametrize('kind', ['link','traversal','duplicate','digest','sizebool'])
def test_receive_bad_members(tmp_path, kind):
    import io,tarfile
    name = '../outside.json' if kind == 'traversal' else 'probe.json'
    archive = tmp_path/'bad.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        member = tarfile.TarInfo(name); member.size = 2
        if kind == 'link': member.type = tarfile.SYMTYPE; member.linkname = '/tmp/target'; member.size = 0
        tar.addfile(member,io.BytesIO(b'{}'))
        if kind == 'duplicate': tar.addfile(member,io.BytesIO(b'{}'))
    raw = archive.read_bytes()
    claim = dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                 files=[dict(path=name,size_bytes=True if kind=='sizebool' else 2,
                             sha256='0'*64 if kind=='digest' else hashlib.sha256(b'{}').hexdigest())])
    path = tmp_path/'receipt.json'; path.write_text(json.dumps(claim))
    with pytest.raises(ValueError): receipt.receive(archive,path,tmp_path/'received')
    assert not (tmp_path/'received').exists()

def test_bounded_read_replacement(tmp_path, monkeypatch):
    p=tmp_path/'x.json';p.write_text('{}');original=c.os.open
    def replaced(path,flags):
        p.unlink();p.write_text('{"new":1}')
        return original(path,flags)
    monkeypatch.setattr(c.os,'open',replaced)
    with pytest.raises(ValueError):c.read(p)

def test_small_link_and_size(tmp_path):
    p=tmp_path/'x.json';p.write_text('{}');link=tmp_path/'link.json';link.symlink_to(p)
    with pytest.raises(ValueError):c.read(link)
    with pytest.raises(ValueError):c.bounded_bytes(p,1)

def test_duplicate_scheduler_tokens():
    args=list(scheduler_fixture());args[2]['scontrol']+=' JobId=123'
    with pytest.raises(ValueError):review.terminal_check(*args)
    with pytest.raises(ValueError):receipt.parse_terminal('123',args[2]['scontrol'])

@pytest.mark.parametrize('mode', ['call','log','ignore','raise'])
def test_unapproved_errstate_before_field_io(tmp_path, monkeypatch, mode):
    claims = fixture(tmp_path)
    monkeypatch.setattr(d.core,'hash_pass',lambda *a:pytest.fail('field read before policy rejection'))
    with np.errstate(over=mode):
        with pytest.raises(ValueError, match='errstate'):
            d.authenticated_probe(claims,[33,2,3],d.core.Guard())

def test_runtime_actual_foreign_origin(tmp_path,monkeypatch):
    import sys, types
    foreign=tmp_path/'helper.py';foreign.write_text('pass')
    module=types.ModuleType('operations.foreign');module.__file__=str(foreign)
    monkeypatch.setitem(sys.modules,'operations.foreign',module)
    repo=Path(__file__).resolve().parents[1]
    code={str(p.relative_to(repo)):dict(size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
          for folder in ('operations','handoff','scripts','src','hpc','tests')
          for p in (repo/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.sbatch')}
    with pytest.raises(ValueError, match='foreign'):
        d.runtime_identity(repo,code)

def test_exact_key_sequence():
    assert not c.exact({'a':1,'b':2},{'b':2,'a':1})

def test_entrypoint_code_freeze_and_no_rebinding():
    import ast
    source=Path(d.__file__).read_text();tree=ast.parse(source)
    assert "'code-freeze'" in source and 'contract.read(a.code_freeze)' in source
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
           and node.func.attr=='slab_statistics']
    assert len(calls)==1 and calls[0].func.value.id=='diagonal'
    assert 'FunctionType' not in source and 'seterr(' not in source

@pytest.mark.parametrize('sig', [signal.SIGUSR1,signal.SIGTERM,signal.SIGINT])
def test_each_signal_retained(tmp_path,sig):
    def work(guard,out,timeline):
        os.kill(os.getpid(),sig);guard.check()
    out=tmp_path/'signal-run'
    assert d.execute(out,work)==1
    assert c.read(out/'failure.json')['signals']==[sig]
    assert not (out/'finished.json').exists()

def test_errstate_changed_during_kernel_rejected(tmp_path,monkeypatch):
    claims=fixture(tmp_path);original=d.diagonal.slab_statistics
    def changed(fields,check):
        row=original(fields,check);np.seterr(over='ignore');return row
    monkeypatch.setattr(d.diagonal,'slab_statistics',changed)
    with np.errstate():
        with pytest.raises(ValueError,match='errstate'):
            d.authenticated_probe(claims,[33,2,3],d.core.Guard())


def test_new_lifecycle_and_oracle(tmp_path):
    from handoff.audit_tools.exercise_x20_86304_radiation_resource import exercise
    meta=exercise(tmp_path/'small')
    assert meta['new_field_payload_bytes']==37440 and meta['scalar_matrix_checks']==250
    assert meta['oracle_source_bytes']==9504 and meta['total_synthetic_field_payload_bytes']==46944
    assert meta['archive_roundtrip'] and not meta['production_resource_verified']


def test_native_mirrors_and_all_ownership():
    from types import SimpleNamespace
    from operations.x20_86304_radiation_live import native_facts
    trial={k:np.arange(8,dtype=float).reshape(4,2)+1 for k in ('density_g_cm3','temperature_k','hydrogen_fraction','helium_fraction')}
    names=dict(density_g_cm3='density_parent',temperature_k='temperature_parent',hydrogen_fraction='hydrogen_parent',helium_fraction='helium_parent')
    material={names[k]:np.concatenate((v,v[::-1]),axis=0) for k,v in trial.items()}
    ctx=dict(phase=1367,duration_s=889.419892762322,mu=[0]*32,beta=[0]*4096,blocks=[SimpleNamespace(core_group_start=i*128,core_group_stop=min((i+1)*128,9632)) for i in range(76)])
    assert len(native_facts(trial,material,ctx))==4
    ctx['blocks'][-1].core_group_stop=9631
    with pytest.raises(ValueError):native_facts(trial,material,ctx)
    ctx['blocks'][-1].core_group_stop=9632;material['density_parent'][0,0]+=1
    with pytest.raises(ValueError):native_facts(trial,material,ctx)


def test_ancestor_link_rejected(tmp_path):
    folder=tmp_path/'ordinary';folder.mkdir();p=folder/'small.json';p.write_text('{}')
    link=tmp_path/'linked';link.symlink_to(folder,target_is_directory=True)
    with pytest.raises(ValueError):c.read(link/'small.json')


def test_fixed_current_fields_reject_oldjob(tmp_path):
    from tests.test_x20_86304_radiation_resource_review import fixture as full_fixture
    binding=full_fixture(tmp_path)[3]['binding']
    assert len(c.fields(binding))==6
    for key,value in [('job_id',85889),('job_id',True),('version','old')]:
        changed=copy.deepcopy(binding);changed[key]=value
        with pytest.raises(ValueError):c.fields(changed)
    binding['fields']['historical']['previous']['sha256']='0'*64
    with pytest.raises(ValueError):c.fields(binding)

@pytest.mark.parametrize('fault',['none','oldjob','binding','npz_limit','role_sha','missing_trial','archive','payload_bool','runtime','link_path'])
def test_manifest_contract(fault):
    from operations import x20_86304_radiation_live as live
    repo=Path(__file__).resolve().parents[1]
    binding=c.read(repo/'outputs/review-20260925/20261007-86304-radiation-binding.json')
    m=dict(schema='86304-live-sources-v1',source_job=86304,binding=binding,files=copy.deepcopy(binding['checked_sources']),roles={},branches={},archives=[dict(path=f'archive-{i}.tar.gz',size_bytes=n,sha256=h) for i,(n,h) in enumerate(live.ARCHIVES)],expected_native={'test':'synthetic'},expected_opened_paths=[])
    for role,sha in live.PHYSICAL.items():
        path=role+('.npy' if role=='base_residual' else '.npz');m['roles'][role]=path
        m['files'].append(dict(path=path,size_bytes=1,sha256=sha))
    for b in ('accelerated','historical'):
        roles={k:f'{c.RUN}/{b}/'+name for k,name in [('config','config.json'),('trial','trial_material.npz'),('native_trial_audit','native_trial_audit.json'),('initialized_identity','initialized_identity.json')]}
        m['branches'][b]=roles
        for k,p in roles.items():m['files'].append(dict(path=p,size_bytes=1,sha256=live.PHYSICAL['outer_base_material'] if k=='trial' else 'a'*64))
    m['expected_opened_paths']=[m['roles']['outer_base_material']]
    m['payload_bytes_per_check']=2*sum(r['size_bytes'] for r in m['files'])+sum(x[0] for x in live.ARCHIVES)
    if fault=='oldjob':m['source_job']=85889
    elif fault=='binding':m['binding']['map_receipts']=303
    elif fault=='npz_limit':m['files'][-3]['size_bytes']=1024**2
    elif fault=='role_sha':m['files'][-9]['sha256']='0'*64
    elif fault=='missing_trial':m['branches']['historical']['trial']='missing.npz'
    elif fault=='archive':m['archives'][0]['sha256']='0'*64
    elif fault=='payload_bool':m['payload_bytes_per_check']=True
    elif fault=='runtime':m['expected_opened_paths']=['missing.json']
    elif fault=='link_path':m['files'][-1]['path']='../other.json'
    if fault=='none':live.validate_manifest(m)
    else:
        with pytest.raises((ValueError,KeyError)):live.validate_manifest(m)
