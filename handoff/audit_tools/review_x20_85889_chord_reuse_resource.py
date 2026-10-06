"""Independent reuse evidence reviewer: strict JSON, Decimal80, external job/code pins.

No scanner imports. review_evidence accepts explicit synthetic references for tests;
production review_run always loads the fixed historical byte pins.
"""
import argparse
import math
from pathlib import Path
from operations import x20_85889_chord_reuse_contract as c
from handoff.audit_tools.review_x20_85889_chord_resource import review as review_slab


def integer(value, lower=0):
    if type(value) is not int or value < lower: raise ValueError('integer required')
    return value


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('nonnegative finite timing')
    return value


def phases(rows, names, wall, claims, archive=False):
    if [x['name'] for x in rows] != names: raise ValueError('phase order/completeness')
    previous = 0; size = 32*claims['shape'][1]*claims['shape'][2]*8
    total = sum(x['size_bytes'] for x in claims['source_claims'])
    for row in rows:
        a = finite(row['start_s']); b = finite(row['end_s']); duration = finite(row['seconds'])
        if not previous <= a <= b <= wall or duration != b-a: raise ValueError('phase timing')
        previous = b; payload = integer(row['payload_bytes'])
        name = row['name']
        expected = total if name.startswith('field-hash-') else (
            size if name.startswith(('slice-read-', 'slice-reread-')) else (
            303877902 if archive and name.startswith('live-') else 0))
        if payload != expected: raise ValueError('phase payload')
        rate = payload/duration if duration else None
        if not c.exact(rate, row['payload_bytes_per_second']): raise ValueError('phase payload rate')
        if not 0 < integer(row['cumulative_peak_rss_bytes']) < 6442450944: raise ValueError('phase RSS')


def review(data, reference, wall=None):
    if data['status'] != c.STATUS or type(data['version']) is not int or data['version'] != 3:
        raise ValueError('reuse version identity')
    p = data['probe']; review_slab(p)
    for value in [p['first_group'], p['group_count'], p['slab']['count'], p['field_bytes_read'],
                  p['arithmetic']['rounding_mode_code'], p['arithmetic']['nmant'], p['arithmetic']['maxexp'],
                  data['field_bytes_read'], data['kernel_calls']]: integer(value)
    if data['kernel_calls'] != 1: raise ValueError('exactly one kernel call')
    for key in ('new_maps', 'new_feedback', 'new_material'):
        if integer(data[key]) != 0 or integer(p[key]) != 0: raise ValueError('unexpected physics work')
    for key in ('full_field_statistics_complete', 'full_scan_authorized', 'physical_inference_authorized', 'strict_error_bound'):
        if data[key] is not False: raise ValueError('unsupported promotion')
    if data['full_field_sha_refreshed'] is not True: raise ValueError('full source hashes missing')
    claims = data['source_claims']
    if not c.exact(claims, p['source_claims']): raise ValueError('source claims')
    for key in ('source_stats_before', 'source_stats_after'):
        if not c.exact(data[key], p[key]) or not c.exact(data[key], data['source_stats_before']):
            raise ValueError('source stat proof')
        for row in data[key]:
            if len(row) != 5: raise ValueError('stat length')
            for x in row: integer(x)
    hashes = [x['sha256'] for x in claims]
    for key in ('full_sha256_before', 'full_sha256_after'):
        if data[key] != hashes: raise ValueError('whole SHA proof')
    if data['field_bytes_read'] != 2*sum(integer(x['size_bytes']) for x in claims)+p['field_bytes_read']:
        raise ValueError('field payload')
    for x in [data['full_hash_seconds_before'], data['full_hash_seconds_after'], p['calculation_seconds'],
              *p['read_seconds_first_pass']]: finite(x)
    if len(p['read_seconds_first_pass']) != 6: raise ValueError('six read times')
    comparison = c.compare(p, reference)
    rows = data['phases']; selected = [x for x in rows if x['name'] in c.PROBE_PHASES]
    phases(selected, c.PROBE_PHASES, finite(wall) if wall is not None else 1500, p)
    times = {x['name']:x['seconds'] for x in selected}
    if (times['slab'] != p['calculation_seconds'] or
        [times[f'slice-read-{i}'] for i in range(6)] != p['read_seconds_first_pass'] or
        times['field-hash-before'] != data['full_hash_seconds_before'] or
        times['field-hash-after'] != data['full_hash_seconds_after']): raise ValueError('phase/result times')
    return dict(status='reuse_resource_small_evidence_consistent', decimal_precision=80,
                comparison=comparison, field_bytes_read=data['field_bytes_read'],
                production_resource_preflight_complete=False, full_scan_authorized=False,
                physical_validation=False, strict_error_bound=False)


