"""Bounded full feedback pair replay after a bitwise-identical allocation-policy probe."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'src'), str(ROOT / 'scripts')]
import pipeline
from scripts import phase7b9_formal_feedback_pair_adapter as pair
from operations.recover_common_seed_feedback import OUTPUT_KEYS

SOURCE = ROOT / 'outputs/hpc/paired-precision-base-seeded-20260919'
EXPECTED = '4f33550f7239afbaa6565e74b541e9f1e6d499adfbd36a2b021871cfce4f737e'


def replay_protocol(original, run):
    """Only output paths and worker count change; scientific gates remain exact."""
    new = deepcopy(original)
    for key in OUTPUT_KEYS:
        new['configuration'][key] = str(Path(run) / Path(original['configuration'][key]).name)
    new['configuration']['maximum_concurrent_processes'] = 16
    return new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('replay requires declared import-time allocation setting')
    out = pipeline.safe_path(ROOT, args.run)
    out.relative_to(ROOT / 'outputs/hpc')
    out.mkdir(parents=True, exist_ok=False)
    status = {'status': 'preflight', 'new_maps': 0}
    pipeline.write_json(out / 'status.json', status)
    try:
        state = pipeline.read(SOURCE / 'state.json')
        if len(state['history']) != 4 or state.get('active_map'):
            raise RuntimeError('source four-map radiation endpoints not frozen')
        path = SOURCE / 'feedback-round2/feedback_protocol.json'
        original = pair.load_frozen_pair_protocol(path, EXPECTED, validate_sources=True)
        pair._validate_worker_template_sources(original)
        for label, row in zip(('previous', 'final'), state['history'][-2:], strict=True):
            claim = original['sources'][label + '_radiation']
            if claim['path'] != row['input_path'] or claim['sha256'] != row['input_sha256']:
                raise RuntimeError('radiation endpoints differ from declared round')
        pipeline.write_json(out / 'source_state_snapshot.json', state)
        pipeline.write_json(out / 'source_protocol_snapshot.json', original)
        new = replay_protocol(original, args.run)
        newpath = out / 'feedback_protocol.json'
        pipeline.write_json(newpath, new)
        declaration = {'git': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                       'environment': pipeline.environment(), 'source_protocol': pipeline.claim(path),
                       'new_protocol': pipeline.claim(newpath),
                       'code': [pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix('.sbatch'))],
                       'NUMPY_MADVISE_HUGEPAGE': '0', 'worker_count': 16,
                       'new_maps': 0, 'feedback_state_budget': 2,
                       'old_partials_reused': False, 'source_run_modified': False,
                       'changes': ['output paths', 'concurrency 2 to 16', 'NumPy hugepage requests disabled'],
                       'resource_accounting': 'Both states recomputed from scratch; old spent time remains in old run.'}
        pipeline.write_json(out / 'declaration.json', declaration)
        status['status'] = 'feedback'
        pipeline.write_json(out / 'status.json', status)
        # 中文：完整重算两态，不拼接旧资源失败记录，不放宽任何正式科学或资源门。
        summary = pair.run_pair(newpath, pipeline.sha256(newpath))
        pair.load_frozen_pair_protocol(path, EXPECTED, validate_sources=True)
        status.update(status='complete', decision=summary['decision'])
    except BaseException as exc:
        status.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        pipeline.write_json(out / 'status.json', status)


if __name__ == '__main__':
    main()
