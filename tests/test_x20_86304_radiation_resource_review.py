"""Entire review_run with explicitly fictional lifecycle and tiled synthetic moments.
No real .dat/native/Slurm, no production main or actual submission ticket.
"""
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from operations import x20_86304_radiation_resource as d
from operations import x20_86304_radiation_contract as c
from handoff.audit_tools import review_x20_86304_radiation_resource as review

def save(p,value): p.write_text(json.dumps(value,allow_nan=False))

def fixture(run):
    repo=Path(__file__).resolve().parents[1]
    binding=c.read(repo/'outputs/review-20260925/20261007-86304-radiation-binding.json')
    hashes=[x['sha256'] for x in c.fields(binding)]
    root='/synthetic/frozen-checkout';runpath=root+'/outputs/hpc/fixture'
    claims=[dict(x,path=root+'/'+x['path']) for x in c.fields(binding)]
    x=np.arange(128,dtype=float).reshape(32,2,2)/8+1
    arrays=[x,.5*x+4,.25*x+6,x+2,.5*(x+2)+4,.25*(x+2)+6]
    row=d.diagonal.slab_statistics(arrays)
    from handoff.audit_tools.exercise_x20_86304_radiation import scalar_oracle
    assert scalar_oracle(arrays,row)==250
    # 首片单元数为128的32768倍；重复铺设的矩线性缩放，极值不变。
    factor=32768
    for matrix in [row['gram']]+[p['moments'] for p in row['pairs']]:
        for key in ('value','absolute'): matrix[key]=[[str(Decimal(v)*factor) for v in vs] for vs in matrix[key]]
    for pair in row['pairs']: pair['reconstruction_error_square']=[str(Decimal(v)*factor) for v in pair['reconstruction_error_square']]
    row['count']*=factor
    peak=100000000;stats=[[1,i,10099884032,2,3] for i in range(6)]
    p=dict(status='resource_probe_complete_requires_review',shape=c.SHAPE,first_group=0,group_count=32,
        source_claims=claims,source_stats_before=stats,source_stats_after=stats,slice_sha256=['a'*64]*6,
        field_bytes_read=402653184,read_seconds_first_pass=[1.0]*6,calculation_seconds=1.0,peak_rss_bytes=peak,slab=row,
        arithmetic=c.ARITHMETIC,full_field_sha_refreshed=False,full_field_statistics_complete=False,
        physical_inference_authorized=False,full_scan_authorized=False,new_maps=0,new_feedback=0,new_material=0,strict_error_bound=False)
    expected=dict(binding=binding,expected_native={'accelerated':{'mirror':'synthetic'},'historical':{'mirror':'synthetic'}},expected_opened_paths=['synthetic/runtime.json'],archives=[{'sha256':'a'*64},{'sha256':'b'*64}],payload_bytes_per_check=1234)
    proof=dict(schema='86304-live-proof-v1',source_job=86304,manifest_sha256=c.document_sha(expected),native=expected['expected_native'],opened_paths=expected['expected_opened_paths'],opened_occurrences=expected['expected_opened_paths'],archive_sha256=['a'*64,'b'*64],authenticated_payload_bytes=1234,trial_all_arrays_bitwise_equal=True,live_native_recomputed=True,radiation_field_bytes_read=0,physical_validation=False,strict_error_bound=False)
    names=sorted(str(p.relative_to(repo)) for directory in ('operations','handoff','scripts','src','hpc','tests') for p in (repo/directory).rglob('*') if p.is_file() and p.suffix in ('.py','.sbatch'))
    code={p:dict(size_bytes=len(raw:= (repo/p).read_bytes()),sha256=hashlib.sha256(raw).hexdigest()) for p in names}
    rows=[]
    for i,name in enumerate(c.ALL_PHASES):
        payload=60599304192 if name.startswith('field-hash-') else 33554432 if name.startswith(('slice-read-','slice-reread-')) else 1234 if name.startswith('source-') else 0
        rows.append(dict(name=name,start_s=float(i),end_s=float(i+1),seconds=1.0,payload_bytes=payload,payload_bytes_per_second=float(payload),cumulative_peak_rss_bytes=peak))
    commit='SYNTHETIC-NOT-A-COMMIT';job='900002'
    result=dict(status=c.STATUS,version=c.SCHEMA,probe=p,source_claims=claims,source_stats_before=stats,source_stats_after=stats,full_sha256_before=hashes,full_sha256_after=hashes,full_hash_seconds_before=1.0,full_hash_seconds_after=1.0,field_bytes_read=121601261568,full_field_sha_refreshed=True,full_field_statistics_complete=False,full_scan_authorized=False,physical_inference_authorized=False,strict_error_bound=False,new_maps=0,new_feedback=0,new_material=0,kernel_calls=1,source_job=86304,global_h1=None,labels=['AP','AF','AM','HP','HF','HM'],phases=rows,git_commit=commit,git_clean_before_after=True,job_id=job,peak_rss_bytes=peak,source_before=proof,source_after=proof,archive_bytes_read=915885482,source_payload_bytes=2468,code_bytes_read=2*sum(x['size_bytes'] for x in code.values()),synthetic=True)
    script=root+'/operations/x20_86304_radiation_resource.sbatch'
    tail=f' Command={script} WorkDir={root} SubmitTime=synthetic-time'
    terminal=dict(job_id=job,observed_unix=140.0,synthetic=True,scontrol=f'JobId={job} JobState=COMPLETED ExitCode=0:0'+tail)
    allocation=dict(job_id=job,observed_unix=101.0,synthetic=True,scontrol=f'JobId={job} JobState=RUNNING NumCPUs=4 NumTasks=1 NumNodes=1 Partition=Students QOS=qos_stu_default TimeLimit=00:30:00 MinMemoryNode=16G'+tail)
    ticket=dict(job_id=job,expected_commit=commit,run=runpath,workdir=root,sbatch_file=script,sbatch_fingerprint=code['operations/x20_86304_radiation_resource.sbatch'],code_content_sha256=c.document_sha(code),binding_content_sha256=c.document_sha(expected),digest_encoding='json-ascii-compact-insertion-order-v1',argv=['sbatch','--parsable',script],stdout=job+'\n',returncode=0,request_unix=90.0,returned_unix=99.0,submit_time='synthetic-time',exports=dict(RADIATION_EXPECTED_COMMIT=commit,RADIATION_RUN=runpath,RADIATION_SOURCES='/synthetic/sources',RADIATION_CODE_FREEZE='/synthetic/code'),synthetic=True)
    started=dict(status='incomplete',version=c.SCHEMA,started_unix=100.0,program_seconds=1500,rss_limit_bytes=6442450944,execution=dict(job_id=job,workdir=root,run=runpath,driver=root+'/operations/x20_86304_radiation_resource.py'),arguments={key:ticket['exports']['RADIATION_'+key.upper()] for key in ('expected_commit','run','sources','code_freeze')})
    identity=dict(checkout=root,modules={p:dict(relative_path=p,file=root+'/'+p,origin=root+'/'+p,fingerprint=code[p]) for p in c.IDENTITY_REQUIRED+[c.PREFIX+'live.py']},errstate=c.ERRSTATE,environment=dict(executable=root+'/.venv/python',python_version='synthetic',numpy_file=root+'/.venv/numpy.py',numpy_origin=root+'/.venv/numpy.py',numpy_version='2.5.2'))
    files={'result.json':result,'probe.json':p,'started.json':started,'allocation.json':allocation,'scheduler-terminal.json':terminal,'batch-exit.json':dict(job_id=job,child_exit_status=0,recorded_unix=135.0,synthetic=True),'finished.json':dict(status=c.STATUS,wall_s=30.0,peak_rss_bytes=peak,scheduler_terminal_verified=False,full_scan_authorized=False)}
    for side in ('before','after'):
        files['source-'+side+'.json']=proof;files['identity-'+side+'.json']=identity;files['code-'+side+'.json']=code
        files['field-hash-'+side+'.json']=dict(sha256=hashes,source_stats=stats,seconds=1.0)
    files.update({f'phase-{i:02d}.json':v for i,v in enumerate(rows,1)})
    for name,value in files.items():save(run/name,value)
    return run,commit,code,expected,terminal,job,ticket

