"""Bounded 32-CPU comparison followed by one declared radiation continuation."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'scripts'), str(ROOT / 'src')]
import pipeline
from operations.prepare_encoded_backtrack import audit_native_trial, load_arrays

ORDER = (4, 8, 16, 16, 8, 4)
NEW_MAPS = 32


def select_workers(cases):
    if [c['workers'] for c in cases] != list(ORDER):
        raise RuntimeError('incomplete or changed comparison order')
    if len({c['output_sha256'] for c in cases}) != 1:
        raise RuntimeError('worker-count outputs differ; science must not start')
    if any(c['maximum_worker_rss_mib'] >= 6144 for c in cases):
        raise RuntimeError('worker RSS exceeded the original resource gate')
    medians = {n: statistics.median(c['wall_s'] for c in cases if c['workers'] == n)
               for n in sorted(set(ORDER))}
    return min(medians, key=lambda n: (medians[n], n)), medians


def prepare_copy(template, source_run, seed, run, workers, maximum_maps, dependencies):
    """Copy exact material bytes; never invoke the legacy candidate migration."""
    run.mkdir(parents=True, exist_ok=False)
    trial = run / 'trial_material.npz'
    shutil.copyfile(source_run / 'trial_material.npz', trial)
    if pipeline.sha256(trial) != pipeline.read(source_run / 'state.json')['trial_sha256']:
        raise RuntimeError('copied material differs from frozen source')
    cfg = deepcopy(template)
    cfg.update(run=pipeline.relative(run), workers=workers, maximum_maps=maximum_maps,
               seed='warm', warm_seed=seed, feedback_every=8,
               seed_provenance='exact stopped Linux state; same 0.03125 material candidate')
    cfg['sources'].extend(dependencies + [pipeline.claim(trial)])
    pipeline.write_json(run / 'native_trial_audit.json', audit_native_trial(cfg, load_arrays(trial)))
    pipeline.write_json(run / 'config.json', cfg)
    pipeline.write_json(run / 'trial_migration.json', {
        'method': 'byte-identical candidate copy, no decoding or physical change',
        'source': pipeline.claim(source_run / 'trial_material.npz'), 'destination': pipeline.claim(trial)})
    pipeline.write_json(run / 'state.json', {
        'config_sha256': pipeline.sha256(run / 'config.json'), 'status': 'initializing',
        'initialization_blocks': [], 'history': [], 'current_slot': 0, 'active_map': None,
        'slots': [pipeline.relative(run / f'state_{i}.dat') for i in range(3)]})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    p.add_argument('--source-run', required=True)
    a = p.parse_args()
    pipeline.require_allocation(16)  # 保留原来的每 worker 6 GiB + 主进程 2 GiB 门。
    if int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) != 32 or len(os.sched_getaffinity(0)) < 32:
        raise RuntimeError('this experiment requires a real 32-CPU allocation and affinity')
    run, source = (pipeline.safe_path(ROOT, v) for v in (a.run, a.source_run))
    if not run.is_relative_to(ROOT / 'outputs/hpc'):
        raise RuntimeError('run must be under outputs/hpc')
    state = pipeline.read(source / 'state.json')
    template = pipeline.read(source / 'config.json')
    if (state['status'] != 'diagnostic_round_complete' or state.get('active_map')
            or state.get('pending_feedback') or template.get('candidate_relaxation') != .03125):
        raise RuntimeError('requires a stopped, settled 0.03125 source candidate')
    if pipeline.sha256(source / 'config.json') != state['config_sha256']:
        raise RuntimeError('source configuration changed')
    if pipeline.sha256(source / 'trial_material.npz') != state['trial_sha256']:
        raise RuntimeError('source material changed')
    if pipeline.verify_claims(ROOT, template['sources'], hash_files=True):
        raise RuntimeError('frozen source dependencies changed')
    seed = {'path': state['slots'][state['current_slot']], 'size_bytes': pipeline.STATE_BYTES,
            'sha256': state['current_sha256']}
    run.mkdir(parents=True, exist_ok=False)
    dependencies = [pipeline.claim(x) for x in (
        source / 'config.json', source / 'state.json', source / 'trial_material.npz',
        Path(__file__), ROOT / 'operations/scale_then_continue.sbatch')]
    report = {'status': 'running', 'science_run': False, 'cases': [], 'seed': seed,
              'environment': pipeline.environment(), 'cpu_affinity': sorted(os.sched_getaffinity(0)),
              'order': list(ORDER), 'maximum_workers': 16, 'sources': dependencies,
              'note': '4/8/16 workers in forward/reverse order, two full maps each; same seed/material',
              'next_science': {'run': pipeline.relative(run / 'science'), 'maximum_new_maps': NEW_MAPS,
                               'feedback_every': 8, 'candidate_relaxation': .03125}}
    pipeline.write_json(run / 'experiment.json', report)
    dependencies.append(pipeline.claim(run / 'experiment.json'))
    benchmark_path = run / 'benchmark.json'
    child, stopping = None, False

    def stop(_number, _frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGUSR1)

    signal.signal(signal.SIGUSR1, stop)

    def execute(command, log_path):
        nonlocal child
        if stopping:
            raise RuntimeError('stop requested; do not dispatch another stage')
        with log_path.open('x') as log:
            child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            code = child.wait()
        if code or stopping:
            raise RuntimeError(f'child exit={code}, stop={stopping}; inspect retained state before recovery')

    try:
        pipeline.write_json(benchmark_path, report)
        if pipeline.verify_claims(ROOT, [seed], hash_files=True):
            raise RuntimeError('radiation seed changed')
        for i, workers in enumerate(ORDER):
            if stopping:
                raise RuntimeError('stop requested')
            case = run / f'case{i+1:02d}-w{workers}'
            prepare_copy(template, source, seed, case, workers, 1, dependencies)
            started = time.monotonic()
            execute([sys.executable, 'hpc/pipeline.py', 'run', '--run', pipeline.relative(case),
                     '--maps-per-job', '1', '--no-feedback'], case / 'pipeline.log')
            result = pipeline.read(case / 'state.json')
            if len(result['history']) != 1 or result.get('active_map') or result['status'] == 'resource_gate_failed':
                raise RuntimeError('incomplete map or resource gate failure')
            report['cases'].append({'workers': workers, 'run': pipeline.relative(case),
                'total_wall_s': time.monotonic()-started, 'load_average': os.getloadavg(), **result['history'][0]})
            if len({c['output_sha256'] for c in report['cases']}) != 1:
                raise RuntimeError('output mismatch; stop before more cases or science')
            pipeline.write_json(benchmark_path, report)
        chosen, medians = select_workers(report['cases'])
        report.update(status='complete', chosen_workers=chosen, median_map_wall_s=medians)
        pipeline.write_json(benchmark_path, report)
        science = run / 'science'
        science_deps = dependencies + [pipeline.claim(benchmark_path)]
        prepare_copy(template, source, seed, science, chosen, NEW_MAPS, science_deps)
        # 同一物质候选，先初始化，再继续内层精度；绝不把测速六张累计为科学迭代。
        execute([sys.executable, 'operations/prepare_encoded_backtrack.py', '--run', pipeline.relative(science),
                 '--source-run', pipeline.relative(source), '--initialize-only'], science / 'initialize.log')
        execute([sys.executable, 'diagnostics/interval_diagnostic.py', '--run', pipeline.relative(science),
                 '--maps-per-job', str(NEW_MAPS), '--feedback-every', '8'], science / 'diagnostic.log')
        final = pipeline.read(science / 'state.json')
        if final['status'] not in {'diagnostic_round_complete', 'one_material_trial_accepted'}:
            raise RuntimeError(f"science ended in {final['status']}")
        pipeline.write_json(run / 'execution.json', {'status': 'complete_requires_review',
            'science_status': final['status'], 'science_maps': len(final['history'])})
    except Exception as exc:
        if report['status'] != 'complete':
            report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            pipeline.write_json(benchmark_path, report)
        pipeline.write_json(run / 'execution.json', {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
        raise


if __name__ == '__main__':
    main()
