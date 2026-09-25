"""Read-only precision and exact-sign witnesses for rejected Anderson tails."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import resource
import signal
import sys
import tarfile
import time
import numpy as np
from operations import scan_step21_anderson2 as scan

ROOT = scan.ROOT
pipeline = scan.pipeline
fresh = scan.fresh
SOURCE = 'outputs/hpc/step21-anderson2-scan-20260925'


def fraction_record(x):
    return {'numerator': str(x.numerator), 'denominator': str(x.denominator), 'sign': (x > 0)-(x < 0)}


def exact_cell(values, uv, eta, label):
    if label not in ('q', 'p') or len(values) != 4:
        raise ValueError('invalid witness')
    raw = list(map(float, values)); weights = list(map(float, uv)); eta = float(eta)
    if not np.isfinite(raw+weights+[eta]).all() or min(raw) < 0 or eta <= 0:
        raise ValueError('invalid witness data')
    a = list(map(Fraction.from_float, raw)); u, v = map(Fraction.from_float, weights)
    j = 2 if label == 'q' else 3
    # float64输入和已冻结系数都是有限二进制有理数；逐项精确计算，不靠更宽浮点猜符号。
    base = a[j]; slope = u*(a[j-1]-base)+v*(a[j-2]-base)
    value = base+Fraction.from_float(eta)*slope
    bound = base/(-slope) if slope < 0 else None
    return {'label': label, 'inputs_hex': [x.hex() for x in raw], 'uv_hex': [x.hex() for x in weights],
            'eta_hex': eta.hex(), 'base': fraction_record(base), 'slope': fraction_record(slope),
            'value': fraction_record(value), 'positive_eta_upper_bound': fraction_record(bound) if bound is not None else None,
            'no_positive_eta_on_this_ray': base == 0 and slope < 0}


def inspect_slab(values, uv, eta, start):
    values = [np.asarray(x, dtype=np.float64) for x in values]
    if len(values) != 4 or any(x.shape != values[0].shape for x in values):
        raise ValueError('incompatible basis')
    if any(not np.isfinite(x).all() or np.any(x < 0) for x in values):
        raise ValueError('invalid basis')
    q64, p64 = scan.affine_pair(values, uv, eta)
    rows = {}; wide = [x.astype(np.longdouble) for x in values]
    u, v = np.array(uv, dtype=np.longdouble)
    for label, j, native in [('q', 2, q64), ('p', 3, p64)]:
        base = wide[j]; slope = u*(wide[j-1]-base)+v*(wide[j-2]-base)
        value = base+np.longdouble(eta)*slope
        if not np.isfinite(value).all():
            raise ArithmeticError('nonfinite extended prediction')
        negative_slope = slope < 0
        bound = np.min(base[negative_slope]/(-slope[negative_slope])) if np.any(negative_slope) else None
        zero_obstructs = (base == 0) & negative_slope
        locations = {int(np.argmin(value)), int(np.argmin(native))}
        if np.any(zero_obstructs):
            locations.add(int(np.flatnonzero(zero_obstructs)[0]))
        witnesses = []
        for flat in sorted(locations):
            index = np.unravel_index(flat, value.shape)
            w = exact_cell([x[index] for x in values], uv, eta, label)
            w.update(index=[int(index[0])+start, *map(int, index[1:])], native_value_hex=float(native[index]).hex(),
                     extended_value=str(value[index]))
            witnesses.append(w)
        rows[label] = {'native_negative_count': int(np.count_nonzero(native < 0)),
            'extended_negative_count': int(np.count_nonzero(value < 0)),
            'native_minimum': float(native.min()), 'extended_minimum': str(value.min()),
            'native_negative_but_extended_nonnegative': int(np.count_nonzero((native < 0) & (value >= 0))),
            'extended_negative_but_native_nonnegative': int(np.count_nonzero((value < 0) & (native >= 0))),
            'zero_base_negative_slope_count': int(np.count_nonzero(zero_obstructs)),
            'tail_eta_upper_bound_extended': str(bound) if bound is not None else None,
            'exact_witnesses': witnesses}
    return {'start': start, 'stop': start+values[0].shape[0], 'eta': eta, 'fields': rows}


def execute(out):
    pipeline.require_allocation(1); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(exist_ok=False)
    def mark(status, **kw):
        pipeline.write_json(out/'status.json', dict(status=status, updated_unix=time.time(), new_maps=0,
                           new_material_steps=0, accepted_outer_steps=20, candidate_written=False, **kw))
    mark('preparing')
    try:
        if np.finfo(np.longdouble).eps >= np.finfo(float).eps:
            raise RuntimeError('extended precision is not wider than float64 on this platform')
        audit_path = ROOT/'handoff/evidence/20260925-step21-anderson2-review.json'
        terminal_path = ROOT/'handoff/evidence/20260925-step21-anderson2-77066-terminal.json'
        audit = pipeline.read(audit_path); terminal = pipeline.read(terminal_path)
        if terminal['job_id'] != 77066 or terminal['state'] != 'COMPLETED' or any(r['selected'] is not None for r in audit['cases'].values()):
            raise RuntimeError('require completed rejected three-case scan audit')
        fresh.reused.verify([audit['archive']])
        with tarfile.open(ROOT/audit['archive']['path']) as t:
            inventory = {c['path']: c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
        claims = [pipeline.claim(audit_path), pipeline.claim(terminal_path)]
        for name in ('declaration.json', 'prediction.json', 'status.json'):
            c = pipeline.claim(ROOT/SOURCE/name)
            if any(c[k] != inventory[name][k] for k in ('size_bytes', 'sha256')):
                raise RuntimeError('source archive mismatch: '+name)
            claims.append(c)
        declaration = pipeline.read(ROOT/SOURCE/'declaration.json'); prediction = pipeline.read(ROOT/SOURCE/'prediction.json')
        fresh.reused.verify(declaration['claims']+declaration['code']); claims += declaration['claims']+declaration['code']
        code = fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/diagnose_step21_affine_tail.sbatch', 'tests/test_diagnose_step21_affine_tail.py', 'handoff/protocols/step21-affine-tail-diagnostic-v1.md')]
        plan = {'claims': claims, 'code': code, 'environment': pipeline.environment(), 'source': SOURCE,
                'longdouble_mantissa_bits': int(np.finfo(np.longdouble).nmant), 'scope': 'read-only exact witnesses; no altered candidate',
                'frequency_range': [9424, 9504], 'etas_unchanged': list(scan.ETAS)}
        fresh.reused.immutable(out/'declaration.json', plan); results = {}
        for case, original in prediction.items():
            basis = declaration['cases'][case]['basis']; states = [scan.StreamState(ROOT/c['path'], pipeline.SHAPE) for c in basis]
            results[case] = {'uv': original['solve']['uv'], 'candidates': []}
            for candidate in original['candidates']:
                if not candidate['slabs']:
                    continue
                if candidate['gates']['positive']:
                    raise RuntimeError('unexpected positive candidate')
                bad = [s for s in candidate['slabs'] if s['negative_q'] or s['negative_p']]
                if [(s['start'], s['stop']) for s in bad] != [(i, i+16) for i in range(9424, 9504, 16)]:
                    raise RuntimeError('negative support differs from the registered tail')
                rows = []
                for s in bad:
                    mark('examining', case=case, eta=candidate['eta'], frequency=s['start'])
                    arrays = [state[s['start']:s['stop']] for state in states]
                    with np.errstate(invalid='raise', over='raise', divide='raise'):
                        row = inspect_slab(arrays, original['solve']['uv'], candidate['eta'], s['start'])
                    for label in ('q', 'p'):
                        if row['fields'][label]['native_negative_count'] != s['negative_'+label] or row['fields'][label]['native_minimum'] != s['minimum_'+label]:
                            raise RuntimeError('native tail does not reproduce frozen scan')
                    rows.append(row)
                results[case]['candidates'].append({'eta': candidate['eta'], 'slabs': rows})
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)
            if peak >= 6*1024**3:
                raise RuntimeError('memory guard')
            results[case]['peak_rss_bytes'] = peak
            pipeline.write_json(out/'diagnosis.json', results)
        fresh.reused.verify(claims+code); mark('complete_requires_review'); fresh.reused.archive(out, 'complete')
    except BaseException as exc:
        mark('failed', error=repr(exc)); fresh.reused.archive(out, 'failed'); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', required=True); args = parser.parse_args()
    def stop(*_):
        raise InterruptedError('read-only tail diagnosis stopped')
    for sig in (signal.SIGUSR1, signal.SIGTERM):
        signal.signal(sig, stop)
    execute(pipeline.safe_path(ROOT, args.run))
