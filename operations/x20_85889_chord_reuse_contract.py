"""Pure receipt contract. No numerical kernel imports or production pin overrides."""
import hashlib
import json
import math
import os
import stat
from pathlib import Path

STATUS = 'reuse_resource_complete_requires_review'
OLD_COMMIT = '82aea66f68dd9f1abc27a8268ffd5e1bfa34f418'
KERNEL = 'operations/x20_85889_chord_scan_reuse.py'
KERNEL_SHA = 'a4b6b5b07eaaa457b5b5aa2cd726597f2476c78c7d2b3937810b6551fe0594a6'
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
    if isinstance(a, dict): return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
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
        raise ValueError('external frozen code manifest / reuse kernel')
    required = ['operations/x20_85889_chord_reuse_resource.py',
        'operations/x20_85889_chord_reuse_contract.py', 'operations/x20_85889_chord_reuse_receipt.py',
        'operations/x20_85889_chord_reuse_resource.sbatch',
        'handoff/audit_tools/review_x20_85889_chord_reuse_resource.py',
        'operations/x20_85889_chord_scan.py', 'operations/x20_85889_chord_live.py',
        'operations/x20_85889_chord_binding.py']
    if any(k not in manifest for k in required): raise ValueError('missing executable dependency')
    if manifest['operations/x20_85889_chord_scan.py']['sha256'] != '9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643':
        raise ValueError('frozen original kernel SHA')
