"""Read-only depth-two radiation feasibility; no candidate or transfer solve."""
import argparse
import json
from pathlib import Path
import resource
import signal
import sys
import tarfile
import time
import numpy as np
from operations.scan_step21_radiation_history import StreamState, fresh, algebra

pipeline = fresh.pipeline
ROOT = fresh.ROOT
SOURCE = 'outputs/hpc/step21-radiation-affine-validation-20260925'
ETAS = (1., .5, .25, .125)


def four_basis(state, retained, validation):
    rows = state.get('history', [])
    if len(rows) != 3 or state.get('active_map') is not None:
        raise ValueError('require exactly three complete maps')
    if any(a['output_sha256'] != b['input_sha256'] for a, b in zip(rows, rows[1:])):
        raise ValueError('discontinuous history')
    if retained['history_rows'] != rows[-2:] or validation['actual_map'] != rows[0]:
        raise ValueError('retained history differs')
    basis = [validation['candidate']] + [retained['endpoints'][k] for k in ('previous', 'final', 'mapped_final')]
    expected = [rows[0]['input_sha256']] + [r['output_sha256'] for r in rows]
    if [b['sha256'] for b in basis] != expected:
        raise ValueError('four-state byte identity differs')
    return basis


def solve_coefficients(gram, rhs):
    """Solve the two independent residual differences, never a cancelled 3x3 Gram."""
    g, b = np.asarray(gram, float), np.asarray(rhs, float)
    if g.shape != (2, 2) or b.shape != (2,) or not np.isfinite(g).all() or not np.isfinite(b).all():
        raise ValueError('invalid normal equations')
    if not np.array_equal(g, g.T):
        raise ValueError('asymmetric Gram')
    scale = float(np.max(np.abs(g)))
    if scale <= 0:
        return {'resolved': False, 'reason': 'zero differences'}
    eigen = np.linalg.eigvalsh(g / scale)
    if eigen[0] <= 0 or eigen[-1] / eigen[0] >= 1e10:
        return {'resolved': False, 'reason': 'singular or ill-conditioned differences', 'scaled_eigenvalues': eigen.tolist()}
    uv = np.linalg.solve(g / scale, -b / scale)
    if not np.isfinite(uv).all():
        raise ArithmeticError('nonfinite coefficients')
    denominator = max(np.linalg.norm(b), np.linalg.norm(g) * np.linalg.norm(uv))
    residual = safe_ratio(np.linalg.norm(g @ uv + b), denominator)
    if not np.isfinite(residual) or residual >= 1e-10:
        raise ArithmeticError('normal equation verification failed')
    return {'resolved': True, 'uv': uv.tolist(), 'condition': float(eigen[-1] / eigen[0]), 'normal_equation_relative_residual': float(residual)}


def affine_pair(values, uv, eta):
    x0, x1, x2, x3 = values
    u, v = np.asarray(uv) * eta
    # 权重依次为(v,u,1-u-v)，和为1；用差分形式避免大背景的线性组合相消。
    q = x2 + u * (x1 - x2) + v * (x0 - x2)
    p = x3 + u * (x2 - x3) + v * (x1 - x3)
    if not np.isfinite(q).all() or not np.isfinite(p).all():
        raise ArithmeticError('nonfinite affine prediction')
    return q, p


def safe_ratio(a, b):
    if b == 0:
        if a == 0:
            return 0.
        raise ArithmeticError('nonzero numerator over zero scale')
    return float(a / b)


