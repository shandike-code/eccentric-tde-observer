"""Bounded read-only two-coefficient search with explicit positivity half-planes."""
import argparse
import itertools
import json
from pathlib import Path
import resource
import signal
import sys
import tarfile
import time
import numpy as np
from operations import scan_step21_anderson2 as base

ROOT, pipeline, fresh = base.ROOT, base.pipeline, base.fresh
SCAN = 'outputs/hpc/step21-anderson2-scan-20260925'
TAIL = 'outputs/hpc/step21-affine-tail-diagnostic-20260925'
MAX_PASSES, MAX_CUTS, COEFFICIENT_CAP, RETREAT = 6, 4096, 191., .99


def intersect(poly, row, lower):
    """Intersect a coefficient polygon with row @ (u,v) >= lower."""
    row = np.asarray(row, float); output = []
    if row.shape != (2,) or not np.isfinite(row).all() or not np.isfinite(lower) or lower > 0:
        raise ValueError('invalid positivity half-plane; origin must remain feasible')
    for a, b in zip(poly, np.roll(poly, -1, axis=0)):
        fa, fb = float(row@a-lower), float(row@b-lower)
        if fa >= 0:
            output.append(a)
        if (fa >= 0) != (fb >= 0):
            output.append(a+(fa/(fa-fb))*(b-a))
    if not output:
        raise ArithmeticError('empty polygon despite feasible zero coefficient')
    return np.array(output)


def solve_plane(gram, rhs, cuts):
    g, b = np.asarray(gram, float), np.asarray(rhs, float)
    if not base.solve_coefficients(g, b)['resolved']:
        raise ValueError('unresolved residual differences')
    scale = float(np.max(abs(g))); g = g/scale; b = b/scale
    poly = np.array([[-192., -192.], [192., -192.], [192., 192.], [-192., 192.]])
    # L1(v,u,1-u-v)<=191写成8个线性不等式，给原<192门留显式余量。
    all_cuts = []
    for s0, s1, s2 in itertools.product((-1., 1.), repeat=3):
        all_cuts.append((np.array([s2-s1, s2-s0]), s2-COEFFICIENT_CAP))
    all_cuts += [(np.array(c['row']), float(c['lower'])) for c in cuts]
    for row, lower in all_cuts:
        poly = intersect(poly, row, lower)
    # 严格凸二次目标在内部驻点或边界上取最小；逐边解析最小化，避免黑箱优化器忽略弱约束。
    candidates = [np.zeros(2)]
    unconstrained = np.linalg.solve(g, -b)
    if all(row@unconstrained >= lower for row, lower in all_cuts):
        candidates.append(unconstrained)
    for a, z in zip(poly, np.roll(poly, -1, axis=0)):
        d = z-a; denominator = float(d@g@d)
        if denominator > 0:
            t = min(1., max(0., -float(d@(g@a+b))/denominator))
            candidates.append(a+t*d)
        else:
            candidates.append(a)
    values = [float(x@g@x+2*b@x) for x in candidates]
    raw = candidates[int(np.argmin(values))]
    effective = RETREAT*raw
    if not np.isfinite(effective).all():
        raise ArithmeticError('nonfinite constrained coefficient')
    return {'raw_uv': raw.tolist(), 'effective_uv': effective.tolist(), 'polygon': poly.tolist(),
            'objective_without_constant_scaled': min(values), 'retreat': RETREAT}


def make_cut(values, label, index):
    x = np.asarray(values, float); j = 2 if label == 'q' else 3
    if label not in ('q', 'p') or x.shape != (4,) or not np.isfinite(x).all() or np.any(x < 0):
        raise ValueError('invalid positivity witness')
    scale = float(x[j-2:j+1].max())
    if scale == 0:
        raise ValueError('zero basis cannot generate a negative combination')
    # 用局部强度尺度正规化约束，防止1e-310量级被绝对求解容差当成零约束。
    v = x[j-2:j+1]/scale
    return {'label': label, 'index': list(map(int, index)), 'inputs_hex': [float(a).hex() for a in x],
            'row': [float(v[1]-v[2]), float(v[0]-v[2])], 'lower': -float(v[2])}


def key(c):
    return (c['label'], *c['index'])


