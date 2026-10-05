"""Independent 85856 source binding and 80-digit small-statistic reduction."""
import hashlib,json,subprocess,tarfile
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_window_basis import reduce_rows,minimum
from handoff.audit_tools.review_x20_matched_proposal import boundary
from handoff.audit_tools.review_x20_83080_quarter import local as old_local,ROOT,read,digest

JOB=85856
COMMIT='37cdd3d236ed0fe1baeeda39d59d6f049e243f19'
ORDER=((85821,16),(85821,8),(84026,16),(82989,16))
FOLDERS={84026:'x20-83514-feedback-84026-received',82989:'x20-historical-seed-feedback-82989-received',85821:'x20-85800-feedback-85821-received'}

def local(path):
    for run,folder in [('x20-85800-seed-feedback-20261006',FOLDERS[85821]),('x20-85778-true-validation-20261006','x20-85778-true-85800-received'),('x20-85744-boundary-prediction-20261005','x20-boundary-prediction-85778-received'),('x20-83514-seed-feedback-20261002',FOLDERS[84026]),('x20-83111-half-prediction-20261002','x20-half-prediction-83131-received'),('x20-83131-true-validation-20261002','x20-83131-true-83514-received')]:
        prefix='outputs/hpc/'+run+'/'
        if path.startswith(prefix):
            rel=path[len(prefix):]
            return ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/folder/rel
    return old_local(path)

def terminal_check(t,b,s):
    assert t['job_id']==JOB and t['state']=='COMPLETED' and t['summary']==s
    for token in ('JobId=85856','JobState=COMPLETED','ExitCode=0:0','NumCPUs=4','QOS=qos_stu_default','TimeLimit=01:00:00','MinMemoryNode=16G'):
        assert token in t['scontrol'].split()
    assert b['job_id']==str(JOB) and b['child_exit_status']==0 and b['scheduler_terminal_verified'] is False
    assert t['batch_exit']==b

def source_fields():
    fields=[]
    for job,n in ORDER:
        m=read(ROOT/FOLDERS[job]/f'historical/endpoints-map{n:02d}/manifest.json')
        r0,r1=m['history_rows'];e=m['endpoints']
        assert [r0['iteration'],r1['iteration']]==[n-1,n]
        assert r0['input_sha256']==e['previous']['sha256']
        assert r0['output_sha256']==r1['input_sha256']==e['final']['sha256']
        fields.extend(e[k] for k in ('previous','final'))
    return fields

AUDITS={85821:'20261006-x20-85821-final-review.json',84026:'20261005-x20-84026-final-review.json',82989:'20261001-x20-82989-final-review.json'}
RUNS={85821:'x20-85800-seed-feedback-20261006',84026:'x20-83514-seed-feedback-20261002',82989:'x20-historical-seed-feedback-20261001'}

def field_stats_check(d,s):
    before=d['field_stats_before'];after=s['field_stats_after']
    assert d['git_clean'] is True and s['all_hashes_verified_before_after'] is True
    assert before==after and len(before)==8 and len({v['path'] for v in before})==8
    for c,v in zip(d['fields'],before):
        assert set(v)=={'path','inode','size_bytes','mtime_ns'}
        assert v['path']==c['path'] and v['size_bytes']==c['size_bytes']==10099884032
        assert type(v['inode']) is int and v['inode']>0 and type(v['mtime_ns']) is int and v['mtime_ns']>0

def audit_identity(a,job):
    assert a['job_id']==job and a['completed_experiment'] and a['independent_vector_reduction']
    assert a['all_original_zero_gates_passed'] and a['new_material_steps']==0 and a['accepted_outer_steps']==20
    assert a['baseline_replaced'] is False and a['reference_calibration_eligible'] is False
    assert a['map_counts']=={'historical':16} and a['map_process_receipts']==1216 and a['feedback_process_receipts']==304
    if job==85821:
        assert a['numerical_commit']=='16ad4d6fabdec1e9e958d7168ead0828f25792c7'
        assert a['numerical_artifacts_complete'] and a['child_exit_status']==0
        assert a['scheduler_terminal_verified'] is True and a['scheduler_terminal_state']=='COMPLETED'
        assert a['source_84026_scheduler_terminal_verified'] is False
    if job==84026:
        assert a['numerical_artifacts_complete'] and a['scheduler_terminal_verified'] is False
        assert a['scheduler_terminal_state'] is None

