"""Read-only affine radiation planes built from widely separated, verified map pairs."""
import argparse
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
import numpy as np
from operations import scan_step21_positive_plane as plane
from operations import validate_step21_positive_plane as validation

base = plane.base
ROOT, pipeline, fresh = plane.ROOT, plane.pipeline, plane.fresh
SOURCE = 'outputs/hpc/step21-control-windows-recovery-20260925'
COST_RATIO = .8  # 只决定是否值得昂贵真实映射；不改变任何科学验收门。


def paired_basis(state, retained):
    rows = state['history']
    if len(rows) != 16 or state['active_map'] is not None or [r['iteration'] for r in rows] != list(range(1, 17)):
        raise ValueError('require sixteen completed maps')
    if any(a['output_sha256'] != b['input_sha256'] for a, b in zip(rows, rows[1:])):
        raise ValueError('broken source map lineage')
    pairs = {}
    for n in (8, 16):
        ret = retained[n]
        if ret['history_rows'] != rows[n-2:n]:
            raise ValueError('retained rows differ')
        endpoints = ret['endpoints']
        expected = [rows[n-2]['input_sha256'], rows[n-1]['input_sha256'], rows[n-1]['output_sha256']]
        claims = [endpoints[k] for k in ('previous', 'final', 'mapped_final')]
        if [c['sha256'] for c in claims] != expected:
            raise ValueError('retained pair is not a verified T(x)')
        pairs[n-2] = (claims[0], claims[1])
        pairs[n-1] = (claims[1], claims[2])
    # (X0,X1,X2,Y0,Y1,Y2)中每个Yi确实是同一固定物质算子对Xi的已算输出。
    return {f'x{k}-x14-x15': {'input_indices': [k,14,15],
            'basis': [pairs[i][j] for j in (0,1) for i in (k,14,15)]}
            for k in (6,7)}


def affine_pair(a, uv):
    if len(a) != 6 or np.asarray(uv).shape != (2,):
        raise ValueError('six paired states and two coefficients required')
    u, v = uv
    q = a[2] + u*(a[1]-a[2]) + v*(a[0]-a[2])
    p = a[5] + u*(a[4]-a[5]) + v*(a[3]-a[5])
    if not np.isfinite(q).all() or not np.isfinite(p).all():
        raise ArithmeticError('nonfinite affine prediction')
    return q, p


def make_cut(values, label, index):
    a = np.asarray(values, float)
    if a.shape != (6,) or label not in ('q','p') or not np.isfinite(a).all() or np.any(a < 0):
        raise ValueError('invalid paired positivity witness')
    x = a[:3] if label == 'q' else a[3:]
    scale = float(x.max())
    if scale == 0:
        raise ValueError('zero basis cannot generate a negative combination')
    # 每个弱尾点独立正规化，原始六态以hex保留；不删点、不裁剪辐射强度。
    x = x/scale
    return {'label': label, 'index': list(map(int,index)), 'inputs_hex': [float(v).hex() for v in a],
            'row': [float(x[1]-x[2]),float(x[0]-x[2])], 'lower': -float(x[2])}


def paired_streams(paths, shape):
    if len(paths) != 6:
        raise ValueError('six paired paths required')
    unique = {str(p): base.StreamState(p, shape) for p in dict.fromkeys(paths)}
    return [unique[str(p)] for p in paths]


def read_slab(states, start, stop):
    unique = {id(s): s[start:stop] for s in dict.fromkeys(states)}
    return [unique[id(s)] for s in states]


def gram_terms(a):
    r0,r1,r2 = (a[i+3]-a[i] for i in range(3))
    d = (r1-r2,r0-r2)
    return (np.array([[np.sum(x*y) for y in d] for x in d]),
            np.array([np.sum(x*r2) for x in d]),float(np.sum(r2*r2)))


