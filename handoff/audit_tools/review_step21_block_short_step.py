"""Independent small-artifact audit of a completed fixed-direction line scan."""
import argparse,json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,read,digest,verified_inventory


def close(a,b,rtol=2e-12,atol=0):np.testing.assert_allclose(a,b,rtol=rtol,atol=atol)


def review(archive,receipt,received,terminal,output):
    manifest=receive(archive,receipt,received);d=read(received/'declaration.json');p=read(received/'prediction.json');s=read(received/'status.json');term=read(terminal)
    assert term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol'] and s['status']=='complete_requires_review'
    assert d['maximum_maps']==d['maximum_feedback_pairs']==d['maximum_candidate_writes']==0
    assert d['accepted_outer_steps']==s['accepted_outer_steps']==20 and s['new_material_steps']==0
    assert p['actual_map_performed']==p['candidate_written']==p['accepted_material_step']==False
    for c in d['code']:
        f=Path(c['path']);assert digest(f)==c['sha256'] and f.stat().st_size==c['size_bytes']
    prior=Path('outputs/review-20260925/heating-block-global-77701-received')
    audit=read(Path('handoff/evidence/20260926-block-global-review.json'));claim=audit['archive']
    oldarchive=archive.parent/Path(claim['path']).name;assert digest(oldarchive)==claim['sha256']
    with tarfile.open(oldarchive) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(prior/'ARCHIVE_MANIFEST.json')
    verified_inventory(prior);v=read(prior/'control/validation.json');row=v['actual_map'];original=read(prior/'declaration.json')['source_row']
    expected=v['source_pair']+[v['candidate'],dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=10099884032)]
    assert d['paths']==expected and d['source_row']==original
    slabs=p['slabs'];assert [(z['start'],z['stop']) for z in slabs]==[(i,i+32) for i in range(0,9632,32)]
    assert all(np.isfinite([z[k] for k in ('s0','dd','rd','maximum')]).all() and all(z[k]>=0 for k in ('s0','dd','maximum')) for z in slabs)
    s0,dd,rd=[math.fsum(z[k] for z in slabs) for k in ('s0','dd','rd')];maximum=max(z['maximum'] for z in slabs)
    for k,x in [('s0',s0),('dd',dd),('rd',rd),('original_maximum',maximum),('original_l2',math.sqrt(s0))]:close(x,p[k])
    close(math.sqrt(s0),audit['original_defect_l2']);close(maximum,audit['original_defect_linf'])
    upper=p['linf_upper'];assert 0<=upper<=1;w=p['witness'];witness_data=None
    if w is not None:
        assert len(w['index'])==3 and all(type(i) is int for i in w['index'])
        assert all(0<=i<n for i,n in zip(w['index'],(9632,32,4096)))
        r,delta,m=[float.fromhex(w[k]) for k in ('raw_hex','delta_hex','maximum_hex')]
        assert np.isfinite([r,delta,m]).all() and m==maximum and abs(r)<=m and delta!=0
        bound=(m-r)/delta if delta>0 else (m+r)/(-delta)
        close(bound,upper);close(bound,w['upper'])
        witness_data=dict(index=w['index'],raw=r,delta=delta,maximum=m,delta_over_original_maximum=delta/m,upper=bound,
            relative_to_measured_half_affinity_max=(abs(delta)/m)/audit['fixed_scale_linf_ratios'][3])
    else:assert upper==1
    choice=p['choice'];t=0. if dd==0 or rd>=0 or upper==0 else .9*min(-rd/dd,upper,1.)
    close(t,choice['fraction']);ratio=math.sqrt((s0+2*t*rd+t*t*dd)/s0) if t else 1.
    close(ratio,choice['predicted_l2_ratio']);checks={'nonzero_step':t>0,'l2_cost_pass':t>0 and ratio<=.999}
    assert choice['l2_cost_pass']==checks['l2_cost_pass']
    f=np.asarray(p['fluxes']);assert f.shape==(4,9632) and np.isfinite(f).all()
    if t:
        assert p['passes']==3
        checks.update(streamed_l2_cost_pass=choice['streamed_l2_ratio']<=.999,streamed_linf_nonincrease=choice['streamed_linf_ratio']<=1.0000000001,
            radiation_upper_bound=choice['streamed_linf_ratio']*maximum/p['unchanged_field_scale']<1e-4)
        assert choice['predicted_minimum']>=0 and np.isfinite(choice['predicted_minimum'])
        close(choice['streamed_l2_ratio'],ratio,rtol=1e-7)
        for label,a in [('selected',t),('half',t/2)]:
            x=(1-a)*f[0]+a*f[2];y=(1-a)*f[1]+a*f[3]
            l1=math.fsum(abs(float(v)) for v in y-x)/max(math.fsum(abs(float(v)) for v in x),math.fsum(abs(float(v)) for v in y))
            sx,sy=math.fsum(map(float,x)),math.fsum(map(float,y));bol=abs(sy-sx)/max(abs(sx),abs(sy))
            for key,z in [('boundary_l1',l1),('boundary_bolometric',bol)]:
                close(z,p['boundary_predictions'][label][key],rtol=1e-8,atol=1e-15)
                checks[label+'_'+key]=0<=z<1e-3 and z<=original[key]*1.0000000001
    else:assert p['passes']==2 and not p['boundary_predictions']
    assert checks==p['checks'] and all(checks.values())==p['eligible_for_independent_review']
    assert p['peak_rss_bytes']<6*1024**3
    report=dict(archive=read(receipt),job_id=term['job_id'],verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
        accepted_outer_steps=20,new_material_steps=0,actual_map_performed=False,candidate_written=False,
        original_l2=math.sqrt(s0),original_maximum=maximum,unconstrained_l2_optimum=-rd/dd if dd else None,
        linf_upper=upper,witness=witness_data,choice=choice,checks=checks,eligible_for_independent_review=all(checks.values()),
        peak_rss_bytes=p['peak_rss_bytes'],passes=p['passes'],independent_scalar_and_witness_reduction=True,
        all_field_constraints_recomputed_on_mac=False,third_pass_raw_fields_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for k in ('archive','receipt','received','terminal','output'):parser.add_argument('--'+k,type=Path,required=True)
    review(**vars(parser.parse_args()))
