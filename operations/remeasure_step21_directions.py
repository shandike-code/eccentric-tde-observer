"""Matched-age finite material responses after the audited radiation control.

The two directions and acceptance denominator remain the original r20.  Fresh
control subtraction diagnoses response and drift; it never rebases acceptance.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import os
import resource
import shutil
import signal
import sys
import time
import numpy as np
from operations import confirm_step21_stationarity as station
from operations import common_step21_directions as directions
from operations.common_confirmation_batch import cross_comparisons, all_pair_gates

pipeline, ROOT, fixed, fresh, reused = station.pipeline, station.ROOT, station.fixed, station.fresh, station.reused
SOURCE = 'outputs/hpc/step21-stationarity-confirmation-20260927'
NAMES = ('control', 'thermal', 'population')
CADENCE = (8, 16)
LIMITS = {name: 16 for name in NAMES}
NORMS = ('l2', 'mass_weighted', 'maximum_cell')
SIGNAL_TOLERANCE = .1


def source_seed(summary, audit, state, retained):
    if (summary['status'] != 'persistent_control_stationarity_requires_review'
            or summary['maps'] != 16 or summary['accepted_outer_steps'] != 20
            or summary['new_material_steps'] != 0 or summary['baseline_replaced']
            or summary['strict_error_bound']):
        raise RuntimeError('source is not the completed stationarity witness')
    if (audit['job_id'] != 78594 or not audit['final_summary_present']
            or audit['feedback_rounds'] != [8, 16] or len(audit['maps']) != 16
            or audit['accepted_outer_steps'] != 20 or audit['new_material_steps'] != 0
            or audit['baseline_replaced'] or audit['strict_error_bound']):
        raise RuntimeError('independent stationarity audit missing')
    for n in ('8', '16'):
        actual, checked = summary['windows'][n], audit['windows'][n]
        if (not actual['confirmation_pass'] or not checked['confirmation_pass']
                or not actual['zero_control_stable']
                or set(actual['original_gates']) != station.ZERO_GATES
                or not all(actual['original_gates'].values())
                or actual['original_gates'] != checked['gate_checks']):
            raise RuntimeError('source feedback gate changed')
        for a, b in (('window_comparison', 'window'), ('from_78548_comparison', 'from_78548')):
            if not station.validate_window(actual[a]) or not station.validate_window(checked[b]):
                raise RuntimeError('source drift no longer passes')
    rows = state['history']
    if (state['active_map'] is not None or len(rows) != 16
            or [r['iteration'] for r in rows] != list(range(1, 17))
            or retained['history_rows'] != rows[-2:]
            or any(a['output_sha256'] != b['input_sha256'] for a, b in zip(rows, rows[1:]))):
        raise RuntimeError('source map chain incomplete')
    for key, row in zip(('previous', 'final'), rows[-2:]):
        if retained['endpoints'][key]['sha256'] != row['input_sha256']:
            raise RuntimeError('source retained input changed')
    seed = retained['endpoints']['mapped_final']
    if seed['sha256'] != rows[-1]['output_sha256'] or seed['size_bytes'] != pipeline.STATE_BYTES:
        raise RuntimeError('seed is not the latest audited successor')
    return seed


def norm_vector(vector, mass):
    norms = asdict(fresh.bridge.encoded_residual_norms(vector, mass))
    values = np.array([norms[k] for k in NORMS])
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError('invalid norm')
    return values


def endpoint_vectors(vectors, mass):
    if set(vectors) != {'previous', 'final'}:
        raise ValueError('both endpoints required')
    for value in vectors.values():
        if np.asarray(value).shape != (4 * len(mass),) or not np.isfinite(value).all():
            raise ValueError('invalid full residual vector')


def response_measurement(candidate, control, mass, alpha, earlier=None):
    """Observed signal/spread in all components; not a rigorous error bound."""
    endpoint_vectors(candidate, mass); endpoint_vectors(control, mass)
    if alpha != 1 / 256:
        raise ValueError('undeclared finite amplitude')
    # 先对完整编码残差作向量差，再取范数；不能以范数相减替代方向响应。
    signals = {a + '_vs_' + b: x - y for a, x in candidate.items() for b, y in control.items()}
    minimum = np.min([norm_vector(s, mass) for s in signals.values()], axis=0)
    spread = norm_vector(candidate['final'] - candidate['previous'], mass) + norm_vector(control['final'] - control['previous'], mass)
    # 零信号表示尚不可分辨；用null保留该事实，不引入floor或无穷大占位。
    ratios = [float(a / b) if b > 0 else None for a, b in zip(spread, minimum)]
    result = dict(signal_norms={k:dict(zip(NORMS, norm_vector(v, mass).tolist())) for k, v in signals.items()},
        finite_response_norms={k:dict(zip(NORMS, norm_vector(v / alpha, mass).tolist())) for k, v in signals.items()},
        minimum_signal_norms=dict(zip(NORMS, minimum.tolist())),
        endpoint_spread_over_signal=dict(zip(NORMS, ratios)),
        endpoint_signal_resolved=all(v is not None and v < SIGNAL_TOLERANCE for v in ratios),
        signal_tolerance=SIGNAL_TOLERANCE, strict_error_bound=False, exact_jacobian=False,
        baseline_replaced=False, material_step_promoted=False)
    if earlier is not None:
        if set(earlier) != set(signals) or any(v.shape != next(iter(signals.values())).shape or not np.isfinite(v).all() for v in earlier.values()):
            raise ValueError('earlier signal inventory changed')
        drift = np.max([norm_vector(x - y, mass) for x in signals.values() for y in earlier.values()], axis=0)
        ratio = [float(a / b) if b > 0 else None for a, b in zip(drift, minimum)]
        result['eight_map_signal_drift_over_signal'] = dict(zip(NORMS, ratio))
        result['eight_map_signal_persistent'] = all(v is not None and v < SIGNAL_TOLERANCE for v in ratio)
    return result, signals


def sequence(evaluate):
    """Control first at each matched map age; at most 48 maps and six pairs."""
    for n in CADENCE:
        for name in NAMES:
            outcome = evaluate(name, n)
            if outcome == 'physical_domain_rejected':
                return 'stopped_at_' + name + '_physical_domain'
            if name == 'control' and outcome != 'control_stable':
                return 'stopped_at_control_map' + str(n)
    return 'refreshed_direction_measurement_requires_review'


def make_protocol(finite, zero, rd, ret, trial, retained, declaration, name):
    if name not in NAMES:
        raise ValueError('undeclared direction')
    if name == 'control':
        p = station.recovery.control_protocol(finite, zero, rd, ret['endpoints'], ret['history_rows'], trial, retained, declaration)
    else:
        p = fresh.new_protocol(finite, rd, ret['endpoints'], ret['history_rows'], 16)
        for key in ('positive_plane_validation', 'affine_validation'):
            p['sources'].pop(key, None)
        p['sources'].update(trial_material=trial, retained_manifest=retained)
        p['numerical_backtracking'] = dict(alpha=1/256, fixed_base_accepted_index=20,
            direction_family=name, diagnostic_only=True, physical_time_advanced=False)
        p['outer_iteration'].update(direction_is_latest_confirmed_response=False, diagnostic_only=True)
        fixed.set_authorization(p, name)
    p['sources']['refreshed_direction_declaration'] = declaration
    return p


def prepare(out):
    ev = ROOT / 'handoff/evidence'; root = ROOT / SOURCE
    ap = ev / '20260928-stationarity-complete-review.json'
    names = ['summary.json', 'declaration.json', 'control/state.json', 'control/config.json',
        'control/trial_material.npz', 'control/endpoints-map16/manifest.json', 'control/pair16/feedback_protocol.json',
        'control/pair16/previous_response.npz', 'control/pair16/final_response.npz']
    claims = station.v.audited_inputs(root, ap, ev / '20260928-stationarity-78594-terminal.json', 78594, names)
    state = pipeline.read(root / 'control/state.json'); ret = pipeline.read(root / 'control/endpoints-map16/manifest.json')
    seed = source_seed(pipeline.read(root / 'summary.json'), pipeline.read(ap), state, ret)
    zero = pipeline.read(root / 'control/pair16/feedback_protocol.json'); sources = zero['sources']
    base = fresh.load_arrays(ROOT / sources['outer_base_material']['path'])
    r = np.load(ROOT / sources['base_residual']['path'], allow_pickle=False)
    old = fresh.load_arrays(ROOT / sources['physical_old_time_level']['path'])
    fixed.exact_trial(fresh.load_arrays(root / 'control/trial_material.npz'), base, r, old, 'control')
    accepted = ROOT / fixed.BASE
    fixed.validate_base_against_accepted(base, fresh.load_arrays(accepted / 'trial_material.npz'))
    if not np.array_equal(r, fresh.load_arrays(accepted / 'common-feedback/final_response.npz')['residual']):
        raise RuntimeError('original r20 replaced')
    acceptance = ev / '20260924-accepted-step20.json'
    fixed.validate_acceptance(pipeline.read(acceptance), pipeline.read(ev / '20260924-confirmation20-76727-terminal.json'))
    claims += [pipeline.claim(acceptance)] + pipeline.read(acceptance)['claims']
    finite_root = ROOT / station.original.SOURCE
    claims += station.v.audited_inputs(finite_root, ev / '20260925-positive-validation-complete-review.json',
        ev / '20260925-positive-validation-77126-terminal.json', 77126, ['thermal/pair03/feedback_protocol.json'])
    finite = pipeline.read(finite_root / 'thermal/pair03/feedback_protocol.json')
    cfg = pipeline.read(root / 'control/config.json')
    if pipeline.sha256(root / 'control/config.json') != state['config_sha256']:
        raise RuntimeError('source config changed')
    inputs = out / 'inputs'; inputs.mkdir(); cases = {}
    for name in NAMES:
        folder = inputs / name; folder.mkdir()
        trial = directions.make_trial(base, r, old, name)
        np.savez(folder / 'trial_material.npz', **trial)
        fixed.exact_trial(fresh.load_arrays(folder / 'trial_material.npz'), base, r, old, name)
        config = deepcopy(cfg); config['candidate_relaxation'] = directions.ALPHAS[name]
        pipeline.write_json(folder / 'config.json', config)
        cases[name] = dict(trial=pipeline.claim(folder / 'trial_material.npz'), config=pipeline.claim(folder / 'config.json'))
        preview = make_protocol(finite, zero, out / name / 'pair08', ret, cases[name]['trial'],
            pipeline.claim(root / 'control/endpoints-map16/manifest.json'), pipeline.claim(root / 'declaration.json'), name)
        fixed.native_identity(preview)
        claims += list(cases[name].values())
    prior = pipeline.read(root / 'declaration.json')
    claims += prior['claims'] + prior['code'] + list(sources.values()) + [seed]
    code = fresh.code_claims() + [pipeline.claim(ROOT / p) for p in (
        'operations/remeasure_step21_directions.sbatch', 'tests/test_remeasure_step21_directions.py',
        'handoff/protocols/step21-refreshed-directions-v1.md')]
    claims = list({(c['path'], c['sha256']):c for c in claims}.values())
    reused.verify(claims + code)
    plan = dict(cases=cases, source=SOURCE, source_job=78594, seed=seed, claims=claims, code=code,
        limits=LIMITS, cadence=list(CADENCE), case_order=list(NAMES), maximum_maps=48, maximum_feedback_pairs=6,
        amplitudes=directions.ALPHAS, matched_initial_radiation=True, signal_tolerance=SIGNAL_TOLERANCE,
        control_window_tolerance=.001, accepted_outer_steps=20, automatic_promotion=False,
        baseline_replacement_authorized=False, physical_dt_changed=False, environment=pipeline.environment())
    reused.immutable(out / 'declaration.json', plan)
    origin = {e:fresh.load_arrays(root / f'control/pair16/{e}_response.npz')['residual'] for e in ('previous', 'final')}
    return plan, finite, zero, base, r, old, origin


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('hugepage control required')
    out.relative_to(ROOT / 'outputs/hpc'); out.mkdir(exist_ok=False)
    def mark(status, **kw):
        pipeline.write_json(out / 'status.json', dict(status=status, accepted_outer_steps=20,
            new_material_steps=0, updated_unix=time.time(), **kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free < 36 * pipeline.STATE_BYTES:
            raise RuntimeError('insufficient retained disk budget')
        plan, finite, zero, base, r, old, origin = prepare(out)
        reused.LIMITS = LIMITS.copy(); children = {}; reports = {k:{} for k in NAMES}
        controls = {}; signals = {}; previous_control = origin
        def evaluate(name, n):
            nonlocal previous_control
            reused.checkpoint()
            if name not in children:
                children[name] = reused.child(out, name, name, plan['seed'], plan)
            folder, cfg, state = children[name]
            fixed.same_trial(fresh.load_arrays(folder / 'trial_material.npz'), fresh.load_arrays(ROOT / plan['cases'][name]['trial']['path']))
            while len(state['history']) < n:
                mark('mapping', case=name, completed_maps=len(state['history']), target_maps=n)
                station.original.map_once(folder, cfg, state)
            if len(state['history']) != n:
                raise RuntimeError('map counter changed')
            if not pipeline.pair_ready(state['history'], 1e-4):
                report = dict(feedback_evaluated=False, inner_pair_ready=False, promoted=False)
                reports[name][str(n)] = report; reused.immutable(folder / f'inner-not-ready-map{n:02d}.json', report)
                reused.archive(out, name + f'-map{n:02d}-inner-not-ready')
                return 'inner_not_ready'
            fixed.retain_pair(folder, state)
            rp = folder / f'endpoints-map{n:02d}/manifest.json'; ret = pipeline.read(rp)
            rd = folder / f'pair{n:02d}'; rd.mkdir()
            p = make_protocol(finite, zero, rd, ret, pipeline.claim(folder / 'trial_material.npz'), pipeline.claim(rp), pipeline.claim(out / 'declaration.json'), name)
            fixed.exact_trial(fresh.load_arrays(folder / 'trial_material.npz'), base, r, old, name); fixed.native_identity(p)
            fresh.attach_code(p); p['common_code_claims'] += plan['code']
            pp = rd / 'feedback_protocol.json'; reused.immutable(pp, p)
            reused.verify(list(p['sources'].values()) + p['common_code_claims']); mark('feedback', case=name, after_maps=n)
            with reused.feedback_stop_guard():
                if name == 'control':
                    stable = fixed.zero_feedback(rd, p, pp, state['history'][-2:])
                    result = pipeline.read(rd / 'baseline_summary.json')
                else:
                    result = fresh.pair.run_pair(pp, pipeline.sha256(pp))
                    directions.verify_step21_pair(rd, p, result)
            failures = result.get('material_response_failures', {})
            report = dict(feedback_evaluated=True, original_gates=result['gate_checks'],
                physical_response_failures=failures, promoted=False, baseline_replaced=False)
            outcome = 'physical_domain_rejected' if failures else 'direction_measured'
            if not failures:
                vectors = {e:fresh.load_arrays(rd / f'{e}_response.npz')['residual'] for e in ('previous', 'final')}
                if name == 'control':
                    window = station.original.window_comparison(vectors, previous_control, r, old['cell_mass_g_cm2'])
                    cumulative = station.original.window_comparison(vectors, origin, r, old['cell_mass_g_cm2'])
                    valid = stable and station.validate_window(window) and station.validate_window(cumulative)
                    report.update(zero_control_stable=stable, window_comparison=window,
                        from_78594_comparison=cumulative, control_pass=bool(valid))
                    controls[n] = vectors; previous_control = vectors
                    outcome = 'control_stable' if valid else 'control_unstable'
                else:
                    measure, current = response_measurement(vectors, controls[n], old['cell_mass_g_cm2'], 1/256, signals.get(name))
                    signals[name] = current
                    np.savez(rd / 'direction_response_vectors.npz', **current)
                    report.update(response_measurement=measure, fresh_baseline_comparison=cross_comparisons(vectors, controls[n], old['cell_mass_g_cm2']),
                        all_16_pair_gates=all_pair_gates(result))
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
            if peak >= 6 * 1024**3:
                raise RuntimeError('parent memory guard')
            report['parent_peak_rss_bytes'] = peak
            reused.immutable(rd / 'decision.json', report); reports[name][str(n)] = report
            reused.verify(list(p['sources'].values()) + p['common_code_claims'])
            reused.archive(out, name + f'-map{n:02d}-feedback')
            return outcome
        with fixed.relay_dispatch():
            terminal = sequence(evaluate)
        reused.verify(plan['claims'] + plan['code'])
        reused.immutable(out / 'summary.json', dict(status=terminal, cases=reports,
            maps=sum(len(st['history']) for _, _, st in children.values()), accepted_outer_steps=20,
            new_material_steps=0, baseline_replaced=False, strict_error_bound=False))
        mark(terminal); reused.archive(out, 'complete')
    except reused.Stopped as exc:
        mark('interrupted', reason=str(exc)); reused.archive(out, 'interrupted')
    except Exception as exc:
        mark('failed', error=repr(exc)); reused.archive(out, 'failed'); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); a = p.parse_args()
    for sig in (signal.SIGUSR1, signal.SIGTERM):
        signal.signal(sig, reused.stop)
    execute(pipeline.safe_path(ROOT, a.run))