def terminal_check(result, allocation, terminal, child, expected_job_id, started):
    job = str(expected_job_id)
    if not job.isdigit() or job in ('85889', '86061') or result['job_id'] != job: raise ValueError('external new job ID')
    tokens = c.scheduler_tokens
    final = tokens(terminal['scontrol']); alloc = tokens(allocation['scontrol'])
    expected = dict(JobId=job, JobState='COMPLETED', ExitCode='0:0')
    if any(final.get(k) != v for k,v in expected.items()): raise ValueError('actual terminal')
    expected = dict(JobId=job, JobState='RUNNING', NumCPUs='4', NumTasks='1', NumNodes='1',
                    Partition='Students', QOS='qos_stu_default', TimeLimit='00:30:00')
    if any(alloc.get(k) != v for k,v in expected.items()) or alloc.get('MinMemoryNode') not in ('16G', '16384M'):
        raise ValueError('actual allocation')
    if (terminal['job_id'] != job or allocation['job_id'] != job or child['job_id'] != job or
        integer(child['child_exit_status']) != 0): raise ValueError('child/observer identity')
    start = finite(started['started_unix']); a = finite(allocation['observed_unix'])
    end = finite(terminal['observed_unix']); exit_time = finite(child['recorded_unix'])
    if not start <= a <= exit_time <= end: raise ValueError('external observation chronology')


def review_evidence(run, expected_commit, expected_code, terminal, expected_job_id, reference):
    """Common evidence checks, also exercised with tiny fixtures; never grants production status."""
    run = Path(run); read = lambda name:c.read(run/name)
    if (run/'failure.json').exists() or not (run/'finished.json').is_file(): raise ValueError('failed/incomplete run')
    result = read('result.json'); finished = read('finished.json'); started = read('started.json')
    wall = finite(finished['wall_s'])
    if (finished['status'] != c.STATUS or not 0 < wall < 1500 or
        not 0 < integer(finished['peak_rss_bytes']) < 6442450944 or
        integer(started['version']) != 3 or integer(started['program_seconds']) != 1500 or
        integer(started['rss_limit_bytes']) != 6442450944): raise ValueError('lifecycle limits')
    answer = review(result, reference, wall)
    if (started['status'] != 'incomplete' or finished['scheduler_terminal_verified'] is not False or
        finished['full_scan_authorized'] is not False): raise ValueError('lifecycle scope')
    peak = finished['peak_rss_bytes']
    if any(not 0 < integer(x) <= peak for x in [result['peak_rss_bytes'], result['probe']['peak_rss_bytes'],
            *[r['cumulative_peak_rss_bytes'] for r in result['phases']]]): raise ValueError('cumulative RSS proof')
    if result['git_commit'] != expected_commit or result['git_clean_before_after'] is not True:
        raise ValueError('frozen commit')
    for name in ('code-before.json', 'code-after.json'): c.check_code(read(name), expected_code)
    if not c.exact(read('scheduler-terminal.json'), terminal): raise ValueError('external observer receipt')
    terminal_check(result, read('allocation.json'), terminal, read('batch-exit.json'), expected_job_id, started)
    if not c.exact(read('probe.json'), result['probe']): raise ValueError('probe receipt')
    for side in ('before', 'after'):
        saved = read('field-hash-'+side+'.json')
        if (not c.exact(saved['sha256'], result['full_sha256_'+side]) or
            not c.exact(saved['source_stats'], result['source_stats_'+side]) or
            saved['seconds'] != result['full_hash_seconds_'+side]): raise ValueError('hash receipt')
    if not c.exact(read('comparison.json'), answer['comparison']) or not c.exact(result['comparison'], answer['comparison']):
        raise ValueError('comparison receipt')
    for i,row in enumerate(result['phases'], 1):
        if not c.exact(read(f'phase-{i:02d}.json'), row): raise ValueError('phase receipt')
    return answer


