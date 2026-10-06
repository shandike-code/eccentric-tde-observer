import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import numpy as np
import pytest
from operations import x20_85889_chord_diagonal_resource as d
from operations import x20_85889_chord_diagonal_contract as c
from operations import x20_85889_chord_diagonal_receipt as receipt
from handoff.audit_tools import review_x20_85889_chord_diagonal_resource as review
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
    assert review.review(json.loads(json.dumps(out)), old)['decimal_precision'] == 80


@pytest.mark.parametrize('change', ['matrix','extra','missing','order','keys','zero_sign','bool','precision','slice','claim'])
def test_exact_summary_gate(tmp_path, change):
    data, old = small(tmp_path); p = copy.deepcopy(old)
    if change == 'matrix': p['slab']['gram']['value'][0][0] = '123'
    elif change == 'extra': p['slab']['extra'] = 0
    elif change == 'missing': p['slab'].pop('maxima')
    elif change == 'order': p['slab']['pairs'].reverse()
    elif change == 'keys': p['slab'] = dict(reversed(list(p['slab'].items())))
    elif change == 'zero_sign':
        p['slab']['gram']['value'][1][2] = '-0.000000000000000000000000000000000000e+00'
    elif change == 'bool': p['first_group'] = False
    elif change == 'precision': p['arithmetic']['nmant'] += 1
    elif change == 'slice': p['slice_sha256'][0] = '0'*64
    else: p['source_claims'][0]['sha256'] = '0'*64
    with pytest.raises(ValueError): review.review(data, p)


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
    with pytest.raises(ValueError): review.review(data, old)


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
    with pytest.raises(ValueError): review.review_evidence(out, '', {}, {}, '123', {})


def test_history_production_pins(tmp_path):
    for name in c.HISTORY_PINS: (tmp_path/name).write_text('{}')
    with pytest.raises(ValueError): c.history(tmp_path)
    with pytest.raises(ValueError): review.review_run(tmp_path, '', {}, {}, {}, '123', {})


def test_history_fixed_actual_small_bytes(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    source = repo/'outputs/review-20260925/x20-chord-resource-86061-received'
    if not source.exists(): pytest.skip('historical small JSON not in isolated fixture')
    paths = {'history-probe.json':source/'probe.json', 'history-result.json':source/'result.json',
        'history-terminal.json':source/'scheduler-terminal.json',
        'history-review.json':repo/'handoff/evidence/20261006-x20-86061-resource-review.json'}
    for name, path in paths.items(): (tmp_path/name).write_bytes(path.read_bytes())
    assert c.history(tmp_path)[0]['shape'] == [9632,32,4096]
    p = tmp_path/'history-probe.json'; raw = bytearray(p.read_bytes()); raw[-2] ^= 1; p.write_bytes(raw)
    with pytest.raises(ValueError): c.history(tmp_path)


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


def test_receipt_members(tmp_path):
    run = tmp_path/'run'; run.mkdir()
    for name in ('phase-28.json','comparison.json','history-probe.json','code-before.json'): (run/name).write_text('{}')
    (run/'secret.dat').write_text('no')
    result = receipt.archive(run, tmp_path/'small.tar.gz', [])
    assert len(result['files']) == 4 and result['dat_files'] == 0
    with pytest.raises(ValueError): receipt.archive(run, tmp_path/'bad.tar.gz', [run/'secret.dat'])


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


def test_explicit_lifecycle_receipt_roundtrip(tmp_path):
    from handoff.audit_tools.exercise_x20_86191_diagonal_resource import exercise
    out = tmp_path/'e2e'; meta = exercise(out)
    assert meta['archive_roundtrip'] and meta['total_synthetic_field_payload_bytes'] == 55872
    code = c.read(out/'fixture-code.json'); terminal = c.read(out/'fixture-external-terminal.json')
    reference = c.read(out/'fixture-reference.json')
    args = (out/'run', 'synthetic-fixture-not-a-production-commit', code, terminal, '900001', reference)
    result_path = out/'run/result.json'; result = c.read(result_path)
    for mutate in ('kernel','terminal','partial'):
        if mutate == 'kernel':
            bad = copy.deepcopy(code); bad.pop(c.KERNEL)
            with pytest.raises(ValueError): review.review_evidence(args[0],args[1],bad,*args[3:])
        elif mutate == 'terminal':
            bad = copy.deepcopy(terminal); bad['job_id'] = '86061'
            with pytest.raises(ValueError): review.review_evidence(*args[:3],bad,*args[4:])
        else:
            (out/'run/failure.json').write_text('{}')
            with pytest.raises(ValueError): review.review_evidence(*args)
    with pytest.raises(FileExistsError): receipt.receive(out/'small.tar.gz', out/'small.tar.receipt.json', out/'received')


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
