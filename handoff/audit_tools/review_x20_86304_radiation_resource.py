"""Independent 86304 single-slab review. No scanner import or old-field baseline."""
import argparse
import math
from decimal import localcontext
from handoff.audit_tools.review_x20_85889_chord_scan import summarize
from pathlib import Path
from operations import x20_86304_radiation_contract as c
from handoff.audit_tools.review_x20_85889_chord_resource import review as review_slab


def integer(value, lower=0):
    if type(value) is not int or value < lower: raise ValueError('integer required')
    return value


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('nonnegative finite timing')
    return value


def phases(rows, names, wall, claims, source_payload=0):
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
            source_payload if name.startswith('source-') else 0))
        if payload != expected: raise ValueError('phase payload')
        rate = payload/duration if duration else None
        if not c.exact(rate, row['payload_bytes_per_second']): raise ValueError('phase payload rate')
        if not 0 < integer(row['cumulative_peak_rss_bytes']) < 6442450944: raise ValueError('phase RSS')


def review(data, wall=None):
    if data['status'] != c.STATUS or data['version'] != c.SCHEMA:
        raise ValueError('diagonal version identity')
    p = data['probe']; review_slab(p)
    if list(p['slab'])!=['gram','count','minima','maxima','pairs']: raise ValueError('slab schema/order')
    if any(type(x) is not int for x in p['shape']): raise ValueError('shape integers')
    if p['arithmetic']['numpy']!='2.5.2': raise ValueError('arithmetic version')
    if (p['arithmetic']['nmant'],p['arithmetic']['maxexp']) not in ((52,1024),(63,16384)): raise ValueError('arithmetic range')
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
    if type(data['source_job']) is not int or data['source_job']!=86304 or data['global_h1'] is not None: raise ValueError('source/scope')
    if data['labels']!=['AP','AF','AM','HP','HF','HM']: raise ValueError('field order')
    comparison = dict(local_only=True,global_h1=None,full_field_statistics_complete=False)
    rows = data['phases']; selected = [x for x in rows if x['name'] in c.PROBE_PHASES]
    phases(selected, c.PROBE_PHASES, finite(wall) if wall is not None else 1500, p)
    times = {x['name']:x['seconds'] for x in selected}
    if (times['slab'] != p['calculation_seconds'] or
        [times[f'slice-read-{i}'] for i in range(6)] != p['read_seconds_first_pass'] or
        times['field-hash-before'] != data['full_hash_seconds_before'] or
        times['field-hash-after'] != data['full_hash_seconds_after']): raise ValueError('phase/result times')
    with localcontext() as context:
        context.prec=80
        local_summary=summarize([p['slab']])
    return dict(local_summary=local_summary, first_group=0, group_count=32, global_h1=None,
                status='86304_resource_small_evidence_consistent', decimal_precision=80,
                comparison=comparison, field_bytes_read=data['field_bytes_read'],
                production_resource_preflight_complete=False, full_scan_authorized=False,
                physical_validation=False, strict_error_bound=False)


def terminal_check(result, allocation, terminal, child, expected_job_id, started):
    job = str(expected_job_id)
    if not job.isdigit() or job in ('85889', '86061', '86191', '86290', '86304') or result['job_id'] != job: raise ValueError('external new job ID')
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


def review_evidence(run, expected_commit, expected_code, terminal, expected_job_id):
    """Common evidence checks, also exercised with tiny fixtures; never grants production status."""
    run = Path(run); read = lambda name:c.read(run/name)
    if (run/'failure.json').exists() or not (run/'finished.json').is_file(): raise ValueError('failed/incomplete run')
    result = read('result.json'); finished = read('finished.json'); started = read('started.json')
    wall = finite(finished['wall_s'])
    if (finished['status'] != c.STATUS or not 0 < wall < 1500 or
        not 0 < integer(finished['peak_rss_bytes']) < 6442450944 or
        started['version'] != c.SCHEMA or integer(started['program_seconds']) != 1500 or
        integer(started['rss_limit_bytes']) != 6442450944): raise ValueError('lifecycle limits')
    answer = review(result, wall)
    if (started['status'] != 'incomplete' or finished['scheduler_terminal_verified'] is not False or
        finished['full_scan_authorized'] is not False): raise ValueError('lifecycle scope')
    peak = finished['peak_rss_bytes']
    if any(not 0 < integer(x) <= peak for x in [result['peak_rss_bytes'], result['probe']['peak_rss_bytes'],
            *[r['cumulative_peak_rss_bytes'] for r in result['phases']]]): raise ValueError('cumulative RSS proof')
    if result['git_commit'] != expected_commit or result['git_clean_before_after'] is not True:
        raise ValueError('frozen commit')
    for name in ('code-before.json', 'code-after.json'): c.check_code(read(name), expected_code)
    c.check_identity_pair(read('identity-before.json'), read('identity-after.json'), expected_code)
    if not c.exact(read('scheduler-terminal.json'), terminal): raise ValueError('external observer receipt')
    terminal_check(result, read('allocation.json'), terminal, read('batch-exit.json'), expected_job_id, started)
    if not c.exact(read('probe.json'), result['probe']): raise ValueError('probe receipt')
    for side in ('before', 'after'):
        saved = read('field-hash-'+side+'.json')
        if (not c.exact(saved['sha256'], result['full_sha256_'+side]) or
            not c.exact(saved['source_stats'], result['source_stats_'+side]) or
            saved['seconds'] != result['full_hash_seconds_'+side]): raise ValueError('hash receipt')
    for i,row in enumerate(result['phases'], 1):
        if not c.exact(read(f'phase-{i:02d}.json'), row): raise ValueError('phase receipt')
    return answer



