"""Production reviewer acceptance on historical JSON with synthetic lifecycle metadata.

No fields, native configuration, Slurm, or production driver are executed here.
The fixture is NOT evidence of a new completed job or measured reuse performance.
"""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from operations import x20_85889_chord_reuse_contract as c
from handoff.audit_tools import review_x20_85889_chord_reuse_resource as review


def save(path, data):
    path.write_text(json.dumps(data, allow_nan=False))


@pytest.fixture
def evidence(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    source = repo/'outputs/review-20260925/x20-chord-resource-86061-received'
    history = repo/'outputs/review-20260925/chord-reuse-resource-history-20261006'
    if not source.exists() or not history.exists():
        pytest.skip('requires the pinned historical small JSON fixture')
    for name in c.HISTORY_PINS:
        (tmp_path/name).write_bytes((history/name).read_bytes())
    reference, blobs = c.history(tmp_path)
    result = c.read(source/'result.json')
    bound = c.read(source/'binding-before.json')
    # 原数值摘要不改。仅为审阅入口构造明确虚拟的新生命周期和28阶段。
    commit = 'SYNTHETIC-REVIEW-FIXTURE-NOT-A-COMMIT'; job = '900002'
    peak = result['peak_rss_bytes']
    code = {}
    for directory in ('operations', 'handoff/audit_tools'):
        for p in (repo/directory).glob('*chord*'):
            if p.suffix in ('.py', '.sbatch'):
                raw = p.read_bytes()
                code[str(p.relative_to(repo))] = dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    c.check_code(code, code)
    rows = []
    total = sum(x['size_bytes'] for x in reference['source_claims'])
    for i, name in enumerate(c.ALL_PHASES):
        payload = total if name.startswith('field-hash-') else (
            33554432 if name.startswith(('slice-read-', 'slice-reread-')) else (
            303877902 if name.startswith('live-') else 0))
        rows.append(dict(name=name, start_s=float(i), end_s=float(i+1), seconds=1.0,
                         payload_bytes=payload, payload_bytes_per_second=payload/1.0,
                         cumulative_peak_rss_bytes=peak))
    result.update(status=c.STATUS, version=3, kernel_calls=1, phases=rows,
                  git_commit=commit, job_id=job, synthetic=True,
                  full_hash_seconds_before=1.0, full_hash_seconds_after=1.0,
                  archive_bytes_read=607755804, historical_bytes_read=sum(map(len, blobs.values())),
                  code_bytes_read=2*sum(x['size_bytes'] for x in code.values()))
    result['probe'].update(calculation_seconds=1.0, read_seconds_first_pass=[1.0]*6)
    result['comparison'] = c.compare(result['probe'], reference)
    terminal = dict(job_id=job, observed_unix=140.0, synthetic=True,
                    scontrol=f'JobId={job} JobState=COMPLETED ExitCode=0:0')
    allocation = dict(job_id=job, observed_unix=101.0, synthetic=True,
        scontrol=f'JobId={job} JobState=RUNNING NumCPUs=4 NumTasks=1 NumNodes=1 Partition=Students QOS=qos_stu_default TimeLimit=00:30:00 MinMemoryNode=16G')
    files = {'result.json': result, 'probe.json': result['probe'],
        'started.json': dict(status='incomplete', version=3, started_unix=100.0,
            program_seconds=1500, rss_limit_bytes=6442450944),
        'finished.json': dict(status=c.STATUS, wall_s=30.0, peak_rss_bytes=peak,
            scheduler_terminal_verified=False, full_scan_authorized=False),
        'allocation.json': allocation, 'scheduler-terminal.json': terminal,
        'batch-exit.json': dict(job_id=job, child_exit_status=0, recorded_unix=135.0, synthetic=True),
        'comparison.json': result['comparison']}
    for side in ('before', 'after'):
        files[f'code-{side}.json'] = code
        files[f'binding-{side}.json'] = bound
        files[f'live-{side}.json'] = result['live_'+side]
        files[f'field-hash-{side}.json'] = dict(sha256=result['full_sha256_'+side],
            source_stats=result['source_stats_'+side], seconds=1.0)
    files.update({f'phase-{i:02d}.json': row for i, row in enumerate(rows, 1)})
    for name, data in files.items(): save(tmp_path/name, data)
    return tmp_path, commit, code, bound, terminal, job


def test_full_production_review_entry(evidence):
    answer = review.review_run(*evidence)
    assert answer['production_resource_preflight_complete']
    assert answer['job_id'] == '900002' and not answer['full_scan_authorized']


@pytest.mark.parametrize('change', ['external_binding', 'source_path', 'live_flag', 'live_changed',
    'phase', 'dt', 'archive', 'history_bytes', 'code_bytes', 'stage_missing', 'geometry',
    'dependency', 'opened_paths', 'geometry_bool', 'dependency_size_bool', 'live_promotion', 'closed_job'])
def test_production_gate_rejections(evidence, change):
    args = list(evidence); run = args[0]; result = c.read(run/'result.json')
    if change == 'external_binding':
        args[3] = copy.deepcopy(args[3]); args[3]['accepted_outer_steps'] = 21
    elif change == 'closed_job':
        args[4] = copy.deepcopy(args[4]); args[5] = '85889'; result['job_id'] = '85889'
        for name in ('allocation.json', 'batch-exit.json', 'scheduler-terminal.json'):
            record = c.read(run/name); record['job_id'] = '85889'
            if 'scontrol' in record: record['scontrol'] = record['scontrol'].replace('900002','85889')
            save(run/name, record)
            if name == 'scheduler-terminal.json': args[4] = record
    elif change == 'source_path':
        result['source_claims'][0]['path'] = '/wrong/name.dat'
        result['probe']['source_claims'] = copy.deepcopy(result['source_claims'])
        save(run/'probe.json', result['probe'])
    elif change in ('history_bytes', 'code_bytes'): result[{'history_bytes':'historical_bytes_read', 'code_bytes':'code_bytes_read'}[change]] += 1
    elif change == 'stage_missing': result['phases'].pop()
    else:
        live = result['live_before']
        if change == 'live_flag': live['live_native_recomputed'] = False
        elif change == 'live_changed': live['environment']['numpy'] = 'changed'
        elif change == 'phase': live['phase'] = 1368
        elif change == 'dt': live['dt'] = 1.0
        elif change == 'archive': live['archive_sha256'] = '0'*64
        elif change == 'geometry': live['groups'] = 1
        elif change == 'geometry_bool': live['blocks'] = True
        elif change == 'dependency': live['live_dependencies'][0]['sha256'] = '0'*64
        elif change == 'dependency_size_bool': live['live_dependencies'][0]['size_bytes'] = True
        elif change == 'opened_paths': live['native_opened_data_paths'] = []
        elif change == 'live_promotion': live['physical_validation'] = True
        if change != 'live_changed': result['live_after'] = copy.deepcopy(live)
        for side in ('before','after'): save(run/f'live-{side}.json', result['live_'+side])
    save(run/'result.json', result)
    with pytest.raises(ValueError): review.review_run(*args)
