"""Audit current endpoint basis independently; candidate selection is separate."""
import argparse,hashlib,json,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT,digest,read
from handoff.audit_tools.review_x20_window_basis import reduce_rows,close
from handoff.audit_tools.review_x20_matched_proposal import boundary


def main(job, commit):
    receipt=read(ROOT/f'{job}-latest-basis-review.json');arc=ROOT/f'{job}-latest-basis-review.tar.gz'
    assert arc.stat().st_size==receipt['size_bytes'] and digest(arc)==receipt['sha256']
    out=ROOT/f'x20-latest-basis-{job}-received';out.mkdir(exist_ok=False)
    with tarfile.open(arc) as tar:
        index={r['path']:r for r in receipt['files']};members=tar.getmembers()
        assert len(index)==len(members)==8
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in index
            b=tar.extractfile(m).read();c=index[m.name]
            assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
            (out/m.name).write_bytes(b)
    d=read(out/'declaration.json');s=read(out/'summary.json');p=read(out/'basis.json');t=read(out/'scheduler-terminal.json')
    assert d['job_id']==str(job) and d['source_jobs']==[82273,82396] and d['shape']==[9632,32,4096]
    assert d['git_commit']==commit
    assert d['field_order']==['A16','T_A16','H16','T_H16','A8','T_A8','H8','T_H8']
    assert d['basis_order']==['r_A16','r_H16-r_A16','r_A8-r_A16','r_H8-r_A16']
    assert t['job_id']==job and t['state']=='COMPLETED' and 'ExitCode=0:0' in t['scontrol'] and t['summary']==s
    assert 'NumCPUs=4' in t['scontrol'] and 'QOS=qos_stu_default' in t['scontrol'] and 'TimeLimit=01:00:00' in t['scontrol']
    assert not (out/f'tde-x20-lbasis-{job}.err').read_bytes()
    prefix='outputs/hpc/x20-window-feedback-20260930/'
    for c in d['code']+d['small_claims']:
        path=c['path']
        if path.startswith(prefix):
            rel=path[len(prefix):]
            f=ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/'x20-feedback-82273-complete-received'/rel
        elif path.startswith('outputs/hpc/x20-window-difference-20260930/'):f=ROOT/'x20-window-difference-82396-received'/Path(path).name
        elif path.endswith('x20-accelerated-feedback-windows-20260930/source-preflight/boundary_geometry.npz'):f=ROOT/'x20-feedback-81769-complete-received/source-preflight/boundary_geometry.npz'
        else:f=Path(path)
        assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],path
    source=ROOT/'x20-feedback-82273-complete-received';fields=[]
    for name,n in [('accelerated',16),('historical',16),('accelerated',8),('historical',8)]:
        m=read(source/name/f'endpoints-map{n:02d}/manifest.json');row=m['history_rows'][-1]
        assert row['iteration']==n
        assert row['input_sha256']==m['endpoints']['final']['sha256']
        assert row['output_sha256']==m['endpoints']['mapped_final']['sha256']
        fields.extend(m['endpoints'][e] for e in ('final','mapped_final'))
    assert fields==d['fields'] and all(c['size_bytes']==10099884032 for c in fields)
    prev=read('handoff/evidence/20260930-x20-window-difference-82396-review.json')
    earlier=read(ROOT/'x20-window-difference-82396-received/declaration.json')
    assert fields[:4]==earlier['fields']['16'] and fields[4:]==earlier['fields']['8'] and p['all_eight_sha256_verified'] is True
    g,f=reduce_rows(p['slabs']);close(g,p['gram']);close(g,s['gram'])
    close(g[1][1],prev['results']['16']['total']['ee'])
    close(g[3][3]+g[2][2]-2*g[2][3],prev['results']['8']['total']['ee'])
    peaks=[max(r['basis_linf'][i] for r in p['slabs']) for i in range(4)]
    minima=[min(r['field_minima'][i] for r in p['slabs']) for i in range(8)]
    close(peaks,p['basis_linf']);close(minima,p['field_minima'])
    assert f.shape==(8,9632) and s['slabs']==301
    for z in (s,d):
        assert z['new_maps']==z['new_feedback_pairs']==z['new_material_steps']==0
        assert z['baseline_replaced'] is False and z['strict_error_bound'] is False
    assert d['maximum_field_scans']==1 and d['longdouble_mantissa_bits']>=52
    assert p['candidate_written'] is False and s['candidate_written'] is False
    assert s['status']==read(out/'status.json')['status']=='basis_complete_requires_review'
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    result=dict(job_id=job,receipt=receipt,independent_audit=True,code_claims_verified=len(d['code']),source_claims_verified=len(d['small_claims']),
                fields=fields,gram=g,basis_linf=peaks,field_minima=minima,
                boundary_metrics=[boundary(f[i],f[i+1]) for i in range(0,8,2)],slabs=301,blocks=76,groups=9632,
                peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],large_fields_recomputed_on_mac=False,
                new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    Path(f'handoff/evidence/20261001-x20-latest-basis-{job}-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(job_id=job,gram=g,slabs=301,source_verified=True),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--commit',required=True);a=p.parse_args();main(a.job,a.commit)
