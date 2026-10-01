"""Exact sign audit of the full and half negative points in the two rejected 83063 slabs; never changes a field."""
import argparse,json,math,os,resource,signal,subprocess,time
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import basis_fields


def exact_sign(values, coefficients):
    if len(values)!=4 or len(coefficients)!=3 or not all(math.isfinite(v) for v in list(values)+list(coefficients)):
        raise ValueError('four finite fields and three coefficients required')
    # 将已存 binary64 当作精确有理数；检查符号，不裁剪或改变强度。
    v=list(map(F,values));c=list(map(F,coefficients))
    full=v[0]+sum((x*(y-v[0]) for x,y in zip(c,v[1:])),F(0))
    half=(v[0]+full)/2
    def record(x):
        denominator=x.denominator
        assert denominator & (denominator-1)==0
        return dict(sign=int(x>0)-int(x<0),numerator=str(x.numerator),denominator_power_of_two=denominator.bit_length()-1,rounded_binary64_hex=float(x).hex())
    return dict(full=record(full),half=record(half))


def upper_fraction(values,coefficients):
    """Exact local bound along the original full direction; not a global certificate."""
    v=list(map(F,values));c=list(map(F,coefficients))
    if any(x<0 for x in v):raise ValueError('source field is negative')
    delta=sum((x*(y-v[0]) for x,y in zip(c,v[1:])),F(0))
    if delta>=0:return None
    t=v[0]/(-delta)
    return dict(numerator=str(t.numerator),denominator=str(t.denominator),float=float(t))


def audit_slab(aa,c,start,max_unique=4096):
    q,p=basis_fields(aa,c);rows=[]
    for name,z,ix in [('input',q,(0,2,4,6)),('predicted_output',p,(1,3,5,7)),
                       ('half_input',.5*aa[0]+.5*q,(0,2,4,6)),('half_predicted_output',.5*aa[1]+.5*p,(1,3,5,7))]:
        flat=np.flatnonzero(z.ravel()<0)
        if not len(flat):continue
        values=np.column_stack([aa[i].ravel()[flat] for i in ix])
        unique,first,counts=np.unique(values,axis=0,return_index=True,return_counts=True)
        if len(unique)>max_unique:raise RuntimeError('unique exact-check budget exceeded')
        cases=[]
        for j,(v,k,n) in enumerate(zip(unique,first,counts)):
            if j%32==0 and shared.STOP:raise InterruptedError('stop before exact tuple')
            local=np.unravel_index(int(flat[k]),z.shape)
            cases.append(dict(source_hex=[float(x).hex() for x in v],count=int(n),
                first_index=[start+int(local[0]),int(local[1]),int(local[2])],
                observed_binary64_hex=float(z.ravel()[flat[k]]).hex(),
                full_direction_upper_fraction=upper_fraction(v.tolist(),c),**exact_sign(v.tolist(),c)))
        rows.append(dict(kind=name,negative_count=len(flat),unique_count=len(unique),
            minimum_observed_hex=float(z.min()).hex(),cases=cases,
            exact_full_sign_counts={str(s):sum(v['count'] for v in cases if v['full']['sign']==s) for s in (-1,0,1)},
            exact_half_sign_counts={str(s):sum(v['count'] for v in cases if v['half']['sign']==s) for s in (-1,0,1)}))
    return rows


def run(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def stop():
        if shared.STOP:raise InterruptedError('stop requested')
    mark('preflight')
    try:
        ap=Path('handoff/evidence/20261001-x20-historical-heating-prediction-83063-review.json');a=shared.read(ap)
        assert a['job_id']==83063 and a['independent_slab_reduction'] and a['source_and_code_verified']
        assert a['result']['checks']==dict(full_field_nonnegative=False)
        source=Path('outputs/hpc/x20-82989-heating-prediction-20261001');d=shared.read(source/'declaration.json');p=shared.read(source/'prediction.json')
        ix={r['path']:r for r in a['receipt']['files']}
        for name in ('declaration.json','prediction.json','summary.json','status.json'):
            assert shared.digest(source/name)==ix[name]['sha256'] and (source/name).stat().st_size==ix[name]['size_bytes']
        assert d['global_coefficients']==[0.,-7.2,3.7942299325052176] and d['shape']==[9632,32,4096]
        targets=[r for r in p['slabs'] if min(r['minima'])<0]
        assert [r['first_group'] for r in targets]==[9440,9472]
        fields=d['fields'];paths=[Path(c['path']) for c in fields];before=[v.stat() for v in paths]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/x) for x in ('operations/x20_83063_subnormal_audit.py','operations/x20_83063_subnormal_audit.sbatch','operations/x20_window_fields.py','tests/test_x20_83063_subnormal_audit.py','handoff/protocols/x20-83063-subnormal-audit-v1.md')]
        small=[core.pipeline.claim(v) for v in (ap,source/'declaration.json',source/'prediction.json')]
        core.reused.verify(fields+small+code);stop()
        shared.write(out/'declaration.json',dict(source_job=83063,source_claims=small,code=code,fields=fields,coefficients=d['global_coefficients'],shape=d['shape'],targets=[9440,9472],maximum_unique_tuples_per_slab_kind=4096,
            job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),new_maps=0,new_feedback_pairs=0,new_material_steps=0,field_written=False,baseline_replaced=False))
        results=[]
        for row in targets:
            stop();start=row['first_group'];mark('checking',first_group=start)
            aa=[np.array(np.memmap(v,mode='r',dtype=np.float64,shape=tuple(d['shape']))[start:start+32]) for v in paths]
            q,pp=basis_fields(aa,d['global_coefficients']);x,y=aa[:2]
            minima=[float(z.min()) for z in (q,pp,.5*x+.5*q,.5*y+.5*pp)]
            assert minima==row['minima']
            results.append(dict(first_group=start,group_count=32,minima_hex=[v.hex() for v in minima],checks=audit_slab(aa,d['global_coefficients'],start)))
            del aa,q,pp,x,y
        core.reused.verify(fields+small+code)
        for path,b in zip(paths,before):
            now=path.stat();assert (now.st_ino,now.st_size,now.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('RSS guard')
        shared.write(out/'exact-signs.json',dict(slabs=results,scope='all stored-negative points separately for full and half, input and predicted output; overlapping kind counts are not unique point counts; no zero-point or full-domain exact sign certificate'))
        shared.write(out/'summary.json',dict(status='exact_sign_audit_complete_requires_review',wall_s=time.monotonic()-started,peak_rss_bytes=peak,new_maps=0,new_feedback_pairs=0,new_material_steps=0,field_written=False,baseline_replaced=False))
        mark('exact_sign_audit_complete_requires_review')
    except BaseException as exc:mark('stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc));raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);run(p.parse_args().run)
