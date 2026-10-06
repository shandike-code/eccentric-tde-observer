"""Independent review of whole-source authentication plus one resource slab."""
import argparse
import json
import math
from pathlib import Path
from handoff.audit_tools.review_x20_85889_chord_resource import review as review_slab


def review(data):
    if data['status']!='authenticated_resource_probe_complete_requires_review' or data['version']!=2:
        raise ValueError('resource v2 identity')
    probe=data['probe'];small=review_slab(probe);claims=data['source_claims']
    if (claims!=probe['source_claims'] or data['source_stats_before']!=probe['source_stats_before']
        or data['source_stats_after']!=data['source_stats_before']):raise ValueError('source chain')
    hashes=[c['sha256'] for c in claims]
    if any(len(h)!=64 or any(x not in '0123456789abcdef' for x in h) for h in hashes):raise ValueError('source SHA format')
    if data['full_sha256_before']!=hashes or data['full_sha256_after']!=hashes:raise ValueError('full source SHA')
    if data['full_field_sha_refreshed'] is not True:raise ValueError('whole source not authenticated')
    if data['field_bytes_read']!=2*sum(c['size_bytes'] for c in claims)+probe['field_bytes_read']:
        raise ValueError('whole hash byte budget')
    for key in ('full_field_statistics_complete','full_scan_authorized','physical_inference_authorized','strict_error_bound'):
        if data[key] is not False:raise ValueError('unsupported scientific promotion')
    if any(data[k]!=0 for k in ('new_maps','new_feedback','new_material')):raise ValueError('unexpected physics work')
    times=[data['full_hash_seconds_before'],data['full_hash_seconds_after'],probe['calculation_seconds'],*probe['read_seconds_first_pass']]
    if len(probe['read_seconds_first_pass'])!=6 or any(not isinstance(t,(int,float)) or not math.isfinite(t) or t<0 for t in times):
        raise ValueError('invalid timing')
    return dict(status='authenticated_resource_small_statistics_consistent',slabs=1,combinations=4,
        field_bytes_read=data['field_bytes_read'],full_field_sha_refreshed=True,
        full_field_statistics_complete=False,full_scan_authorized=False,physical_validation=False,strict_error_bound=False)


def review_run(run, expected_commit, expected_binding, terminal):
    """验收必须同时消费完整生命周期、外部来源绑定和实际Slurm终态。"""
    run=Path(run)
    if (run/'failure.json').exists() or not (run/'finished.json').is_file():
        raise ValueError('failed or incomplete run cannot be accepted')
    read=lambda name:json.loads((run/name).read_text())
    finished=read('finished.json');result=read('result.json')
    answer=review(result)
    if (finished['status']!='authenticated_resource_probe_complete_requires_review' or
        not 0<finished['wall_s']<1500 or not 0<finished['peak_rss_bytes']<6*1024**3):
        raise ValueError('lifecycle/resource limit')
    if result['git_commit']!=expected_commit or result['git_clean_before_after'] is not True:
        raise ValueError('frozen code identity')
    tokens=dict(x.split('=',1) for x in terminal['scontrol'].split() if '=' in x)
    if any(tokens.get(k)!=v for k,v in dict(JobId=str(result['job_id']),JobState='COMPLETED',ExitCode='0:0').items()):
        raise ValueError('actual successful scheduler terminal required')
    before=read('binding-before.json');after=read('binding-after.json')
    if before!=after:raise ValueError('small binding changed')
    # Mac收到的old/base/r20副本路径不同；仅去本地定位字段，声明字节仍逐项核。
    def canonical(value):
        value=json.loads(json.dumps(value))
        for c in value['physical_sources'].values():c.pop('local_path',None)
        return value
    if canonical(before)!=canonical(expected_binding):raise ValueError('external original source binding')
    claims=result['source_claims'];original=before['field_claims']
    roots=[]
    for c,e in zip(claims,original):
        if c['size_bytes']!=e['size_bytes'] or c['sha256']!=e['sha256'] or not c['path'].endswith('/'+e['path']):
            raise ValueError('production field claim')
        roots.append(c['path'][:-len(e['path'])])
    if len(set(roots))!=1 or result['probe']['shape']!=[9632,32,4096]:raise ValueError('production layout')
    live=result['live_before'];live_after=result['live_after']
    stable=lambda x:{k:v for k,v in x.items() if k!='environment_metadata_reads'}
    if stable(live)!=stable(live_after) or live!=read('live-before.json') or live_after!=read('live-after.json'):
        raise ValueError('live proof changed')
    for key in ('live_native_recomputed','trial_mirrored_arrays_bitwise','archive_payload_rehashed'):
        if live[key] is not True:raise ValueError('live prerequisite missing')
    if (live['live_original_code_files']!=801 or live['phase']!=1367 or live['dt']!=889.419892762322 or
        live['radiation_field_bytes_read']!=0 or live['archive_bytes_read']!=before['source_archive']['size_bytes'] or
        live['archive_sha256']!=before['source_archive']['sha256']):raise ValueError('live/archive identity')
    for phase in ('before','after'):
        saved=read('field-hash-'+phase+'.json')
        if saved['sha256']!=result['full_sha256_'+phase] or saved['source_stats']!=result['source_stats_'+phase]:
            raise ValueError('hash stage proof')
    if read('probe.json')!=result['probe']:raise ValueError('probe stage proof')
    allocation=read('allocation.json')
    alloc=dict(x.split('=',1) for x in allocation['scontrol'].split() if '=' in x)
    expected=dict(JobId=str(result['job_id']),JobState='RUNNING',NumCPUs='4',NumTasks='1',NumNodes='1',
                  Partition='Students',QOS='qos_stu_default',TimeLimit='00:30:00')
    if any(alloc.get(k)!=v for k,v in expected.items()) or alloc.get('MinMemoryNode') not in ('16G','16384M'):
        raise ValueError('actual initial allocation')
    answer.update(scheduler_terminal_verified=True,production_resource_preflight_complete=True,
                  archive_bytes_read=2*live['archive_bytes_read'],job_id=result['job_id'],git_commit=expected_commit)
    return answer


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--expected-commit',required=True);p.add_argument('--binding',type=Path,required=True)
    p.add_argument('--terminal',type=Path,required=True);a=p.parse_args()
    result=review_run(a.run,a.expected_commit,json.loads(a.binding.read_text()),json.loads(a.terminal.read_text()))
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
