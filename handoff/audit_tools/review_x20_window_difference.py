"""Independent Decimal reduction of the post-82273 read-only field scan."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from handoff.audit_tools.review_x20_cross_seed_chord import (
    ROOT, digest, read, reduce_independent, same, verify_slabs,
)


def main(job, commit):
    receipt=read(ROOT/f'{job}-window-difference-review.json');archive=ROOT/f'{job}-window-difference-review.tar.gz';out=ROOT/f'x20-window-difference-{job}-received'
    assert archive.stat().st_size==receipt['size_bytes'] and digest(archive)==receipt['sha256']
    out.mkdir(exist_ok=False)
    with tarfile.open(archive) as tar:
        members=tar.getmembers();assert len(members)==len(receipt['files']) and 8<=len(members)<=10
        claims={v['path']:v for v in receipt['files']};assert len(claims)==len(members)
        for m in members:
            assert m.isfile() and m.name in claims and Path(m.name).name==m.name
            b=tar.extractfile(m).read();c=claims[m.name]
            assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
            (out/m.name).write_bytes(b)
    d=read(out/'declaration.json');s=read(out/'summary.json');t=read(out/'scheduler-terminal.json')
    assert t['job_id']==job and t['state']=='COMPLETED' and 'ExitCode=0:0' in t['scontrol'] and t['summary']==s
    assert 'NumCPUs=4' in t['scontrol'] and 'QOS=qos_stu_default' in t['scontrol']
    assert not (out/f'tde-x20-wdiff-{job}.err').read_bytes()
    assert d['job_id']==str(job) and d['source_job']==s['source_job']==82273 and d['shape']==[9632,32,4096]
    audit=Path('handoff/evidence/20260930-x20-82273-final-review.json');old=read(audit)
    assert d['audit_sha256']==digest(audit) and d['archive']==old['archive']
    for p,sha in d['code'].items():assert digest(p)==sha
    assert d['git_commit']==commit
    assert d['maximum_field_scans']==2 and d['maximum_new_maps']==d['maximum_feedback_pairs']==d['new_material_steps']==0 and not d['baseline_replaced']
    source=ROOT/'x20-feedback-82273-complete-received';results={}
    source_archive=ROOT/Path(old['archive']['path']).name
    assert source_archive.stat().st_size==old['archive']['size_bytes'] and digest(source_archive)==old['archive']['sha256']
    # Bind small source manifests to the already audited archive inventory.
    inventory=read(source_archive.with_suffix('').with_suffix('.json'));index={v['path']:v for v in inventory['files']}
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
    result=dict(job_id=job,source_job=82273,receipt=receipt,independent_slab_reduction=True,large_fields_recomputed_on_mac=False,source_code_and_field_claims_verified=True,results=results,peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],new_maps=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    Path(f'handoff/evidence/20260930-x20-window-difference-{job}-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v['total'] for k,v in results.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--commit',required=True);a=p.parse_args();main(a.job,a.commit)