def inspect_fields(paths, shape, uv, edges, latest, progress=lambda **kw: None):
    states = [base.StreamState(p, shape) for p in paths]
    mu, weights = base.algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    widths = np.diff(edges); rows = []; cuts = []
    for start in range(0, shape[0], 16):
        stop = min(start+16, shape[0]); a = [s[start:stop] for s in states]
        q, p = base.affine_pair(a, uv, 1.)
        for label, field in [('q', q), ('p', p)]:
            ids = np.flatnonzero(field < 0)
            if ids.size:
                original = np.stack([v.ravel()[ids] for v in a], axis=1)
                j = 2 if label == 'q' else 3
                scales = original[:,j-2:j+1].max(axis=1)
                if np.any(scales <= 0):
                    raise ArithmeticError('negative output from zero basis')
                scores = field.ravel()[ids]/scales
                n = min(2, len(ids)); picks = np.argpartition(scores, n-1)[:n]
                for k in picks:
                    ix = np.unravel_index(ids[k], field.shape)
                    cuts.append(make_cut(original[k], label, (start+ix[0], *ix[1:])))
        fq = base.algebra._block_flux(q, mu, weights, widths[start:stop]); fp = base.algebra._block_flux(p, mu, weights, widths[start:stop])
        change = float(np.max(abs(p-q))); scale = max(float(np.max(abs(q))), float(np.max(abs(p))))
        rows.append(dict(start=start, stop=stop, change=change, scale=scale, local_relative=base.safe_ratio(change, scale),
            negative_q=int(np.count_nonzero(q < 0)), negative_p=int(np.count_nonzero(p < 0)), minimum_q=float(q.min()), minimum_p=float(p.min()),
            boundary_num=float(np.sum(abs(fp-fq))), q_abs_flux=float(np.sum(abs(fq))), p_abs_flux=float(np.sum(abs(fp))),
            q_bol=float(np.sum(fq)), p_bol=float(np.sum(fp))))
        if start % 128 == 0:
            progress(frequency=start)
    total = lambda k: sum(r[k] for r in rows)
    residual = base.safe_ratio(max(r['change'] for r in rows), max(r['scale'] for r in rows))
    l1 = base.safe_ratio(total('boundary_num'), max(total('q_abs_flux'), total('p_abs_flux')))
    bol = base.safe_ratio(abs(total('p_bol')-total('q_bol')), max(abs(total('q_bol')), abs(total('p_bol'))))
    u, v = uv; coeff = [v, u, 1-u-v]
    if not np.isfinite([residual, l1, bol, *coeff]).all():
        raise ArithmeticError('nonfinite aggregated prediction')
    gates = dict(positive=total('negative_q') == total('negative_p') == 0, coefficient_l1=sum(abs(x) for x in coeff) < 192,
                 coefficient_sum=abs(sum(coeff)-1.) < 1e-12,
                 strict_inner=residual < 1e-4, maximum_improves=residual/latest < .99, boundary_l1=l1 < 1e-3, boundary_bolometric=bol < 1e-3)
    return {'uv': list(map(float, uv)), 'coefficients': list(map(float, coeff)), 'slabs': rows, 'gates': gates,
            'predicted_global_residual': residual, 'predicted_ratio': residual/latest, 'predicted_boundary_l1': l1,
            'predicted_boundary_bolometric': bol, 'cuts': cuts}


def search(gram, rhs, initial_cuts, evaluate, save_round=lambda rounds, cuts: None):
    cuts = {key(c): c for c in initial_cuts}; rounds = []
    for n in range(MAX_PASSES):
        if len(cuts) > MAX_CUTS:
            return {'rounds': rounds, 'feasible': False, 'reason': 'cut_budget', 'cuts': list(cuts.values())}
        active = list(cuts.values()); solution = solve_plane(gram, rhs, active)
        result = evaluate(solution['effective_uv'], n)
        rounds.append({'solve': solution, 'input_cut_count': len(active), 'result': result})
        for c in result['cuts']:
            if key(c) in cuts and cuts[key(c)] != c:
                raise RuntimeError('same witness bytes changed')
            cuts[key(c)] = c
        save_round(rounds, list(cuts.values()))
        if len(cuts) > MAX_CUTS:
            return {'rounds': rounds, 'feasible': False, 'reason': 'cut_budget', 'cuts': list(cuts.values())}
        if result['gates']['positive']:
            return {'rounds': rounds, 'cuts': list(cuts.values()), 'feasible': all(result['gates'].values()),
                    'reason': 'positive_candidate_review_required'}
    return {'rounds': rounds, 'cuts': list(cuts.values()), 'feasible': False, 'reason': 'pass_budget'}