@pytest.fixture
def evidence(tmp_path):return fixture(tmp_path)

def test_full_review(evidence):
    answer=review.review_run(*evidence)
    assert answer['review_complete'] and answer['synthetic_evidence'] and not answer['production_resource_preflight_complete'] and answer['execution_job']=='900002'
    assert answer['global_h1'] is None and not answer['full_field_statistics_complete']

@pytest.mark.parametrize('fault',['native','runtime','source_digest','archive','nativeflag','boolzero','promotion'])
def test_both_sides_wrong(evidence,fault):
    run=evidence[0];result=c.read(run/'result.json');proof=result['source_before']
    if fault=='native':proof['native']['accelerated']['mirror']='wrong'
    elif fault=='runtime':proof['opened_paths']=[]
    elif fault=='source_digest':proof['manifest_sha256']='0'*64
    elif fault=='archive':proof['archive_sha256'][0]='0'*64
    elif fault=='nativeflag':proof['live_native_recomputed']=False
    elif fault=='boolzero':proof['radiation_field_bytes_read']=False
    else:proof['physical_validation']=True
    result['source_after']=copy.deepcopy(proof)
    for side in ('before','after'):save(run/f'source-{side}.json',proof)
    save(run/'result.json',result)
    with pytest.raises(ValueError):review.review_run(*evidence)

@pytest.mark.parametrize('fault',['oldjob','oldsource','shape','calls','square_missing','origin','ticket_sha','ticket_run','ticket_time','phase_missing','rss','partial','bool_source'])
def test_end_to_end_refusal(evidence,fault):
    args=list(evidence);run=args[0];result=c.read(run/'result.json')
    if fault=='oldjob':args[5]='86304'
    elif fault=='oldsource':result['source_job']=85889
    elif fault=='bool_source':result['source_job']=True
    elif fault=='shape':result['probe']['shape']=[32,32,4096]
    elif fault=='calls':result['kernel_calls']=2
    elif fault=='phase_missing':result['phases'].pop()
    elif fault=='rss':result['peak_rss_bytes']=6442450944
    elif fault=='partial':save(run/'failure.json',{})
    elif fault=='square_missing':
        args[2]=copy.deepcopy(args[2]);args[2].pop('operations/x20_85889_chord_scan_square.py')
        for side in ('before','after'):save(run/f'code-{side}.json',args[2])
    elif fault=='origin':
        for side in ('before','after'):
            p=run/f'identity-{side}.json';identity=c.read(p);identity['modules'][c.KERNEL]['origin']='/wrong/kernel.py';save(p,identity)
    else:
        args[6]=copy.deepcopy(args[6]);key={'ticket_sha':'code_content_sha256','ticket_run':'run','ticket_time':'returned_unix'}[fault]
        args[6][key]=-1 if fault=='ticket_time' else 'wrong'
    save(run/'result.json',result)
    with pytest.raises(ValueError):review.review_run(*args)
