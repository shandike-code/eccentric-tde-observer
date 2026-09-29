"""Independent audit of the 80925 joint-cap proposal and spectral rejection."""
import json,math
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_operator import old,cw,read,arrays,slab_coverage
from handoff.audit_tools.review_x20_subspace import active_face_certificate
from handoff.audit_tools.review_x20_histories import source_archive
ROOT=Path('outputs/review-20260925')
BASE='complete-1790671833050176732'
OUT=ROOT/'x20-capped-80925-received'


def reduce_prediction(p,source):
    assert p['gram']==source['gram'] and p['boundary_coefficients']==source['boundary_coefficients'] and p['reused_gram_from_job']==80862
    g=np.asarray(p['gram']);certificate=active_face_certificate(g,p['boundary_coefficients'])
    np.testing.assert_allclose(p['solve']['raw_coefficients'],certificate['coefficients'],rtol=2e-9,atol=0)
    assert p['solve']['coefficient_l1_cap']==17 and p['solve']['retained_rank']==3
    np.testing.assert_allclose(p['solve']['l2_ratio'],certificate['l2_ratio'],rtol=1e-10)
    assert abs(p['solve']['squared_upper']-p['solve']['squared_support_lower'])<=p['solve']['roundoff_allowance']
    limits=p['positivity_slabs'];slab_coverage(limits)
    assert all(r['upper']==1 and r['negative_candidate']==r['negative_prediction']==0 for r in limits)
    assert p['bounds']['positivity_upper']==p['bounds']['bounded_upper']==1 and p['bounds']['selected_fraction']==.9
    selected=.9*np.array(certificate['coefficients'])
    np.testing.assert_allclose(selected,p['selected_coefficients'],rtol=2e-9,atol=0)
    # Use the stored selected coefficients in reduction, after independently checking the solve.
    selected=np.asarray(p['selected_coefficients']);w=np.r_[selected[0],1-math.fsum(selected),selected[1:]]
    np.testing.assert_allclose(w,p['weights'],rtol=1e-12)
    assert math.isclose(math.fsum(abs(w)),p['bounds']['coefficient_l1'],rel_tol=1e-12) and math.fsum(abs(w))<=17
    measured=p['prediction'];rows=measured['slabs'];slab_coverage(rows)
    for r in rows:
        for k in ('squared_l2','linf','scales','minima','boundary_flux','boundary_l1_numerator'):
            assert np.isfinite(r[k]).all() and np.all(np.asarray(r[k])>=0)
        assert np.isfinite(r['boundary_signed']).all()
    ss=np.array([math.fsum(r['squared_l2'][i] for r in rows) for i in range(3)])
    peaks=np.max([r['linf'] for r in rows],axis=0)
    for i,t in enumerate((0,1,.5)):
        u=np.r_[1,t*selected];expected=float(u@g@u)
        np.testing.assert_allclose(ss[i],expected,rtol=2e-9,atol=0)
    ratios=np.sqrt(ss/ss[0]);linf=peaks/peaks[0]
    np.testing.assert_allclose(ratios,measured['fixed_scale_l2_ratios'],rtol=1e-12,atol=0)
    np.testing.assert_allclose(linf,measured['fixed_scale_linf_ratios'],rtol=1e-12,atol=0)
    flux=[math.fsum(r['boundary_flux'][i] for r in rows) for i in range(6)];boundary=[]
    for i in range(3):
        den=max(flux[2*i:2*i+2]);assert den>0
        boundary.append(dict(boundary_l1=math.fsum(r['boundary_l1_numerator'][i] for r in rows)/den,
            boundary_bolometric=abs(math.fsum(r['boundary_signed'][i] for r in rows))/den,
            residual=peaks[i]/max(r['scales'][i] for r in rows)))
    old.same_record(boundary,measured['boundary'])
    gates=dict(full_l2_benefit=bool(ratios[1]<=.8),full_linf_nonincrease=bool(linf[1]<=1.0000000001),
        half_l2_nonincrease=bool(ratios[2]<=1.0000000001),half_linf_nonincrease=bool(linf[2]<=1.0000000001))
    for i,name in ((1,'full'),(2,'half')):
        gates[name+'_radiation']=bool(boundary[i]['residual']<1e-4)
        for k in ('boundary_l1','boundary_bolometric'):gates[name+'_'+k]=bool(boundary[i][k]<1e-3 and boundary[i][k]<=boundary[0][k]*1.0000000001)
    assert gates==measured['checks'] and not measured['passed'] and not p['all_predicted_checks_passed'] and not p['candidate_written']
    assert [k for k,v in gates.items() if not v]==['full_boundary_l1','half_boundary_l1']
    boundary_ratios={k:[v[k]/boundary[0][k] for v in boundary] for k in ('boundary_l1','boundary_bolometric')}
    return dict(selected_coefficients=selected.tolist(),weights=w.tolist(),joint_certificate=certificate,
        bounds=p['bounds'],l2_ratios=ratios.tolist(),linf_ratios=linf.tolist(),boundary=boundary,checks=gates,
        boundary_ratios=boundary_ratios,net_vs_spectral_cancellation=[v['boundary_l1']/v['boundary_bolometric'] for v in boundary])


