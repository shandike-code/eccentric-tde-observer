"""Read-only per-frequency verification of the two saved 79296 population local fields."""
import json,hashlib,math,os,resource,sys,time,tarfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/hpc/step21-late-population-pilot-20260928'
OUT=ROOT/'outputs/hpc/step21-late-population-array-audit-20260928'
SHAPE=(9632,32,4096)

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def claim(p):
    return dict(path=str(p.relative_to(ROOT)),size_bytes=p.stat().st_size,sha256=digest(p))

def verify(c):
    p=ROOT/c['path']
    if p.stat().st_size!=c['size_bytes'] or digest(p)!=c['sha256']:raise RuntimeError('source changed: '+str(p))

def write(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')

def frequency_stats(a,b):
    if a.shape!=b.shape or a.ndim!=2 or not np.isfinite(a).all() or not np.isfinite(b).all() or min(a.min(),b.min())<0:
        raise ValueError('invalid field slice')
    delta=(b-a).astype(np.longdouble)
    return dict(square=float(np.sum(delta*delta,dtype=np.longdouble)),maximum=float(np.max(np.abs(delta))),minimum_input=float(a.min()),minimum_output=float(b.min()))

def check_population_source(d):
    if (d.get('source_job_id')!=79151 or d.get('refreshed_halo') is not True
            or d.get('source_run')!='outputs/hpc/step21-late-direction-windows-20260928'
            or d.get('frozen_material_case')!='population' or d.get('material_relaxation')!=1/256
            or d.get('original_r20_unchanged') is not True or d.get('physical_dt_unchanged') is not True
            or set(d.get('cases',{}))!={'population'} or d.get('blocks')!=[37,44]):
        raise RuntimeError('requires the frozen 79151 population source')
    case=d['cases']['population']
    expected=('a6addd2bd50f55ebc222bfbcc4d992f8c34d518ddc96e65f1b37b3e074a41151',
              'b37287a5418eb6c34bb8cd1e83f2509f630ca69d9b3f27fa39c962a2ecdc3c8a')
    if tuple(case[k]['sha256'] for k in ('input','output'))!=expected or d['source_pair']!=[case['input'],case['output']]:
        raise RuntimeError('wrong actual population map pair')


def main():
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<4:raise RuntimeError('requires four-core allocation')
    OUT.mkdir(exist_ok=False);start=time.monotonic()
    d=json.loads((SOURCE/'declaration.json').read_text());s=json.loads((SOURCE/'summary.json').read_text())
    check_population_source(d)
    audit=json.loads((ROOT/'handoff/evidence/20260928-late-population-metadata-review.json').read_text())
    if audit['job_id']!=79296 or audit['frozen_material_case']!='population' or not audit['all_local_cases_passed'] or d['core_intervals']!=[[4352,5248],[5248,6144]]:raise RuntimeError('unreviewed source')
    archive_claim=audit['archive'];verify(archive_claim)
    with tarfile.open(ROOT/archive_claim['path']) as t:
        inventory={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    for name in ('declaration.json','summary.json'):
        c=inventory[name]
        if digest(SOURCE/name)!=c['sha256'] or (SOURCE/name).stat().st_size!=c['size_bytes']:raise RuntimeError('not audited source')
    case=d['cases']['population']
    claims=[case[k] for k in ('input','output','config','trial','state')]+[r['local_arrays'] for r in s['rows']]
    claims+=[archive_claim]
    claims+=[claim(SOURCE/n) for n in ('declaration.json','summary.json')]
    claims+=[claim(ROOT/'handoff/evidence/20260928-late-population-metadata-review.json')]
    code=[claim(Path(__file__)),claim(ROOT/'operations/scan_late_population_arrays.sbatch'),claim(ROOT/'tests/test_late_population_array_scan.py'),claim(ROOT/'handoff/protocols/step21-late-population-array-audit-v1.md')]
    for c in claims+code:verify(c)
    write(OUT/'declaration.json',dict(claims=claims,code=code,source=str(SOURCE.relative_to(ROOT)),job_id=os.environ['SLURM_JOB_ID'],source_job_id=79296,frozen_material_case='population',maximum_frequency_rows=1792,source_data_passes=1,maximum_wall_s=1800,new_maps=0,new_feedback=0,new_material_steps=0,strict_error_bound=False))
    x=np.memmap(ROOT/case['input']['path'],mode='r',dtype='<f8',shape=SHAPE)
    y=np.memmap(ROOT/case['output']['path'],mode='r',dtype='<f8',shape=SHAPE)
    results=[]
    for r in s['rows']:
        lo,hi=r['core_groups']
        with np.load(ROOT/r['local_arrays']['path'],allow_pickle=False) as z:
            if set(z.files)!={'candidate','mapped_candidate'}:raise ValueError('array schema')
            a=z['candidate'];b=z['mapped_candidate']
        if a.shape!=b.shape or a.shape!=(896,32,4096):raise ValueError('local shape')
        rows=[dict(group=j,raw=frequency_stats(x[j],y[j]),fresh=frequency_stats(a[j-lo],b[j-lo])) for j in range(lo,hi)]
        norms={k:dict(l2=math.sqrt(math.fsum(v[k]['square'] for v in rows)),linf=max(v[k]['maximum'] for v in rows)) for k in ('raw','fresh')}
        for k in ('raw','fresh'):
            for n in ('l2','linf'):
                if not np.isclose(norms[k][n],r[k+'_defect_'+n],rtol=2e-11,atol=0):raise RuntimeError('raw-array norm mismatch')
        result=dict(block=r['block_index'],core=[lo,hi],rows=rows,norms=norms,local_arrays=r['local_arrays'])
        write(OUT/f"block{r['block_index']}.json",result);results.append({k:v for k,v in result.items() if k!='rows'})
        del a,b
    del x,y
    for c in claims+code:verify(c)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    if peak>=8*1024**3:raise RuntimeError('8 GiB audit memory guard exceeded')
    write(OUT/'summary.json',dict(status='complete_requires_mac_reduction',results=results,peak_rss_bytes=peak,wall_s=time.monotonic()-start,new_maps=0,new_feedback=0,new_material_steps=0,operator_recomputed=False,half_operator_recomputed=False,source_unchanged=True))
    print(json.dumps({'status':'complete_requires_mac_reduction','wall_s':time.monotonic()-start,'peak_rss_bytes':peak}))

if __name__=='__main__':main()
