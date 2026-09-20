"""One bounded inner-precision follow-up of the unchanged half-step material."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_common_seed_precision import latest_seed
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_extension_run import carry_trial
from operations.prepare_half_step_after_audit import ALPHA, REQUIRED_GATES, assert_written_trial

SOURCE = 'outputs/hpc/half-step-a001953125-20260920'


def eligible_source(state, summary, trial):
    """Require the declared four-map experiment and its actual last feedback pair."""
    seed = latest_seed(state)
    history = state['history']; rounds = state.get('diagnostic', {}).get('rounds', [])
    if len(history) != 4 or len(rounds) != 2 or rounds[-1]['endpoints'] != [3, 4]:
        raise ValueError('source is not the completed four-map half-step experiment')
    pair = rounds[-1]
    if pair['protocol_sha256'] != summary['protocol_sha256']:
        raise ValueError('source summary differs from the completed pair')
    for row, label in zip(history[-2:], ('previous', 'final')):
        claim = pair['endpoints_claim'][label]
        if (claim['path'], claim['sha256']) != (row['input_path'], row['input_sha256']):
            raise ValueError('source feedback endpoints differ from map inputs')
    failures = {'candidate_l2_contraction_pass', 'candidate_mass_weighted_contraction_pass',
                'last_two_atomic_heating_pass', 'last_two_direct_heating_pass',
                'last_two_formal_heating_pass', 'two_inner_radiation_residuals_pass'}
    gates = summary['gate_checks']
    if (set(gates) != REQUIRED_GATES or {k for k, v in gates.items() if v is not True} != failures
            or summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] is not False):
        raise ValueError('source no longer matches the declared inner-precision failure')
    if (float(trial['relaxation']) != ALPHA or not np.array_equal(
            trial['encoded_state'], trial['base_encoded_state'] + ALPHA*trial['finite_direction'])):
        raise ValueError('source is not the exact declared half-step material')
    return seed, pair


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run', required=True)
    args = p.parse_args(); pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc')
    out.mkdir(parents=True, exist_ok=False); snap = Snapshot(out)
    pipeline.write_json(out/'preparation_status.json', {'status': 'preparing'})
    try:
        state = snap.read(SOURCE+'/state.json')
        summary = snap.read(SOURCE+'/feedback-round2/feedback_summary.json')
        trial = load_arrays(snap.save(SOURCE+'/trial_material.npz', state['trial_sha256']))
        seed, pair = eligible_source(state, summary, trial)
        proto = snap.read(SOURCE+'/feedback-round2/feedback_protocol.json', pair['protocol_sha256'])
        if proto['sources']['trial_material']['sha256'] != state['trial_sha256']:
            raise RuntimeError('source trial differs from formally evaluated material')
        cfg = deepcopy(snap.read(SOURCE+'/config.json', state['config_sha256']))
        if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True):
            raise RuntimeError('frozen source dependencies changed')
        if pipeline.claim(ROOT/seed['path']) != seed: raise RuntimeError('latest seed changed')
        for claim in cfg['sources']:
            if not claim['path'].endswith('.dat'): snap.save(claim['path'], claim['sha256'])
        copied = carry_trial(ROOT/SOURCE, out)
        # 中文：只提高同一物质候选的辐射精度，不重新解码、迁移或改变任何物质字段。
        assert_written_trial(load_arrays(out/'trial_material.npz'), trial)
        cfg.update(run=args.run, workers=16, maximum_maps=8, feedback_every=4,
                   radiation_threshold=1e-4, seed='warm', warm_seed=seed,
                   candidate_relaxation=ALPHA, extension_of=SOURCE,
                   seed_provenance='latest state of identical material; no inherited map history',
                   extension_purpose='one bounded precision check after the first four maps missed radiation and heating gates')
        declaration = {'environment': pipeline.environment(), 'source_run': SOURCE, 'source_seed': seed,
                       'candidate_alpha': ALPHA, 'maximum_new_maps': 8, 'maximum_feedback_pairs': 2,
                       'feedback_every': 4, 'workers': 16, 'material_fields_unchanged': True,
                       'physical_dt_changed': False, 'science_gates_relaxed': False,
                       'automatic_budget_extension': False, 'true_inner_error_bound_available': False,
                       'source_summary': pipeline.claim(ROOT/SOURCE/'feedback-round2/feedback_summary.json')}
        pipeline.write_json(out/'precision_declaration.json', declaration)
        cfg['sources'] = list(cfg['sources']) + [seed, copied['source'], copied['destination'],
            pipeline.claim(out/'precision_declaration.json'), pipeline.claim(Path(__file__)),
            pipeline.claim(ROOT/'operations/half_step_precision.sbatch'),
            pipeline.claim(ROOT/SOURCE/'state.json'), declaration['source_summary']]
        pipeline.write_json(out/'config.json', cfg)
        pipeline.write_json(out/'native_trial_audit.json', audit_native_trial(cfg, trial))
        pipeline.write_json(out/'state.json', {'config_sha256': pipeline.sha256(out/'config.json'),
            'status': 'initializing', 'initialization_blocks': [], 'history': [],
            'slots': [args.run+f'/state_{i}.dat' for i in range(3)], 'current_slot': 0, 'active_map': None})
        pipeline.run_pipeline(out, 0, False)
        initialized = pipeline.read(out/'state.json')
        if (initialized['status'] != 'radiation' or initialized['history']
                or initialized['current_sha256'] != seed['sha256']):
            raise RuntimeError('initialization did not preserve the latest same-material seed')
        assert_written_trial(load_arrays(out/'trial_material.npz'), trial)
        pipeline.write_json(out/'preparation_status.json', {'status': 'complete', 'new_maps': 0})
    except BaseException as exc:
        pipeline.write_json(out/'preparation_status.json', {'status': 'failed', 'error': str(exc)}); raise


if __name__ == '__main__': main()