def gram_scan(paths, shape, latest, progress):
    states = paired_streams(paths, shape); rows = []
    for start in range(0, shape[0], 16):
        stop = min(start+16,shape[0]); a = read_slab(states,start,stop)
        g,b,r = gram_terms(a)
        rows.append(dict(start=start,stop=stop,gram=g.tolist(),rhs=b.tolist(),r2_squared=r,
                         change=float(np.max(abs(a[5]-a[2]))),scale=max(float(a[5].max()),float(a[2].max()))))
        if start % 128 == 0: progress(frequency=start)
    g = [[math.fsum(r['gram'][i][j] for r in rows) for j in range(2)] for i in range(2)]
    b = [math.fsum(r['rhs'][i] for r in rows) for i in range(2)]
    actual = base.safe_ratio(max(r['change'] for r in rows),max(r['scale'] for r in rows))
    if not math.isclose(actual,latest,rel_tol=1e-12,abs_tol=0):
        raise RuntimeError('latest map residual differs from retained state bytes')
    return dict(gram=g,rhs=b,r2_squared=math.fsum(r['r2_squared'] for r in rows),slabs=rows,
                latest_actual_residual=actual,solve=base.solve_coefficients(g,b))


def cost_eligible(result):
    return bool(result.get('feasible') and result['rounds'][-1]['result']['predicted_ratio'] < COST_RATIO)


def inspect_fields(paths, shape, uv, edges, latest, progress=lambda **kw: None):
    states = paired_streams(paths, shape)
    mu, weights = base.algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    widths = np.diff(edges); rows = []; cuts = []
    for start in range(0, shape[0], 16):
        stop = min(start+16, shape[0]); a = read_slab(states, start, stop)
        q, p = affine_pair(a, uv)
        for label, field in [('q', q), ('p', p)]:
            ids = np.flatnonzero(field < 0)
            if ids.size:
                original = np.stack([v.ravel()[ids] for v in a], axis=1)
                j = 2 if label == 'q' else 5
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


def prepare():
    ev = ROOT/'handoff/evidence'; source = ROOT/SOURCE
    ap = ev/'20260925-control-recovery-complete-review.json'
    tp = ev/'20260925-control-recovery-77299-terminal.json'
    audit = pipeline.read(ap)
    if audit['audited_windows'] != [8,16] or not audit['final_summary_present'] or audit['new_material_steps'] != 0 or audit['baseline_replaced']:
        raise RuntimeError('complete fixed-state window audit required')
    names = ['status.json','summary.json','declaration.json','control/state.json','control/config.json','control/trial_material.npz']
    names += [f'control/endpoints-map{n:02d}/manifest.json' for n in (8,16)]
    names += [f'control/pair{n:02d}/'+x for n in (8,16) for x in ('feedback_protocol.json','decision.json')]
    claims = validation.audited_inputs(source,ap,tp,77299,names)
    if pipeline.read(source/'status.json')['status'] != 'control_window_diagnostic_complete':
        raise RuntimeError('source is not complete')
    prior = pipeline.read(source/'declaration.json'); state = pipeline.read(source/'control/state.json')
    if pipeline.sha256(source/'control/config.json') != state['config_sha256']:
        raise RuntimeError('source configuration changed')
    retained = {n:pipeline.read(source/f'control/endpoints-map{n:02d}/manifest.json') for n in (8,16)}
    cases = paired_basis(state,retained)
    protocols = [pipeline.read(source/f'control/pair{n:02d}/feedback_protocol.json') for n in (8,16)]
    for p in protocols:
        validation.fixed.native_identity(p)
        if not p['numerical_backtracking']['diagnostic_only'] or p['numerical_backtracking']['physical_time_advanced']:
            raise RuntimeError('source is not fixed-state control')
        claims += list(p['sources'].values())
    for key in ('outer_base_material','base_residual','physical_old_time_level','trial_material'):
        if protocols[0]['sources'][key] != protocols[1]['sources'][key]:
            raise RuntimeError('fixed physical identity changed')
    s = protocols[0]['sources']
    x = validation.load_arrays(ROOT/s['outer_base_material']['path'])
    r = np.load(ROOT/s['base_residual']['path'],allow_pickle=False)
    old = validation.load_arrays(ROOT/s['physical_old_time_level']['path'])
    trial = validation.load_arrays(source/'control/trial_material.npz')
    validation.fixed.exact_trial(trial,x,r,old,'control'); validation.fixed.same_trial(trial,x)
    validation.fixed.validate_base_against_accepted(x,validation.load_arrays(ROOT/validation.fixed.BASE/'trial_material.npz'))
    if not np.array_equal(r,validation.load_arrays(ROOT/validation.fixed.BASE/'common-feedback/final_response.npz')['residual']):
        raise RuntimeError('r20 changed')
    claims += prior['claims']+prior['code']+[c for case in cases.values() for c in case['basis']]
    claims = list({(c['path'],c['sha256']):c for c in claims}.values())
    fresh.reused.verify(claims)
    return cases,claims,state['history'][-1]['residual']