def review_run(run, expected_commit, expected_code, expected_binding, terminal, expected_job_id):
    """Production acceptance has no synthetic-reference or arithmetic override."""
    run = Path(run); read = lambda name:c.read(run/name)
    reference, blobs = c.history(run)
    answer = review_evidence(run, expected_commit, expected_code, terminal, expected_job_id, reference)
    result = read('result.json'); before = read('binding-before.json'); after = read('binding-after.json')
    if not c.exact(before, after): raise ValueError('small binding changed')
    def canonical(x):
        x = c.loads(__import__('json').dumps(x))
        for source in x['physical_sources'].values(): source.pop('local_path', None)
        return x
    if not c.exact(canonical(before), canonical(expected_binding)): raise ValueError('external source binding')
    if result['probe']['shape'] != [9632,32,4096] or len(before['field_claims']) != 6:
        raise ValueError('production layout')
    roots = []
    for claim, original in zip(result['source_claims'], before['field_claims']):
        if (claim['size_bytes'] != original['size_bytes'] or claim['sha256'] != original['sha256'] or
            not claim['path'].endswith('/'+original['path'])): raise ValueError('production field claim')
        roots.append(claim['path'][:-len(original['path'])])
    if len(set(roots)) != 1: raise ValueError('production field root')
    live = result['live_before']; later = result['live_after']
    stable = lambda x:{k:v for k,v in x.items() if k != 'environment_metadata_reads'}
    if (not c.exact(stable(live), stable(later)) or not c.exact(live, read('live-before.json')) or
        not c.exact(later, read('live-after.json'))): raise ValueError('live proof changed')
    for key in ('live_native_recomputed','trial_mirrored_arrays_bitwise','archive_payload_rehashed'):
        if live[key] is not True: raise ValueError('live prerequisite')
    # 前后相等不认证来源；另与固定SHA的86061历史runtime清单逐项比较。
    historical_live = c.loads(blobs['history-result.json'])['live_before']
    for key, expected in (('groups',9632), ('directions',32), ('depths',4096), ('blocks',76)):
        if integer(live[key]) != expected: raise ValueError('live geometry identity')
    for key in ('live_dependencies', 'native_opened_data_paths'):
        if not c.exact(live[key], historical_live[key]): raise ValueError('pinned live runtime identity')
    for key in ('physical_validation', 'strict_error_bound'):
        if live[key] is not False: raise ValueError('unsupported live promotion')
    if (integer(live['live_original_code_files']) != 801 or integer(live['phase']) != 1367 or
        live['dt'] != 889.419892762322 or integer(live['radiation_field_bytes_read']) != 0 or
        integer(live['archive_bytes_read']) != before['source_archive']['size_bytes'] or
        live['archive_sha256'] != before['source_archive']['sha256'] or
        integer(result['archive_bytes_read']) != 607755804 or
        integer(result['historical_bytes_read']) != sum(len(b) for b in blobs.values()) or
        integer(result['code_bytes_read']) != 2*sum(x['size_bytes'] for x in expected_code.values())):
        raise ValueError('live/archive/payload identity')
    phases(result['phases'], c.ALL_PHASES, read('finished.json')['wall_s'], result['probe'], archive=True)
    answer.update(production_resource_preflight_complete=True, scheduler_terminal_verified=True,
                  job_id=str(expected_job_id), git_commit=expected_commit, archive_bytes_read=607755804)
    return answer


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('run', type=Path); p.add_argument('output', type=Path)
    for name in ('expected-commit', 'expected-job-id', 'code', 'binding', 'terminal'):
        p.add_argument('--'+name, required=True)
    a = p.parse_args()
    result = review_run(a.run, a.expected_commit, c.read(a.code), c.read(a.binding), c.read(a.terminal), a.expected_job_id)
    with a.output.open('x') as f: __import__('json').dump(result, f, indent=2, allow_nan=False); f.write('\n')
