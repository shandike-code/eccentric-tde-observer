"""Bounded step-sixteen amplitude test from the audited fifteenth confirmation.

Only numerical relaxation changes: 1/32, then 1/64 if not accepted.
The frozen physical old time level and all scientific gates are preserved.
"""
from contextlib import contextmanager
import argparse
import fcntl
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'scripts'), str(ROOT/'hpc')]
from operations import numbered_confirmation_step as stage
from operations import response_direction_batch as batch
from operations import composite_hybrid_batch as reused
from operations.constrained_hybrid_batch import relay_dispatch
import pipeline

SOURCE = 'outputs/hpc/outer-steps13to15-20260922/step15/next-step'
CONFIRMATION = 'outputs/hpc/outer-steps13to15-20260922/final-confirmation'
# 只改变非线性物质迭代的数值位移；旧物理时间层与 dt 不变。
ALPHAS = {'full': 1/32, 'half': 1/64}
LIMITS = {'control': 2, 'full': 8, 'half': 8}
PREFLIGHT = 'outputs/hpc/step16-amplitude-preflight-20260923/result.json'


@contextmanager
def amplitude_contract():
    """Process-local adapter; never edit the frozen source modules on disk."""
    old = batch.ALPHAS, batch.LIMITS
    batch.ALPHAS, batch.LIMITS = dict(ALPHAS), dict(LIMITS)
    try:
        yield
    finally:
        batch.ALPHAS, batch.LIMITS = old


def require_source():
    stage.configure(SOURCE, 15)
    if not stage.confirmation_passed(ROOT/CONFIRMATION):
        raise RuntimeError('fifteenth precision confirmation did not pass')
    preflight = pipeline.read(ROOT/PREFLIGHT)
    if preflight.get('native_exact_rebase') is not True or preflight.get('alphas') != ALPHAS:
        raise RuntimeError('native real-artifact preflight did not pass')
    reused.verify(preflight['sources'])


def execute(out):
    error_path = out/'amplitude-probe-error.json'
    if error_path.exists() and not pipeline.read(error_path).get('ledger_only_recoverable'):
        raise RuntimeError('previous program/resource failure requires review; no blind retry')
    require_source()
    with amplitude_contract():
        # prepare_next replays actual source response and all derived gates,
        # hashes the seed, writes trial before initialization and pins this code.
        stage.run_next(out, ROOT/CONFIRMATION)
        batch.check_budget(batch.child_states(out))
        status = pipeline.read(out/'status.json')
        accepted = status['status'] == 'formal_acceptance_requires_review'
        corroborated = False
        if accepted:
            name = status['candidate']
            state = pipeline.read(out/name/'state.json')
            rd = ROOT/Path(state['diagnostic']['rounds'][-1]['ledger']).parent
            corroborated = stage.fresh_contraction(pipeline.read(rd/'fresh_control_comparison.json'))
        reused.immutable(out/'amplitude-probe-decision.json', {
            'outer_step_index': 16, 'alphas': ALPHAS,
            'maximum_maps': 18, 'maximum_pairs': 5,
            'formal_finite_step_accepted': accepted,
            'fresh_control_corroborated': corroborated,
            'requires_review_before_confirmation_or_step17': True,
            'physical_time_advanced': False, 'gates_relaxed': False,
            'coupled_column_accepted': False})
        reused.archive(out, 'amplitude-probe-finished')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    a = p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('hugepage control required')
    out = pipeline.safe_path(ROOT, a.run)
    out.relative_to(ROOT/'outputs/hpc')
    out.mkdir(parents=True, exist_ok=True)
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGUSR1, reused.stop)
        signal.signal(signal.SIGTERM, reused.stop)
        with relay_dispatch():
            try:
                execute(out)
            except reused.Stopped as exc:
                batch.mark(out, 'interrupted', reason=str(exc))
                reused.archive(out, 'interrupted')
            except Exception as exc:
                pending = any(s.get('status') == 'diagnosis_incomplete'
                    and (s.get('pending_feedback') or {}).get('stage') == 'ledger'
                    for s in batch.child_states(out).values())
                # Preserve the underlying terminal state if one already exists.
                pipeline.write_json(out/'amplitude-probe-error.json', {
                    'error': repr(exc), 'ledger_only_recoverable': pending})
                if not (out/'status.json').exists() or pipeline.read(out/'status.json')['status'] not in batch.TERMINAL:
                    batch.mark(out, 'diagnosis_incomplete' if pending else 'failed', error=repr(exc))
                reused.archive(out, 'failed')
                raise


if __name__ == '__main__':
    main()