def execute(out):
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0': raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc'); out.mkdir(exist_ok=False)
    def mark(status,**kw):
        pipeline.write_json(out/'status.json',dict(status=status,updated_unix=time.time(),accepted_outer_steps=20,
                            new_material_steps=0,new_maps=0,candidate_written=False,**kw))
    mark('preparing')
    try:
        cases,claims,latest = prepare()
        code = fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/scan_step21_wide_plane.sbatch',
               'tests/test_scan_step21_wide_plane.py','handoff/protocols/step21-wide-plane-v1.md')]
        fresh.reused.immutable(out/'declaration.json',dict(cases=cases,claims=claims,code=code,environment=pipeline.environment(),
            source=SOURCE,maximum_passes_per_case=plane.MAX_PASSES,maximum_cuts_per_case=plane.MAX_CUTS,
            coefficient_cap=plane.COEFFICIENT_CAP,retreat=plane.RETREAT,cost_ratio_strict_upper_bound=COST_RATIO,
            candidate_write_budget=0,map_budget=0,feedback_budget=0,accepted_outer_steps=20))
        with np.load(ROOT/pipeline.MASTER,allow_pickle=False) as z: edges=z['active_edge_hz'].copy()
        results = {}
        for name,case in cases.items():
            paths = [ROOT/c['path'] for c in case['basis']]
            with np.errstate(invalid='raise',divide='raise',over='raise'):
                gram = gram_scan(paths,pipeline.SHAPE,latest,lambda **kw:mark('gram',case=name,**kw))
                pipeline.write_json(out/(name+'-gram.json'),gram)
                if gram['solve']['resolved']:
                    result = plane.search(gram['gram'],gram['rhs'],[],
                        lambda uv,n:inspect_fields(paths,pipeline.SHAPE,uv,edges,latest,
                            lambda **kw:mark('scanning',case=name,iteration=n,**kw)),
                        lambda rounds,cuts:pipeline.write_json(out/(name+'-progress.json'),dict(rounds=rounds,cuts=cuts)))
                else: result = dict(feasible=False,rounds=[],reason=gram['solve']['reason'])
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak >= 6*1024**3: raise RuntimeError('memory guard')
            result.update(cost_eligible=cost_eligible(result),peak_rss_bytes=peak,actual_map_performed=False,
                          candidate_written=False,accepted_material_step=False,full_constrained_optimum_proven=False)
            results[name]=result; pipeline.write_json(out/'prediction.json',results)
        fresh.reused.verify(claims+code); mark('complete_requires_review'); fresh.reused.archive(out,'complete')
    except BaseException as exc:
        mark('failed',error=repr(exc)); fresh.reused.archive(out,'failed'); raise


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    def stop(*_): raise InterruptedError('bounded wide-plane scan stopped')
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,stop)
    execute(pipeline.safe_path(ROOT,args.run))
