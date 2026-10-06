"""Pure receipt contract. No numerical kernel imports or production pin overrides."""
import hashlib
import json
import math
import os
import stat
from pathlib import Path

STATUS = 'diagonal_resource_complete_requires_review'
OLD_COMMIT = '82aea66f68dd9f1abc27a8268ffd5e1bfa34f418'
KERNEL = 'operations/x20_85889_chord_scan_diagonal.py'
KERNEL_SHA = 'a3737320592fac5511d5f8c979524919b5fd9229e36634b64b7e8437cc0b0896'
HISTORY_PINS = {
    'history-probe.json': (26348, '7ef2572f2b4008f2af9900fd21f6e3f288dd1aa1d9fd7292e4716ffdd4290324'),
    'history-result.json': (37696, 'e56b0b4ec22826e15350dc8be9f464dd166a937bc7b7d62d8eef889b7180c6c2'),
    'history-terminal.json': (1652, 'b2f1c80da309801f8c7359b0f3e1292118de74b9b5b67cf39ca691b6dea2b655'),
    'history-review.json': (520, '506afc8e4d7584c29babe554c2a5681e06d60a2effac81f2b57165339d51863c'),
}
ARITHMETIC = dict(rounding_mode_code=0, nmant=63, maxexp=16384, numpy='2.5.2')
PROBE_PHASES = (['field-hash-before'] +
    [f'{kind}-{i}' for i in range(6) for kind in ('slice-read', 'slice-hash')] +
    ['slab'] + [f'slice-reread-{i}' for i in range(6)] + ['field-hash-after'])
ALL_PHASES = ['allocation-code-history', 'binding-before', 'live-before'] + PROBE_PHASES + [
    'binding-after', 'live-after', 'code-after', 'comparison']


