"""One bounded confirmation for the stopped 0.03125 trial near the inner gate."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'src'), str(ROOT / 'scripts')]
import pipeline
from operations.scale_then_continue import prepare_copy


def eligible(config, state, summary):
    """Require the actual near-threshold state and stable heating; no broad retry."""
    if (config.get('candidate_relaxation') != .03125 or state['status'] != 'diagnostic_round_complete'
            or len(state['history']) != 32 or state.get('active_map') or state.get('pending_feedback')):
        raise RuntimeError('not the declared stopped 32-map source')
    threshold = config['radiation_threshold']
    if not threshold < state['history'][-1]['residual'] <= 1.5 * threshold:
        raise RuntimeError('not near the declared radiation gate; requires a different decision')
    gates = summary['gate_checks']
    if not all(gates.get(k) is True for k in ('last_two_atomic_heating_pass',
                'last_two_direct_heating_pass', 'last_two_formal_heating_pass')):
        raise RuntimeError('heating is not yet stable under its existing gates')


def prepare(run, source):
    pipeline.require_allocation(16)
    if not run.is_relative_to(ROOT / 'outputs/hpc'):
        raise RuntimeError('run outside outputs/hpc')
    if run.exists():
        raise RuntimeError('confirmation already exists; inspect it rather than overwrite or repeat')
    cfg = pipeline.read(source / 'config.json')
    state = pipeline.read(source / 'state.json')
    last = state['diagnostic']['rounds'][-1]
    folder = (ROOT / last['ledger']).parent
    summary = pipeline.read(folder / 'feedback_summary.json')
    eligible(cfg, state, summary)
    if (pipeline.sha256(source / 'config.json') != state['config_sha256']
            or pipeline.sha256(source / 'trial_material.npz') != state['trial_sha256']
            or pipeline.sha256(folder / 'feedback_protocol.json') != last['protocol_sha256']
            or summary['protocol_sha256'] != last['protocol_sha256']):
        raise RuntimeError('source trial/config/formal feedback identity changed')
    if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True):
        raise RuntimeError('frozen dependencies changed')
    seed = {'path': state['slots'][state['current_slot']], 'size_bytes': pipeline.STATE_BYTES,
            'sha256': state['current_sha256']}
    if pipeline.verify_claims(ROOT, [seed], hash_files=True):
        raise RuntimeError('source endpoint changed')
    deps = [pipeline.claim(p) for p in (source/'config.json', source/'state.json',
        source/'trial_material.npz', folder/'feedback_summary.json', folder/'feedback_protocol.json',
        Path(__file__), ROOT/'operations/confirm_inner_threshold.sbatch')]
    prepare_copy(cfg, source, seed, run, 16, 8, deps)
    # 只改变新 run 的预算和反馈频率；物质、物理 dt、门槛完全继承。
    new = pipeline.read(run/'config.json')
    new.update(feedback_every=4, confirmation_source_run=pipeline.relative(source),
               purpose='8-map near-threshold confirmation; no automatic extension')
    pipeline.write_json(run/'config.json', new)
    initial = pipeline.read(run/'state.json')
    initial['config_sha256'] = pipeline.sha256(run/'config.json')
    pipeline.write_json(run/'state.json', initial)
    print('Declared '+pipeline.relative(run), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    parser.add_argument('--source-run',required=True)
    args=parser.parse_args()
    prepare(pipeline.safe_path(ROOT,args.run),pipeline.safe_path(ROOT,args.source_run))