def execute(out):
    pipeline.require_allocation(1); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(exist_ok=False)
    def mark(status, **kw):
        pipeline.write_json(out/'status.json', dict(status=status, updated_unix=time.time(), new_maps=0,
                           accepted_outer_steps=20, new_material_steps=0, candidate_written=False, **kw))
    mark('preparing')
    try:
        claims = []; inputs = {}
        for name, source, audit_name, terminal_name, job in [
            ('scan', SCAN, '20260925-step21-anderson2-review.json', '20260925-step21-anderson2-77066-terminal.json', 77066),
            ('tail', TAIL, '20260925-step21-tail-review.json', '20260925-step21-tail-77094-terminal.json', 77094)]:
            ap = ROOT/'handoff/evidence'/audit_name; tp = ROOT/'handoff/evidence'/terminal_name
            audit = pipeline.read(ap); terminal = pipeline.read(tp)
            if terminal['job_id'] != job or terminal['state'] != 'COMPLETED' or audit['accepted_outer_steps'] != 20:
                raise RuntimeError('missing completed independent audit')
            fresh.reused.verify([audit['archive']]); claims += [pipeline.claim(ap), pipeline.claim(tp)]
            with tarfile.open(ROOT/audit['archive']['path']) as t:
                inv = {c['path']: c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
            current = {}
            for filename, expected in inv.items():
                c = pipeline.claim(ROOT/source/filename)
                if any(c[k] != expected[k] for k in ('size_bytes', 'sha256')):
                    raise RuntimeError('source changed: '+filename)
                claims.append(c); current[filename] = pipeline.read(ROOT/source/filename)
            inputs[name] = current
        declaration = inputs['scan']['declaration.json']; prediction = inputs['scan']['prediction.json']; tail = inputs['tail']['diagnosis.json']
        claims += declaration['claims']+declaration['code']+inputs['tail']['declaration.json']['claims']+inputs['tail']['declaration.json']['code']
        claims = list({(c['path'], c['sha256']): c for c in claims}.values()); fresh.reused.verify(claims)
        code = fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/scan_step21_positive_plane.sbatch', 'tests/test_scan_step21_positive_plane.py', 'handoff/protocols/step21-positive-plane-v1.md')]
        plan = dict(claims=claims, code=code, cases=declaration['cases'], environment=pipeline.environment(),
                    maximum_passes=MAX_PASSES, maximum_cuts=MAX_CUTS, coefficient_cap=COEFFICIENT_CAP,
                    common_retreat=RETREAT, source_scan=SCAN, source_tail=TAIL, candidate_write_budget=0)
        fresh.reused.immutable(out/'declaration.json', plan)
        with np.load(ROOT/pipeline.MASTER, allow_pickle=False) as z:
            edges = z['active_edge_hz'].copy()
        results = {}
        for case, old in prediction.items():
            if old['selected'] is not None:
                raise RuntimeError('expected failed unconstrained scan')
            initial = {}
            for candidate in tail[case]['candidates']:
                for slab in candidate['slabs']:
                    for field in slab['fields'].values():
                        for w in field['exact_witnesses']:
                            c = make_cut([float.fromhex(x) for x in w['inputs_hex']], w['label'], w['index']); initial[key(c)] = c
            paths = [ROOT/c['path'] for c in declaration['cases'][case]['basis']]
            def evaluate(uv, iteration):
                return inspect_fields(paths, pipeline.SHAPE, uv, edges, old['latest_actual_residual'],
                    progress=lambda **kw: mark('scanning', case=case, iteration=iteration, **kw))
            with np.errstate(invalid='raise', divide='raise', over='raise'):
                result = search(old['gram'], old['rhs'], list(initial.values()), evaluate,
                    save_round=lambda rounds, cuts: pipeline.write_json(out/(case+'-progress.json'), {'rounds': rounds, 'cuts': cuts}))
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)
            if peak >= 6*1024**3:
                raise RuntimeError('memory guard')
            result.update(peak_rss_bytes=peak, initial_cuts=list(initial.values()), actual_map_performed=False,
                          candidate_written=False, accepted_material_step=False, full_constrained_optimum_proven=False)
            results[case] = result; pipeline.write_json(out/'prediction.json', results)
        fresh.reused.verify(claims+code); mark('complete_requires_review'); fresh.reused.archive(out, 'complete')
    except BaseException as exc:
        mark('failed', error=repr(exc)); fresh.reused.archive(out, 'failed'); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); args = p.parse_args()
    def stop(*_):
        raise InterruptedError('bounded positive-plane scan stopped')
    for sig in (signal.SIGUSR1, signal.SIGTERM):
        signal.signal(sig, stop)
    execute(pipeline.safe_path(ROOT, args.run))