def scan(paths, shape, edges, latest, chunk=16, progress=lambda **kw: None):
    if not np.isfinite(latest) or latest <= 0 or chunk <= 0:
        raise ValueError('invalid reference residual/chunk')
    edges = np.asarray(edges)
    if edges.shape != (shape[0]+1,) or not np.isfinite(edges).all() or np.any(np.diff(edges) <= 0):
        raise ValueError('invalid frequency edges')
    states = [StreamState(p, shape) for p in paths]
    if len(states) != 4:
        raise ValueError('four states required')
    gram = np.zeros((2, 2)); rhs = np.zeros(2); norm2 = 0.; gram_slabs = []
    for start in range(0, shape[0], chunk):
        stop = min(start+chunk, shape[0]); x0, x1, x2, x3 = [s[start:stop] for s in states]
        r0, r1, r2 = x1-x0, x2-x1, x3-x2
        # 固定物质下 T 近似仿射；最小化 r2+u(r1-r2)+v(r0-r2) 的离散场L2。
        d = [r1-r2, r0-r2]
        g = np.array([[np.sum(a*b) for b in d] for a in d]); b = np.array([np.sum(a*r2) for a in d])
        r = float(np.sum(r2*r2)); gram += g; rhs += b; norm2 += r
        gram_slabs.append({'start': start, 'stop': stop, 'gram': g.tolist(), 'rhs': b.tolist(), 'r2_squared': r})
        if start % 128 == 0:
            progress(phase='gram', frequency=start)
    solved = solve_coefficients(gram, rhs)
    result = {'gram': gram.tolist(), 'rhs': rhs.tolist(), 'r2_squared': norm2, 'gram_slabs': gram_slabs,
              'solve': solved, 'latest_actual_residual': latest, 'candidates': [], 'selected': None,
              'candidate_written': False, 'new_maps': 0, 'fresh_map_required': True, 'strict_error_bound': False}
    if not solved['resolved']:
        return result
    for eta in ETAS:
        u, v = eta*np.array(solved['uv']); coefficients = [v, u, 1-u-v]
        result['candidates'].append({'eta': eta, 'coefficients': list(map(float, coefficients)),
            'coefficient_l1': float(np.sum(np.abs(coefficients))), 'slabs': []})
    mu, weight = algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    width = np.diff(edges)
    for start in range(0, shape[0], chunk):
        stop = min(start+chunk, shape[0]); values = [s[start:stop] for s in states]
        for row in result['candidates']:
            if row['coefficient_l1'] >= 192:
                continue
            q, p = affine_pair(values, solved['uv'], row['eta'])
            fq = algebra._block_flux(q, mu, weight, width[start:stop]); fp = algebra._block_flux(p, mu, weight, width[start:stop])
            change = float(np.max(np.abs(p-q))); scale = max(float(np.max(np.abs(q))), float(np.max(np.abs(p))))
            row['slabs'].append({'start': start, 'stop': stop, 'change': change, 'scale': scale,
                'local_relative': safe_ratio(change, scale), 'negative_q': int(np.count_nonzero(q < 0)),
                'negative_p': int(np.count_nonzero(p < 0)), 'minimum_q': float(q.min()), 'minimum_p': float(p.min()),
                'boundary_num': float(np.sum(np.abs(fp-fq))), 'q_abs_flux': float(np.sum(np.abs(fq))),
                'p_abs_flux': float(np.sum(np.abs(fp))), 'q_bol': float(np.sum(fq)), 'p_bol': float(np.sum(fp))})
        if start % 128 == 0:
            progress(phase='metrics', frequency=start)
    for row in result['candidates']:
        slabs = row['slabs']
        if not slabs:
            row.update(feasible=False, reason='coefficient l1 limit'); continue
        summed = lambda k: sum(s[k] for s in slabs)
        global_res = safe_ratio(max(s['change'] for s in slabs), max(s['scale'] for s in slabs))
        l1 = safe_ratio(summed('boundary_num'), max(summed('q_abs_flux'), summed('p_abs_flux')))
        bol = safe_ratio(abs(summed('p_bol')-summed('q_bol')), max(abs(summed('q_bol')), abs(summed('p_bol'))))
        gates = {'positive': summed('negative_q') == summed('negative_p') == 0,
                 'maximum_improves': global_res/latest < .99, 'strict_inner': global_res < 1e-4,
                 'boundary_l1': l1 < 1e-3, 'boundary_bolometric': bol < 1e-3}
        row.update(predicted_global_residual=global_res, predicted_ratio=global_res/latest,
                   predicted_boundary_l1=l1, predicted_boundary_bolometric=bol,
                   gates=gates, feasible=all(gates.values()))
    eligible = [r for r in result['candidates'] if r['feasible']]
    if eligible:
        winner = min(eligible, key=lambda r: r['predicted_global_residual'])
        result['selected'] = {k: winner[k] for k in ('eta', 'coefficients', 'predicted_ratio', 'predicted_global_residual')}
    return result


