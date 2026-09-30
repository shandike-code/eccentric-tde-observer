"""Independent Decimal slab/block reduction of the immutable 82039 scan receipt."""
from decimal import Decimal,localcontext
import hashlib,json,math,tarfile
from pathlib import Path

ROOT=Path('outputs/review-20260925')


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())


def reduce_independent(rows):
    if not rows:raise ValueError('empty reduction')
    if any(not math.isfinite(r[k]) for r in rows for k in ('dd','de','ee','difference_linf','change_linf')):raise ValueError('nonfinite moments')
    if any(r['dd']<0 or r['ee']<0 or r['difference_linf']<0 or r['change_linf']<0 for r in rows):raise ValueError('negative squared norm')
    with localcontext() as c:
        c.prec=70
        dd,de,ee=[sum((Decimal.from_float(float(r[k])) for r in rows),Decimal(0)) for k in ('dd','de','ee')]
        if de*de>dd*ee*(1+Decimal('1e-12')):raise ValueError('Cauchy inequality failed')
        r=dict(dd=float(dd),de=float(de),ee=float(ee),zero_difference=dd==0)
        if dd==0:return dict(**r,relative_change_l2=None,rayleigh_action=None)
        return dict(**r,relative_change_l2=float((ee/dd).sqrt()),rayleigh_action=float(1+de/dd),mapped_difference_l2_ratio=float(((dd+2*de+ee)/dd).sqrt()),difference_linf=max(z['difference_linf'] for z in rows),change_linf=max(z['change_linf'] for z in rows),spectral_radius_established=False,strict_error_bound=False)


def same(a,b):
    assert set(a)==set(b)
    for k,v in a.items():
        if isinstance(v,bool) or v is None:assert b[k] is v
        else:assert math.isclose(v,b[k],rel_tol=3e-12,abs_tol=1e-30),(k,v,b[k])


def verify_slabs(rows):
    assert len(rows)==301
    for j,r in enumerate(rows):assert (r['first_group'],r['group_count'],r['block'])==(32*j,32,j//4)
    assert sum(r['group_count'] for r in rows)==9632


def main():
    receipt=read(ROOT/'82039-review-20260930.json');archive=ROOT/'82039-review-20260930.tar.gz';out=ROOT/'x20-chord-82039-received'
    assert archive.stat().st_size==receipt['size_bytes'] and digest(archive)==receipt['sha256']
    out.mkdir(exist_ok=False)
    with tarfile.open(archive) as tar:
        members=tar.getmembers();assert len(members)==len(receipt['files'])==9
        claims={v['path']:v for v in receipt['files']};assert len(claims)==9
        for m in members:
            assert m.isfile() and m.name in claims and Path(m.name).name==m.name
            b=tar.extractfile(m).read();c=claims[m.name]
            assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
            (out/m.name).write_bytes(b)
    d=read(out/'declaration.json');s=read(out/'summary.json');t=read(out/'scheduler-terminal.json')
    assert t['job_id']==82039 and t['state']=='COMPLETED' and 'ExitCode=0:0' in t['scontrol'] and t['summary']==s
    assert 'NumCPUs=4' in t['scontrol'] and 'QOS=qos_stu_default' in t['scontrol']
    assert not (out/'tde-x20-chord-82039.err').read_bytes()
    assert d['job_id']=='82039' and d['source_job']==s['source_job']==81769 and d['shape']==[9632,32,4096]
    audit=Path('handoff/evidence/20260930-x20-81769-final-review.json');old=read(audit)
    assert d['audit_sha256']==digest(audit) and d['archive']==old['archive']
    for p,sha in d['code'].items():assert digest(p)==sha
    assert d['git_commit']=='cb9b040e5494848ed4d693397dc6b0f8de35f425'
    assert d['maximum_field_scans']==2 and d['maximum_new_maps']==d['maximum_feedback_pairs']==d['new_material_steps']==0 and not d['baseline_replaced']
    source=ROOT/'x20-feedback-81769-complete-received';results={}
    source_archive=ROOT/Path(old['archive']['path']).name
    assert source_archive.stat().st_size==old['archive']['size_bytes'] and digest(source_archive)==old['archive']['sha256']
    # Bind small source manifests to the already audited archive inventory.
    inventory=read(ROOT/'complete-1790746035725169062.json');index={v['path']:v for v in inventory['files']}
    for n in (8,16):
        fields=[]
        for name in ('accelerated','historical'):
            rel=f'{name}/endpoints-map{n:02d}/manifest.json';assert digest(source/rel)==index[rel]['sha256']
            with tarfile.open(source_archive) as tar:
                assert hashlib.sha256(tar.extractfile(rel).read()).hexdigest()==digest(source/rel)
            m=read(source/rel);fields.extend(m['endpoints'][e] for e in ('final','mapped_final'))
        assert d['fields'][str(n)]==fields
        r=read(out/f'checkpoint{n:02d}.json');assert r['all_field_sha256_verified'] is True
        rows=r['slabs'];verify_slabs(rows);total=reduce_independent(rows);same(total,r['total']);same(total,s['results'][str(n)])
        assert set(r['blocks'])=={str(i) for i in range(76)}
        for i in range(76):same(reduce_independent([z for z in rows if z['block']==i]),r['blocks'][str(i)])
        results[str(n)]=dict(total=total,blocks=r['blocks'],slab_count=len(rows))
    assert s['status']==read(out/'status.json')['status']=='scan_complete_requires_review'
    assert s['new_maps']==s['new_feedback_pairs']==s['new_material_steps']==0
    assert s['baseline_replaced'] is False and s['strict_error_bound'] is False and 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    result=dict(job_id=82039,source_job=81769,receipt=receipt,independent_slab_reduction=True,large_fields_recomputed_on_mac=False,source_code_and_field_claims_verified=True,results=results,peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],new_maps=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    Path('handoff/evidence/20260930-x20-82039-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v['total'] for k,v in results.items()},indent=2))


if __name__=='__main__':main()