def main():
    inventory=cw.receive(ROOT/(BASE+'.tar.gz'),ROOT/(BASE+'-receipt.json'),OUT)
    assert inventory==read(ROOT/(BASE+'.json')) and len(inventory['files'])==8
    d=read(OUT/'declaration.json');pre=read(OUT/'source-preflight/declaration.json');s=read(OUT/'summary.json')
    terminal=read(Path('handoff/evidence/20260929-x20-capped-80925-terminal.json'))
    assert terminal['job_id']==80925 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='80925'
    assert d['maximum_maps']==2 and d['maximum_feedback_pairs']==0 and d['maximum_field_scans']==4 and d['maximum_proposals']==1
    assert d['coefficient_l1_cap']==17 and d['rcond']==1e-12 and d['source_jobs']==[80554,80826,80823,80862]
    assert d['fixed_material_x20'] and d['historical_failures_retained'] and not any(d[k] for k in ('baseline_replaced','automatic_promotion','strict_error_bound'))
    assert s['status']==read(OUT/'status.json')['status']=='prediction_rejected'
    assert s['new_maps']==s['new_feedback_pairs']==s['new_material_steps']==0 and s['accepted_outer_steps']==20
    assert not any(s[k] for k in ('baseline_replaced','strict_error_bound','validated','all_predicted_checks_passed'))
    assert s['parent_peak_rss_bytes']<6*1024**3
    for c in d['code']+pre['code']:old.verify_claim(c,Path(c['path']))
    source=ROOT/'x20-history-80554-received';source_archive(source,'20260929-x20-history-review.json',ROOT)
    basis=[]
    for child,n in [('late',16),('historical',24)]:
        m=read(source/child/f'endpoints-map{n:02d}/manifest.json');st=read(source/child/'state.json')
        assert m['history_rows']==st['history'][-2:]
        z=[m['endpoints'][k] for k in ('previous','final','mapped_final')]
        assert [r['sha256'] for r in z]==[st['history'][-2]['input_sha256'],st['history'][-1]['input_sha256'],st['history'][-1]['output_sha256']]
        basis+=z
    assert d['basis']==basis and pre['field_pairs']==[basis[i] for i in (1,2,4,5)]
    assert d['source_row']==pre['source_rows'][0]==read(source/'late/state.json')['history'][-1]
    for c in d['cases']['control'].values():old.verify_claim(c,OUT/'source-preflight/inputs'/Path(c['path']).name)
    assert read(OUT/'source-preflight/inputs/config.json')==read(source/'late/config.json')
    trial=OUT/'source-preflight/inputs/trial_material.npz';assert old.digest(trial)==old.digest(source/'late/trial_material.npz')==old.digest(source/'historical/trial_material.npz')
    t=arrays(trial);assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    claim_index={c['path']:c for c in d['claims']}
    for mode,job,run in [('scan',80826,'x20-history-scan-v2-20260929'),('midpoint',80823,'x20-history-midpoint-20260929')]:
        folder=ROOT/f'x20-{mode}-{job}-received';ap=f'20260929-x20-{mode}-review.json'
        source_archive(folder,ap,ROOT)
        for name in ('declaration.json','summary.json','prediction.json' if mode=='scan' else 'validation.json'):
            old.verify_claim(claim_index['outputs/hpc/'+run+'/'+name],folder/name)
        for name in (ap,f'20260929-x20-{mode}-{job}-terminal.json'):
            old.verify_claim(claim_index['handoff/evidence/'+name],Path('handoff/evidence')/name)
    previous=ROOT/'x20-subspace-80862-received'
    source_archive(previous,'20260929-x20-subspace-review.json',ROOT)
    for name in ('declaration.json','summary.json','prediction.json'):
        old.verify_claim(claim_index['outputs/hpc/x20-boundary-subspace-20260929/'+name],previous/name)
    for name in ('20260929-x20-subspace-review.json','20260929-x20-subspace-80862-terminal.json'):
        old.verify_claim(claim_index['handoff/evidence/'+name],Path('handoff/evidence')/name)
    assert d['basis']==read(previous/'declaration.json')['basis']
    result=reduce_prediction(read(OUT/'prediction.json'),read(previous/'prediction.json'))
    result.update(job_id=80925,archive=read(ROOT/(BASE+'-receipt.json')),verified_files=8,verified_code_claims=len(d['code']),
        accepted_outer_steps=20,new_material_steps=0,new_maps=0,new_feedback_pairs=0,baseline_replaced=False,
        independent_small_statistic_reduction=True,large_fields_recomputed_on_mac=False,strict_error_bound=False,
        parent_peak_rss_bytes=s['parent_peak_rss_bytes'],wall_s=s['wall_s'])
    target=Path('handoff/evidence/20260929-x20-capped-review.json');target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    axes[0].bar(['Full','Half'],result['l2_ratios'][1:]);axes[0].axhline(.8,color='r',ls='--',label='Full gate <= 0.8; half gate <= 1');axes[0].set(ylabel='Predicted L2 / original late',ylim=(0,1));axes[0].legend(fontsize=8)
    x=np.arange(2)
    for off,key in [(-.17,'boundary_l1'),(.17,'boundary_bolometric')]:axes[1].bar(x+off,result['boundary_ratios'][key][1:],width=.34,label=key)
    axes[1].axhline(1,color='r',ls='--');axes[1].set(xticks=x,xticklabels=['Full','Half'],ylabel='Boundary change / original late');axes[1].legend()
    fig.savefig('handoff/evidence/20260929-x20-capped-review.png',dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