def execute(out):
    pipeline.require_allocation(1); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(exist_ok=False)
    def mark(status, **kw):
        pipeline.write_json(out/'status.json', dict(status=status, updated_unix=time.time(), accepted_outer_steps=20,
                           new_material_steps=0, new_maps=0, candidate_written=False, **kw))
    mark('preparing')
    try:
        audit_path = ROOT/'handoff/evidence/20260925-step21-affine-complete-review.json'
        terminal_path = ROOT/'handoff/evidence/20260925-step21-affine-76957-terminal.json'
        audit = pipeline.read(audit_path); terminal = pipeline.read(terminal_path)
        if not audit['final_summary_present'] or audit['audited_cases'] != ['control', 'thermal', 'population'] or terminal['job_id'] != 76957 or terminal['state'] != 'COMPLETED':
            raise RuntimeError('complete independent source audit required')
        fresh.reused.verify([audit['archive']])
        with tarfile.open(ROOT/audit['archive']['path']) as t:
            inventory = {c['path']: c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
        claims = [pipeline.claim(audit_path), pipeline.claim(terminal_path), pipeline.claim(ROOT/pipeline.MASTER)]
        def source_claim(name):
            c = pipeline.claim(ROOT/SOURCE/name)
            if any(c[k] != inventory[name][k] for k in ('size_bytes', 'sha256')):
                raise RuntimeError('source differs from independent audit: '+name)
            claims.append(c)
        cases = {}
        for case in ('control', 'thermal', 'population'):
            for name in ('state.json', 'config.json', 'trial_material.npz', 'validation.json', 'endpoints-map03/manifest.json'):
                source_claim(case+'/'+name)
            folder = ROOT/SOURCE/case; state = pipeline.read(folder/'state.json')
            if pipeline.sha256(folder/'config.json') != state['config_sha256']:
                raise RuntimeError('config changed')
            cfg = pipeline.read(folder/'config.json')
            if not any(c['sha256'] == claims[2]['sha256'] for c in cfg['sources']):
                raise RuntimeError('frequency master differs')
            basis = four_basis(state, pipeline.read(folder/'endpoints-map03/manifest.json'), pipeline.read(folder/'validation.json'))
            fresh.reused.verify(basis); claims += basis
            cases[case] = {'basis': basis, 'latest_actual_residual': state['history'][-1]['residual']}
        code = fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/scan_step21_anderson2.sbatch', 'tests/test_scan_step21_anderson2.py', 'handoff/protocols/step21-anderson2-scan-v1.md')]
        fresh.reused.immutable(out/'declaration.json', {'cases': cases, 'claims': claims, 'code': code,
            'etas': list(ETAS), 'chunk': 16, 'condition_limit': 1e10, 'coefficient_l1_limit': 192,
            'environment': pipeline.environment(), 'scope': 'read only; no candidate, map, feedback, or promotion'})
        with np.load(ROOT/pipeline.MASTER, allow_pickle=False) as z:
            edges = z['active_edge_hz'].copy()
        results = {}
        for case, info in cases.items():
            with np.errstate(invalid='raise', over='raise', divide='raise'):
                results[case] = scan([ROOT/c['path'] for c in info['basis']], pipeline.SHAPE, edges, info['latest_actual_residual'],
                                    progress=lambda **kw: mark('scanning', case=case, **kw))
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)
            if peak >= 6*1024**3:
                raise RuntimeError('scan exceeded memory guard')
            results[case]['peak_rss_bytes'] = peak
            pipeline.write_json(out/'prediction.json', results)
        fresh.reused.verify(claims+code); mark('complete_requires_review'); fresh.reused.archive(out, 'complete')
    except BaseException as exc:
        mark('failed', error=repr(exc)); fresh.reused.archive(out, 'failed'); raise


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); args = p.parse_args()
    def stop(*_):
        raise InterruptedError('bounded read-only scan interrupted')
    for sig in (signal.SIGUSR1, signal.SIGTERM):
        signal.signal(sig, stop)
    execute(pipeline.safe_path(ROOT, args.run))


if __name__ == '__main__':
    main()
