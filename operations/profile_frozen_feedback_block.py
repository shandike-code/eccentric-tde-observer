"""Profile one already committed feedback block without changing its source run."""
from __future__ import annotations

import argparse
import cProfile
import io
from pathlib import Path
import pstats
import signal
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'src'), str(ROOT / 'scripts')]
import pipeline
from scripts import phase7b9_formal_feedback_pair_adapter as adapter

SOURCE = ROOT / 'outputs/hpc/paired-precision-base-seeded-20260919'
PROTOCOL_SHA = '4f33550f7239afbaa6565e74b541e9f1e6d499adfbd36a2b021871cfce4f737e'
BLOCK = 24


def compare_arrays(reference: Path, replay: Path) -> dict:
    """Report finite array discrepancies without granting scientific acceptance."""
    result = {}
    with np.load(reference, allow_pickle=False) as a, np.load(replay, allow_pickle=False) as b:
        if set(a.files) != set(b.files):
            raise RuntimeError('profiled block fields differ')
        for key in a.files:
            x, y = a[key], b[key]
            if x.shape != y.shape or x.dtype != y.dtype:
                raise RuntimeError(f'profiled block shape/type changed: {key}')
            if np.issubdtype(x.dtype, np.number):
                if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
                    raise RuntimeError(f'nonfinite block array: {key}')
                delta = float(np.max(np.abs(x.astype(float) - y.astype(float)))) if x.size else 0.0
                scale = float(np.max(np.abs(x))) if x.size else 0.0
                result[key] = {'bitwise_equal': x.tobytes() == y.tobytes(),
                               'maximum_absolute_difference': delta,
                               'reference_maximum_absolute_value': scale,
                               'relative_to_reference_maximum': delta / scale if scale > 0 else None}
            else:
                if not np.array_equal(x, y):
                    raise RuntimeError(f'block metadata differs: {key}')
    return result


def stop(_signum, _frame):
    raise TimeoutError('Slurm stopping signal; preserve incomplete profile')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    pipeline.require_allocation(1)
    out = args.run.resolve()
    out.relative_to((ROOT / 'outputs/hpc').resolve())
    out.mkdir(parents=True, exist_ok=False)
    signal.signal(signal.SIGUSR1, stop)
    signal.signal(signal.SIGTERM, stop)
    protocol_path = SOURCE / 'feedback-round2/feedback_protocol.json'
    profiler = cProfile.Profile()
    status = {'status': 'preflight', 'scientific_acceptance': False}
    pipeline.write_json(out / 'status.json', status)
    try:
        state = pipeline.read(SOURCE / 'state.json')
        if len(state['history']) != 4 or state.get('active_map'):
            raise RuntimeError('source radiation slots not at declared four-map endpoint')
        # 中文：原输入只读，先验完整协议及继承源；不把剖析输出接入正式反馈。
        protocol = adapter.load_frozen_pair_protocol(protocol_path, PROTOCOL_SHA, validate_sources=True)
        adapter._validate_worker_template_sources(protocol)
        manifest_path = SOURCE / 'feedback-round2/feedback/final_manifest.json'
        manifest = pipeline.read(manifest_path)
        claims = [r for r in manifest['completed_blocks'] if r['block_index'] == BLOCK]
        if len(claims) != 1:
            raise RuntimeError('reference block is not uniquely committed')
        reference = ROOT / claims[0]['partial_path']
        if pipeline.sha256(reference) != claims[0]['partial_sha256']:
            raise RuntimeError('reference partial changed')
        declaration = {'protocol': pipeline.claim(protocol_path), 'block': claims[0],
                       'state': state, 'environment': pipeline.environment(),
                       'git': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                       'code': [pipeline.claim(Path(__file__)), pipeline.claim(ROOT / 'operations/profile_frozen_feedback_block.sbatch')],
                       'profile_overhead_present': True, 'changes_physics': False,
                       'source_run_is_not_modified': True, 'block_count_budget': 1}
        pipeline.write_json(out / 'declaration.json', declaration)
        pipeline.write_json(out / 'protocol_snapshot.json', protocol)
        status['status'] = 'profiling'
        pipeline.write_json(out / 'status.json', status)
        started = time.perf_counter()
        profiler.runcall(adapter.run_worker_adapter, protocol_path, PROTOCOL_SHA,
                        'final', BLOCK, out / 'block24.npz', out / 'block24.json')
        wall = time.perf_counter() - started
        # 中文：完成后再次验原辐射源，避免并行时槽位变化被当作同输入测速。
        adapter.load_frozen_pair_protocol(protocol_path, PROTOCOL_SHA, validate_sources=True)
        comparison = compare_arrays(reference, out / 'block24.npz')
        pipeline.write_json(out / 'comparison.json', comparison)
        status.update(status='complete', profiled_worker_wall_s=wall,
                      original_worker_wall_s=claims[0]['runtime_s'])
    except BaseException as exc:
        status.update(status='failed_or_interrupted', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        profiler.disable()
        profiler.dump_stats(str(out / 'worker.prof'))
        if profiler.getstats():
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.sort_stats('cumulative').print_stats(50)
            stats.sort_stats('tottime').print_stats(50)
            (out / 'profile.txt').write_text(stream.getvalue())
        pipeline.write_json(out / 'status.json', status)


if __name__ == '__main__':
    main()