def check_source_proof(proof,manifest):
    if proof['schema']!='86304-live-proof-v1' or type(proof['source_job']) is not int or proof['source_job']!=86304: raise ValueError('source proof identity')
    if proof['manifest_sha256']!=c.document_sha(manifest): raise ValueError('external manifest digest')
    for key,mkey in [('native','expected_native'),('opened_paths','expected_opened_paths')]:
        if not c.exact(proof[key],manifest[mkey]): raise ValueError('independent current native/runtime')
    if proof['archive_sha256']!=[x['sha256'] for x in manifest['archives']]: raise ValueError('both archives')
    if integer(proof['authenticated_payload_bytes'])!=manifest['payload_bytes_per_check'] or integer(proof['radiation_field_bytes_read'])!=0: raise ValueError('source payload')
    if proof['trial_all_arrays_bitwise_equal'] is not True or proof['live_native_recomputed'] is not True: raise ValueError('trial/native prerequisite')
    if proof['physical_validation'] is not False or proof['strict_error_bound'] is not False: raise ValueError('source promotion')
    if sorted(set(proof['opened_occurrences']))!=proof['opened_paths']: raise ValueError('native open log')

def review_run(run,expected_commit,expected_code,expected_sources,terminal,expected_job_id,submission):
    """Production review requires external sources and launch evidence, no shape override."""
    run=Path(run); read=lambda n:c.read(run/n)
    answer=review_evidence(run,expected_commit,expected_code,terminal,expected_job_id)
    result=read('result.json'); c.check_binding(expected_sources['binding']); claims=c.fields(expected_sources['binding'])
    if not c.exact(result['probe']['arithmetic'],c.ARITHMETIC): raise ValueError('production arithmetic')
    if result['probe']['shape']!=c.SHAPE: raise ValueError('true production shape required')
    for actual,expected in zip(result['source_claims'],claims):
        wanted=dict(expected,path=str(Path(submission['workdir'])/expected['path']))
        if not c.exact(actual,wanted): raise ValueError('current field/workdir')
    for side in ('before','after'):
        proof=read('source-'+side+'.json'); check_source_proof(proof,expected_sources)
        if not c.exact(proof,result['source_'+side]): raise ValueError('source receipt')
    if not c.exact(result['source_before'],result['source_after']): raise ValueError('source change')
    if integer(result['archive_bytes_read'])!=915885482 or integer(result['source_payload_bytes'])!=2*expected_sources['payload_bytes_per_check']: raise ValueError('source totals')
    c.check_identity_pair(read('identity-before.json'),read('identity-after.json'),expected_code,True)
    c.check_submission(submission,expected_commit,expected_code,expected_sources,expected_job_id,read('started.json')['execution']['run'],read('started.json'),read('allocation.json'),terminal)
    if read('identity-before.json')['checkout']!=submission['workdir']: raise ValueError('checkout association')
    phases(result['phases'],c.ALL_PHASES,read('finished.json')['wall_s'],result['probe'],expected_sources['payload_bytes_per_check'])
    if integer(result['code_bytes_read'])!=2*sum(x['size_bytes'] for x in expected_code.values()): raise ValueError('code payload')
    answer.update(review_complete=True,synthetic_evidence=result.get("synthetic",False),
                  production_resource_preflight_complete=result.get("synthetic",False) is not True,scheduler_terminal_verified=result.get("synthetic",False) is not True,source_job=86304,execution_job=expected_job_id,global_h1=None,full_field_statistics_complete=False)
    return answer

if __name__=='__main__':
    import json
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('output',type=Path)
    for key in ('expected-commit','expected-job-id','code','sources','terminal','submission'): p.add_argument('--'+key,required=True)
    a=p.parse_args();code=c.read(a.code);repo=Path(__file__).resolve().parents[2]
    before=c.reviewer_origins(repo,code)
    result=review_run(a.run,a.expected_commit,code,c.read(a.sources),c.read(a.terminal),a.expected_job_id,c.read(a.submission))
    if not c.exact(before,c.reviewer_origins(repo,code)): raise ValueError('reviewer changed')
    result['reviewer_project_modules']=before
    with a.output.open('x') as f: json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