def source_identity_check(d):
    known={c['path']:c for c in d['source_claims']};configs=[];trials=[];verified={}
    for job in (85821,84026,82989):
        ap=Path('handoff/evidence')/AUDITS[job];a=read(ap);audit_identity(a,job)
        arc=ROOT/Path(a['archive']['path']).name
        assert arc.stat().st_size==a['archive']['size_bytes'] and digest(arc)==a['archive']['sha256']
        assert a['archive']==known[a['archive']['path']]
        names=['declaration.json','summary.json','historical/config.json','historical/trial_material.npz']
        for j,n in ORDER:
            if j==job:names += [f'historical/endpoints-map{n:02d}/manifest.json']+[f'historical/pair{n:02d}/{e}_feedback.npz' for e in ('previous','final')]
        with tarfile.open(arc) as tar:
            ix={c['path']:c for c in json.load(tar.extractfile('ARCHIVE_MANIFEST.json'))['files']}
            for name in names:
                b=tar.extractfile(name).read();assert len(b)==ix[name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[name]['sha256']
                assert b==(ROOT/FOLDERS[job]/name).read_bytes()
                c=known['outputs/hpc/'+RUNS[job]+'/'+name]
                assert c['size_bytes']==len(b) and c['sha256']==ix[name]['sha256']
        if job!=84026:
            tp=Path('handoff/evidence')/('20261006-x20-85821-terminal.json' if job==85821 else '20261001-x20-82989-terminal.json')
            st=read(tp)
            assert st['job_id']==job and st['state']=='COMPLETED'
            assert all(v in st['scontrol'].split() for v in (f'JobId={job}','JobState=COMPLETED','ExitCode=0:0'))
        sd=read(ROOT/FOLDERS[job]/'declaration.json')
        if job==85821:assert sd['environment']['git_commit']==a['numerical_commit']
        configs.append(read(ROOT/FOLDERS[job]/'historical/config.json'))
        with np.load(ROOT/FOLDERS[job]/'historical/trial_material.npz',allow_pickle=False) as z:trials.append({k:z[k] for k in z.files})
        verified[str(job)]=dict(archive=a['archive'],selected_files=len(names),scheduler_terminal_verified=job!=84026)
    for cfg,t in zip(configs,trials):
        assert {k:v for k,v in cfg.items() if k not in ('run','warm_seed','sources')}=={k:v for k,v in configs[0].items() if k not in ('run','warm_seed','sources')}
        assert cfg['shape']==[9632,32,4096] and set(t)==set(trials[0])
        assert all(np.array_equal(t[k],trials[0][k]) for k in t)
        assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    return verified


def run():
    receipt=read(ROOT/f'{JOB}-current-basis-review.json');arc=ROOT/f'{JOB}-current-basis-review.tar.gz'
    assert arc.stat().st_size==receipt['size_bytes'] and digest(arc)==receipt['sha256']
    out=ROOT/f'x20-current-basis-{JOB}-received';out.mkdir(exist_ok=False)
    ix={r['path']:r for r in receipt['files']}
    assert len(ix)==len(receipt['files'])==9
    assert set(ix)=={'declaration.json','basis.json','summary.json','status.json','batch-exit.json','scheduler-terminal.json','execution-terminal.json','stdout.log','stderr.log'}
    with tarfile.open(arc) as tar:
        members=tar.getmembers();assert len(members)==len(ix)
        assert len({m.name for m in members})==len(ix)
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in ix
            b=tar.extractfile(m).read();assert len(b)==ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d,p,s,t=[read(out/(n+'.json')) for n in ('declaration','basis','summary','scheduler-terminal')]
    assert d['job_id']==str(JOB) and d['git_commit']==COMMIT
    assert d['source_job']==85821 and d['source_jobs']==[85821,84026,82989] and d['source_scheduler_terminal_verified'] is True
    assert d['source_84026_scheduler_terminal_verified'] is False
    identities=source_identity_check(d)
    field_stats_check(d,s)
    terminal_check(t,read(out/'batch-exit.json'),s)
    assert read(out/'execution-terminal.json')==t and not (out/'stderr.log').read_bytes()
    for c in d['code']:
        b=subprocess.check_output(['git','show',COMMIT+':'+c['path']]);assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
    for c in d['source_claims']:
        f=local(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],c['path']
    assert d['fields']==source_fields() and d['shape']==[9632,32,4096]
    assert d['field_order']==[f'{j}H{n}_{e}' for j,n in ORDER for e in ('previous','final')]
    assert d['basis_order']==['r_85821H16','r_85821H8-r_85821H16','r_84026H16-r_85821H16','r_82989H16-r_85821H16']
    assert all(c['size_bytes']==10099884032 for c in d['fields']) and p['all_eight_sha256_verified']
    # 85821 -> 85800 -> 85778与原几何，而不是旧83514/83131链。
    sd=read(ROOT/FOLDERS[85821]/'declaration.json')
    vp='outputs/hpc/x20-85778-true-validation-20261006/declaration.json'
    gp='outputs/hpc/x20-85744-boundary-prediction-20261005/declaration.json'
    vd=read(local(vp))
    assert next(c for c in d['source_claims'] if c['path']==vp) in sd['claims']
    assert next(c for c in d['source_claims'] if c['path']==gp) in vd['claims']
    assert d['geometry'] in vd['claims'] and d['geometry']==read(local(gp))['geometry']
    g,f=reduce_rows(p['slabs'])
    for other in (p['gram'],s['gram']):np.testing.assert_allclose(g,other,rtol=3e-12,atol=0)
    peaks=[max(r['basis_linf'][i] for r in p['slabs']) for i in range(4)]
    mins=[min(r['field_minima'][i] for r in p['slabs']) for i in range(8)]
    assert peaks==p['basis_linf'] and mins==p['field_minima'] and f.shape==(8,9632) and s['slabs']==301
    with localcontext() as ctx:
        ctx.prec=80;D=lambda x:Decimal.from_float(float(x))
        wide=[[str(sum((D(r['gram'][i][j]) for r in p['slabs']),Decimal(0))) for j in range(4)] for i in range(4)]
        flux_totals=[str(sum((D(v) for v in row),Decimal(0))) for row in f]
    for z in (d,s):
        assert all(z[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) and not z['baseline_replaced'] and not z['strict_error_bound'] and not z['candidate_written']
    assert not p['candidate_written'] and d['maximum_statistic_scans']==1 and d['longdouble_mantissa_bits']>=52
    assert s['status']==read(out/'status.json')['status']=='basis_complete_requires_review'
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    try:diagnostic=minimum(g)
    except ValueError as exc:diagnostic=dict(matrix_failure=str(exc),directions_removed=False,regularization_applied=False)
    result=dict(job_id=JOB,commit=COMMIT,receipt=receipt,independent_audit=True,scheduler_terminal_verified=True,
        source_85821_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,source_archive_bindings=identities,field_stats_verified=True,git_clean_verified=True,code_claims_verified=len(d['code']),source_claims_verified=len(d['source_claims']),
        gram=g,gram_80digit=wide,unconstrained_diagnostic=diagnostic,boundary_flux_totals_80digit=flux_totals,
        boundary_metrics=[boundary(f[i],f[i+1]) for i in range(0,8,2)],fields=d['fields'],basis_linf=peaks,field_minima=mins,
        slabs=301,peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],large_fields_recomputed_on_mac=False,
        strict_rounding_error_bound=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    with Path('handoff/evidence/20261006-x20-current-basis-85856-review.json').open('x') as o:json.dump(result,o,indent=2,allow_nan=False);o.write('\n')
    print(json.dumps({k:result[k] for k in ('job_id','unconstrained_diagnostic','code_claims_verified','source_claims_verified')},indent=2))

if __name__=='__main__':run()
