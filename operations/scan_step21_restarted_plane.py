"""Bounded read-only restart-plane scan using the audited 77371 endpoints."""
import argparse
import os
from pathlib import Path
import resource
import signal
import sys
import time
import numpy as np
from operations import scan_step21_wide_plane as wide
plane, base, validation = wide.plane, wide.base, wide.validation
ROOT, pipeline, fresh = wide.ROOT, wide.pipeline, wide.fresh
SOURCE = 'outputs/hpc/step21-wide-plane-validation-20260925'
COST_RATIO = wide.COST_RATIO
# Reuse the already validated six-state stream algebra without modifying old code.
gram_scan, inspect_fields, cost_eligible = wide.gram_scan, wide.inspect_fields, wide.cost_eligible

def paired_basis(state, retained):
    rows = state['history']
    if len(rows) != 11 or state['active_map'] is not None or [r['iteration'] for r in rows] != list(range(1, 12)):
        raise ValueError('require eleven completed maps')
    if any(a['output_sha256'] != b['input_sha256'] for a, b in zip(rows, rows[1:])):
        raise ValueError('broken source map lineage')
    pairs = {}
    for n in (3, 11):
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
    return {f'x{k}-x9-x10': {'input_indices': [k,9,10],
            'basis': [pairs[i][j] for j in (0,1) for i in (k,9,10)]}
            for k in (1,2)}


def validate_audit(audit):
    if audit['feedback_rounds'] != [3,11] or not audit['final_summary_present']:
        raise ValueError('complete 77371 audit required')
    if audit['new_material_steps'] != 0 or audit['accepted_outer_steps'] != 20 or audit['baseline_replaced']:
        raise ValueError('fixed matter identity required')
    for n in ('3','11'):
        gates=audit['windows'][n]['gate_checks']
        expected={'last_two_photoionization_pass','last_two_total_recombination_pass',
            'last_two_atomic_heating_pass','last_two_direct_heating_pass',
            'last_two_formal_heating_pass','inner_pair_ready','physical_response_pass'}
        if set(gates) != expected or not all(gates.values()):
            raise ValueError('original feedback gates must pass')
    if audit['windows']['11']['comparison_kind'] != 'eight_map_drift' or audit['windows']['11']['window']['passed']:
        raise ValueError('this scan is only authorized for the unresolved eight-map drift')


def prepare():
    ev = ROOT/'handoff/evidence'; source = ROOT/SOURCE
    ap = ev/'20260925-wide-validation-complete-review.json'
    tp = ev/'20260925-wide-validation-77371-terminal.json'
    audit = pipeline.read(ap)
    if audit['feedback_rounds'] != [3,11] or not audit['final_summary_present'] or audit['new_material_steps'] != 0 or audit['baseline_replaced']:
        raise RuntimeError('complete fixed-state window audit required')
    validate_audit(audit)
    names = ['status.json','summary.json','declaration.json','control/state.json','control/config.json','control/trial_material.npz']
    names += [f'control/endpoints-map{n:02d}/manifest.json' for n in (3,11)]
    names += [f'control/pair{n:02d}/'+x for n in (3,11) for x in ('feedback_protocol.json','decision.json')]
    claims = validation.audited_inputs(source,ap,tp,77371,names)
    if pipeline.read(source/'status.json')['status'] != 'wide_plane_validation_complete_requires_review':
        raise RuntimeError('source is not complete')
    prior = pipeline.read(source/'declaration.json'); state = pipeline.read(source/'control/state.json')
    if pipeline.sha256(source/'control/config.json') != state['config_sha256']:
        raise RuntimeError('source configuration changed')
    retained = {n:pipeline.read(source/f'control/endpoints-map{n:02d}/manifest.json') for n in (3,11)}
    cases = paired_basis(state,retained)
    protocols = [pipeline.read(source/f'control/pair{n:02d}/feedback_protocol.json') for n in (3,11)]
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
        code = fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/scan_step21_restarted_plane.sbatch',
               'tests/test_scan_step21_restarted_plane.py','handoff/protocols/step21-restarted-plane-v1.md')]
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
    def stop(*_): raise InterruptedError('bounded restarted-plane scan stopped')
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,stop)
    execute(pipeline.safe_path(ROOT,args.run))