def loads(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError('duplicate JSON key')
            out[key] = value
        return out
    def constant(value): raise ValueError('nonfinite JSON constant: ' + value)
    out = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    def finite(x):
        if type(x) is float and not math.isfinite(x): raise ValueError('nonfinite JSON number')
        if isinstance(x, dict):
            for v in x.values(): finite(v)
        elif isinstance(x, list):
            for v in x: finite(v)
    finite(out)
    return out


def bounded_bytes(path, limit):
    path = Path(path); before = path.lstat()
    signature = lambda x:(x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit: raise ValueError('ordinary bounded file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if signature(os.fstat(stream.fileno())) != signature(before): raise ValueError('small source replaced')
        raw = stream.read(before.st_size+1)
        if (len(raw) != before.st_size or signature(os.fstat(stream.fileno())) != signature(before) or
            signature(path.lstat()) != signature(before)): raise ValueError('small source changed')
    return raw


def read(path):
    return loads(bounded_bytes(path, 32*1024**2))


def scheduler_tokens(text):
    result = {}
    for item in text.split():
        if '=' in item:
            key, value = item.split('=', 1)
            if key in result: raise ValueError('duplicate scheduler key')
            result[key] = value
    return result


def exact(a, b):
    """Type-aware recursive equality; decimal strings and signed float zero survive."""
    if type(a) is not type(b): return False
    if isinstance(a, dict): return list(a) == list(b) and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if type(a) is float: return math.isfinite(a) and math.isfinite(b) and a.hex() == b.hex()
    return a == b


def compare(probe, reference):
    for key in ('shape', 'first_group', 'group_count', 'slice_sha256', 'arithmetic', 'slab'):
        if not exact(probe[key], reference[key]): raise ValueError('historical mismatch: ' + key)
    for p in (probe, reference):
        if len(p['source_claims']) != 6: raise ValueError('six history claims required')
        if any(type(c['size_bytes']) is not int for c in p['source_claims']): raise ValueError('integer size')
    a = [(x['size_bytes'], x['sha256']) for x in probe['source_claims']]
    b = [(x['size_bytes'], x['sha256']) for x in reference['source_claims']]
    if a != b: raise ValueError('historical field identity')
    return dict(complete_slab_exact=True, decimal_strings_and_zero_sign_preserved=True,
                physical_validation=False, full_scan_authorized=False)


def history(directory):
    """Production-only immutable pins. Synthetic tests use compare, never replace pins."""
    blobs = {}; values = {}
    for name, (size, sha) in HISTORY_PINS.items():
        p = Path(directory)/name
        if p.is_symlink() or not p.is_file() or p.stat().st_size != size: raise ValueError('history size/type')
        blob = bounded_bytes(p, size)
        if len(blob) != size or hashlib.sha256(blob).hexdigest() != sha: raise ValueError('history SHA')
        blobs[name] = blob; values[name] = loads(blob)
    p = values['history-probe.json']; result = values['history-result.json']
    terminal = values['history-terminal.json']; review = values['history-review.json']
    tokens = scheduler_tokens(terminal['scontrol'])
    if (result['job_id'] != '86061' or result['git_commit'] != OLD_COMMIT or
        not exact(p, result['probe']) or not exact(p['arithmetic'], ARITHMETIC) or
        any(tokens.get(k) != v for k, v in dict(JobId='86061', JobState='COMPLETED', ExitCode='0:0').items()) or
        review['production_resource_preflight_complete'] is not True or
        review['scheduler_terminal_verified'] is not True): raise ValueError('historical result/review identity')
    return p, blobs


def check_code(manifest, expected):
    if not exact(manifest, expected) or manifest.get(KERNEL, {}).get('sha256') != KERNEL_SHA:
        raise ValueError('external frozen code manifest / diagonal kernel')
    required = ['operations/x20_85889_chord_diagonal_resource.py',
        'operations/x20_85889_chord_diagonal_contract.py', 'operations/x20_85889_chord_diagonal_receipt.py',
        'operations/x20_85889_chord_diagonal_resource.sbatch',
        'handoff/audit_tools/review_x20_85889_chord_diagonal_resource.py',
        'operations/x20_85889_chord_scan.py', 'operations/x20_85889_chord_live.py',
        'operations/x20_85889_chord_binding.py']
    required += ['operations/x20_85889_chord_scan_square.py']
    if manifest.get('operations/x20_85889_chord_scan_square.py', {}).get('sha256') != '61e6c6d559975f7f863282209eb1ad016c4594f7f898f0c7e0a5d515878c862b':
        raise ValueError('frozen square helper SHA')
    if any(k not in manifest for k in required): raise ValueError('missing executable dependency')
    if manifest['operations/x20_85889_chord_scan.py']['sha256'] != '9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643':
        raise ValueError('frozen original kernel SHA')


ERRSTATE = dict(divide='warn', over='warn', under='ignore', invalid='warn')
IDENTITY_REQUIRED = [KERNEL, 'operations/x20_85889_chord_scan_square.py',
    'operations/x20_85889_chord_scan.py', 'operations/x20_85889_chord_binding.py',
    'operations/x20_85889_chord_diagonal_resource.py',
    'operations/x20_85889_chord_diagonal_contract.py',
    'operations/x20_85889_chord_resource.py', 'operations/x20_85889_chord_resource_v2.py']


def check_errstate(value):
    # 键序不属于 NumPy 策略语义；值与键集合均固定，不调用 seterr 修正。
    if type(value) is not dict or value != ERRSTATE: raise ValueError('unapproved NumPy errstate')


def document_sha(value):
    """External ticket hashes canonical JSON content, never a claimed file SHA."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def check_identity(identity, code, production=False):
    check_errstate(identity['errstate'])
    root = Path(identity['checkout'])
    if not root.is_absolute() or '..' in root.parts: raise ValueError('identity checkout')
    modules = identity['modules']; paths = set()
    if type(modules) is not dict or not modules: raise ValueError('module origins missing')
    for name, row in modules.items():
        relative = row['relative_path']; p = Path(relative)
        if p.is_absolute() or '..' in p.parts or relative not in code: raise ValueError('unfrozen imported module')
        if (row['file'] != str(root/p) or row['origin'] != row['file'] or
            not exact(row['fingerprint'], code[relative])): raise ValueError('import origin/SHA')
        paths.add(relative)
    required = IDENTITY_REQUIRED + (['operations/x20_85889_chord_live.py'] if production else [])
    if any(p not in paths for p in required): raise ValueError('missing actual imported dependency')
    environment = identity['environment']
    for k in ('executable', 'numpy_file', 'numpy_origin'):
        if not Path(environment[k]).is_absolute(): raise ValueError('environment path')
    if (environment['numpy_file'] != environment['numpy_origin'] or
        environment['numpy_version'] != '2.5.2' or not environment['python_version']):
        raise ValueError('environment identity')


def check_identity_pair(before, after, code, production=False):
    for identity in (before, after): check_identity(identity, code, production)
    if (before['checkout'] != after['checkout'] or
        not exact(before['environment'], after['environment'])): raise ValueError('runtime changed')
    for name, row in before['modules'].items():
        if not exact(row, after['modules'].get(name)): raise ValueError('imported dependency changed')


def check_submission(ticket, commit, code, binding, job, run, started, allocation, terminal):
    """Independent launch receipt + raw scheduler association; no authenticity claim."""
    script = 'operations/x20_85889_chord_diagonal_resource.sbatch'
    root = ticket['workdir']; command = str(Path(root)/script)
    expected = dict(job_id=str(job), expected_commit=commit, run=run,
        sbatch_file=command, sbatch_fingerprint=code[script],
        code_content_sha256=document_sha(code), binding_content_sha256=document_sha(binding),
        digest_encoding='json-ascii-compact-insertion-order-v1')
    for key, value in expected.items():
        if not exact(ticket[key], value): raise ValueError('external submission binding: '+key)
    if not Path(root).is_absolute() or not Path(run).is_relative_to(Path(root)/'outputs/hpc'):
        raise ValueError('submission workdir/run')
    if (type(ticket['argv']) is not list or ticket['argv'] != ['sbatch', '--parsable', command] or
        ticket['stdout'].strip().split(';')[0] != str(job) or type(ticket['returncode']) is not int or
        ticket['returncode'] != 0): raise ValueError('submission command/return')
    exports = ticket['exports']
    for key, value in dict(CHORD_EXPECTED_COMMIT=commit, CHORD_RUN=run).items():
        if exports[key] != value: raise ValueError('submission environment')
    for key in ('CHORD_INVENTORY','CHORD_SOURCE_REVIEW','CHORD_HISTORY','CHORD_CODE_FREEZE'):
        if not Path(exports[key]).is_absolute(): raise ValueError('submission parameter path')
    expected_arguments = {key:exports['CHORD_'+key.upper()] for key in ('expected_commit','run','inventory','source_review','history','code_freeze')}
    if not exact(started['arguments'], expected_arguments): raise ValueError('executed arguments differ from submission')
    a, b = ticket['request_unix'], ticket['returned_unix']
    if (type(a) not in (int,float) or type(b) not in (int,float) or not math.isfinite(a) or
        not math.isfinite(b) or not 0 <= a <= b <= terminal['observed_unix'] or
        a > started['started_unix']): raise ValueError('submission times')
    for receipt in (allocation, terminal):
        tokens = scheduler_tokens(receipt['scontrol'])
        if any(tokens.get(k) != v for k,v in dict(JobId=str(job),Command=command,WorkDir=root).items()):
            raise ValueError('scheduler submission association')
        if 'SubmitTime' in tokens and tokens['SubmitTime'] != ticket['submit_time']:
            raise ValueError('scheduler submit time')
    if started['execution'] != dict(job_id=str(job),workdir=root,run=run,driver=str(Path(root)/'operations/x20_85889_chord_diagonal_resource.py')):
        raise ValueError('started submission association')


def reviewer_origins(repo, code):
    """CLI审阅进程自身的项目导入来源；仅标准库，不导入数值核。"""
    import sys
    repo = Path(repo).resolve(); result = {}
    stems = {Path(p).stem for p in code}
    for name, module in sorted(list(sys.modules.items())):
        file = getattr(module, '__file__', None)
        if not file: continue
        path = Path(file).absolute(); resolved = path.resolve()
        local = resolved.is_relative_to(repo) and not any(x.startswith('.venv') for x in resolved.relative_to(repo).parts)
        expected = name.split('.')[0] in ('operations','handoff','hpc','scripts','eccentric_tde_observer') or name in stems
        if not local and not expected: continue
        if path != resolved or not resolved.is_relative_to(repo): raise ValueError('foreign reviewer import')
        relative = str(resolved.relative_to(repo)); origin = getattr(getattr(module,'__spec__',None),'origin',None) or file
        if Path(origin).absolute() != resolved or relative not in code: raise ValueError('reviewer origin')
        raw = bounded_bytes(resolved,32*1024**2)
        fingerprint = dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if not exact(fingerprint,code[relative]): raise ValueError('reviewer code SHA')
        result[name] = dict(relative_path=relative,file=str(resolved),origin=str(resolved),fingerprint=fingerprint)
    required = ['handoff/audit_tools/review_x20_85889_chord_diagonal_resource.py',
        'operations/x20_85889_chord_diagonal_contract.py','handoff/audit_tools/review_x20_85889_chord_scan.py']
    if any(p not in [row['relative_path'] for row in result.values()] for p in required):
        raise ValueError('reviewer dependency missing')
    return result
