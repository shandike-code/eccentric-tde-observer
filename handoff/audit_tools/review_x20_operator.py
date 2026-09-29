"""Independent small-statistic/source/map audit of 80826 and 80823, without dat downloads."""
import json,math
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_refreshed_directions as old
from handoff.audit_tools.review_x20_histories import source_archive
cw,read,arrays=old.cw,old.read,old.arrays
ROOT=Path('outputs/review-20260925');SOURCE=ROOT/'x20-history-80554-received'
CASES={'scan':(80826,'complete-1790664777804282278'),'midpoint':(80823,'complete-1790665125911355612')}


def slab_coverage(rows):
    assert [(r['first_group'],r['group_count']) for r in rows]==[(i,32) for i in range(0,9632,32)]


def norm_reduction(rows,n):
    slab_coverage(rows)
    values=np.asarray([r['squared_l2'] for r in rows]);peaks=np.asarray([r['linf'] for r in rows])
    assert values.shape==(301,n) and peaks.shape[0]==301 and np.isfinite(values).all() and np.isfinite(peaks).all()
    assert np.all(values>=0) and np.all(peaks>=0)
    return np.array([math.fsum(values[:,i]) for i in range(n)]),np.max(peaks,axis=0)


def gram_roundoff_check(g):
    g=np.asarray(g,float);assert g.shape==(4,4) and np.isfinite(g).all() and np.array_equal(g,g.T)
    scale=float(np.max(abs(g)))
    if scale==0:return dict(normalized_min_eigenvalue=0.,normalized_bound=0.)
    # 4x4矩阵每元素一次float转存误差<=半ulp；谱范数误差<=4*半ulp。
    # 亚正规区ulp为nextafter(0,1)，不能将这个绝对误差误判为物理负模。
    bound=max(1e-12,2*(float(np.nextafter(0.,1.))/scale))
    eigen=float(np.linalg.eigvalsh(g/scale).min());assert eigen>=-bound
    return dict(normalized_min_eigenvalue=eigen,normalized_bound=bound)


def scan_review(p):
    rs=p['slabs'];slab_coverage(rs)
    gs=np.asarray([r['gram'] for r in rs]);assert gs.shape==(301,4,4) and np.isfinite(gs).all()
    assert np.array_equal(gs,gs.transpose(0,2,1))
    quantization=[dict(first_group=r['first_group'],**gram_roundoff_check(g)) for r,g in zip(rs,gs)]
    g=np.array([[math.fsum(gs[:,i,j]) for j in range(4)] for i in range(4)]);np.testing.assert_allclose(g,p['gram'],rtol=1e-12,atol=0)
    intervals=np.asarray([r['alpha_interval'] for r in rs]);assert np.isfinite(intervals).all() and np.all(intervals[:,0]>=-8) and np.all(intervals[:,0]<=0) and np.all(intervals[:,1]>=0) and np.all(intervals[:,1]<=8)
    lo,hi=float(max(intervals[:,0])),float(min(intervals[:,1]));resolved=bool(g[1,1]>1e-12*g[0,0])
    optimum=-g[0,1]/g[1,1] if resolved else None
    bounded=min(hi,max(lo,optimum)) if resolved else 0.;a=.9*bounded
    choice=dict(alpha=a,unconstrained_alpha=optimum,direction_resolved=resolved,alpha_interval=[lo,hi],coefficient_l1=abs(1-a)+abs(a),
        difference_gain_l2=math.sqrt(g[3,3]/g[2,2]),difference_projection=g[2,3]/g[2,2],strict_error_bound=False)
    old.same_record(choice,p['choice'])
    ss,pp=norm_reduction(p['prediction_slabs'],3)
    assert all(r['minimum_candidate']>=0 and r['minimum_prediction']>=0 for r in p['prediction_slabs'])
    np.testing.assert_allclose(ss[0],g[0,0],rtol=1e-12,atol=0)
    expected=math.fsum([g[0,0],2*a*g[0,1],a*a*g[1,1]])
    np.testing.assert_allclose(ss[1],expected,rtol=1e-9,atol=0)
    spectra=np.asarray(p['surface_spectra']);assert spectra.shape==(4,9632) and np.isfinite(spectra).all() and np.all(spectra>=0)
    fin,fout,h,k=spectra;pin,pout=fin+a*(h-fin),fout+a*(k-fout)
    assert np.all(pin>=0) and np.all(pout>=0)
    def boundary(x,y):
        den=max(math.fsum(abs(x)),math.fsum(abs(y)));assert den>0
        return dict(boundary_l1=math.fsum(abs(y-x))/den,boundary_bolometric=abs(math.fsum(y-x))/den)
    original,predicted=boundary(fin,fout),boundary(pin,pout)
    old.same_record(original,p['original_boundary']);old.same_record(predicted,p['predicted_boundary'])
    l2,linf=math.sqrt(ss[1]/ss[0]),pp[1]/pp[0]
    np.testing.assert_allclose([l2,linf,math.sqrt(ss[2]/g[3,3])],[p['l2_ratio'],p['linf_ratio'],p['difference_nonparallel_fraction']],rtol=1e-12,atol=0)
    checks=dict(resolved_nonzero_direction=resolved and a!=0,coefficient_l1_bounded=choice['coefficient_l1']<=17,
        l2_benefit=l2<=.8,linf_nonincrease=bool(pp[1]<=pp[0]*(1+1e-10)))
    for key in original:checks[key]=predicted[key]<1e-3 and predicted[key]<=original[key]*(1+1e-10)
    checks={k:bool(v) for k,v in checks.items()}
    assert checks==p['checks'] and p['feasible']==all(checks.values()) and not p['candidate_written'] and p['true_map_required']
    return dict(choice=choice,l2_ratio=l2,linf_ratio=linf,original_boundary=original,predicted_boundary=predicted,checks=checks,feasible=all(checks.values()),
        largest_anchor_defect_slabs=[dict(first_group=int(rs[i]['first_group']),squared_fraction=float(gs[i,0,0]/g[0,0])) for i in np.argsort(gs[:,0,0])[-10:][::-1]],
        largest_history_difference_slabs=[dict(first_group=int(rs[i]['first_group']),squared_fraction=float(gs[i,2,2]/g[2,2])) for i in np.argsort(gs[:,2,2])[-10:][::-1]],
        difference_nonparallel_fraction=p['difference_nonparallel_fraction'],gram=g.tolist(),
        subnormal_gram_roundoff=[r for r in quantization if r['normalized_bound']>1e-12])


def main():
    source_archive(SOURCE,'20260929-x20-history-review.json',ROOT)
    basis=[];rows=[]
    for child,n in [('late',16),('historical',24)]:
        m=read(SOURCE/child/f'endpoints-map{n:02d}/manifest.json');state=read(SOURCE/child/'state.json')
        basis += [m['endpoints'][k] for k in ('final','mapped_final')];rows.append(state['history'][-1])
    results={}
    for mode,(job,base) in CASES.items():
        out=ROOT/f'x20-{mode}-{job}-received';manifest=cw.receive(ROOT/(base+'.tar.gz'),ROOT/(base+'-receipt.json'),out)
        assert manifest==read(ROOT/(base+'.json'))
        d=read(out/'declaration.json');s=read(out/'summary.json');terminal=read(Path(f'handoff/evidence/20260929-x20-{mode}-{job}-terminal.json'))
        assert terminal['job_id']==job and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
        assert d['environment']['scheduler']['SLURM_JOB_ID']==str(job) and d['source_job']==80554 and d['mode']==mode
        assert d['field_pairs']==basis and d['source_rows']==rows and d['frozen_x20'] and d['alpha_bounds']==[-8.,8.]
        assert d['coefficient_l1_cap']==17 and d['step_safety']==.9 and d['affinity_limit']==1e-6
        assert d['maximum_maps']==(1 if mode=='midpoint' else 0) and d['maximum_feedback_pairs']==0 and d['maximum_field_scans']==2
        assert not any(d[k] for k in ('baseline_replaced','automatic_promotion','production_candidate_written','physical_dt_changed'))
        assert s['status']==read(out/'status.json')['status']=='complete_requires_review' and s['mode']==mode and s['source_job']==80554
        assert s['new_maps']==d['maximum_maps'] and s['new_feedback_pairs']==s['new_material_steps']==0 and s['accepted_outer_steps']==20
        assert not s['baseline_replaced'] and not s['strict_error_bound'] and s['historical_failures_retained'] and s['parent_peak_rss_bytes']<6*1024**3
        for c in d['code']:old.verify_claim(c,Path(c['path']))
        for c in d['cases']['control'].values():old.verify_claim(c,out/'inputs'/Path(c['path']).name)
        assert old.digest(out/'inputs/trial_material.npz')==old.digest(SOURCE/'late/trial_material.npz')==old.digest(SOURCE/'historical/trial_material.npz')
        assert read(out/'inputs/config.json')==read(SOURCE/'late/config.json')
        claim_index={c['path']:c for c in d['claims']}
        for child,n in [('late',16),('historical',24)]:
            for name in ('state.json','config.json','trial_material.npz',f'endpoints-map{n:02d}/manifest.json',f'pair{n:02d}/feedback_protocol.json'):
                c=claim_index[d['source']+'/'+child+'/'+name];old.verify_claim(c,SOURCE/child/name)
        for name in ('declaration.json','summary.json'):old.verify_claim(claim_index[d['source']+'/'+name],SOURCE/name)
        for name in ('20260929-x20-history-review.json','20260929-x20-history-80554-terminal.json'):
            path=Path('handoff/evidence')/name;old.verify_claim(claim_index[str(path)],path)
        t=arrays(out/'inputs/trial_material.npz');assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
        geometry=arrays(out/'boundary_geometry.npz');assert set(geometry)=={'mu','weight','width'}
        assert geometry['width'].shape==(9632,) and geometry['mu'].shape==geometry['weight'].shape==(32,)
        assert all(np.isfinite(z).all() for z in geometry.values()) and np.all(geometry['width']>0) and np.all(geometry['weight']>0)
        np.testing.assert_allclose(sum(geometry['weight']),2,rtol=1e-14)
        result=dict(job_id=job,archive=read(ROOT/(base+'-receipt.json')),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
            accepted_outer_steps=20,new_material_steps=0,new_maps=s['new_maps'],new_feedback_pairs=0,baseline_replaced=False,
            independent_small_statistic_reduction=True,large_fields_recomputed_on_mac=False,strict_error_bound=False,parent_peak_rss_bytes=s['parent_peak_rss_bytes'])
        if mode=='scan':
            wrapper=read(out/'scan_driver_declaration.json');assert wrapper['previous_failed_job']==80822 and wrapper['simultaneous_scan_processes']==1 and wrapper['allocated_cpus_required']==4 and wrapper['science_protocol_unchanged']
            for c in wrapper['code']:old.verify_claim(c,Path(c['path']))
            result.update(scan_review(read(out/'prediction.json')));assert not result['feasible'] and not s['scan_feasible']
        else:
            val=read(out/'validation.json');ss,pp=norm_reduction(val['slabs'],5)
            np.testing.assert_allclose(ss,val['squared_l2'],rtol=1e-12,atol=0);np.testing.assert_array_equal(pp,val['linf'])
            lr=[math.sqrt(ss[3]/ss[i]) for i in (0,1)];ir=[pp[3]/pp[i] for i in (0,1)]
            np.testing.assert_allclose(lr,val['affinity_over_each_original_l2'],rtol=1e-12,atol=0)
            np.testing.assert_allclose(ir,val['affinity_over_each_original_linf'],rtol=1e-12,atol=0)
            passed=all(z<=1e-6 for z in lr+ir);assert passed==val['affinity_pass']==s['affinity_pass'] and val['true_map_performed'] and not val['material_step_promoted']
            maps,resources=old.audit_maps(out,'midpoint',max_maps=1);st=read(out/'midpoint/state.json');assert st['history']==[val['actual_map']]
            seed=read(out/'midpoint-claim.json');cfg=read(out/'midpoint/config.json')
            assert cfg['warm_seed']==seed and cfg['workers']==16 and cfg['maximum_maps']==1 and st['history'][0]['input_sha256']==seed['sha256']
            assert old.digest(out/'midpoint/trial_material.npz')==old.digest(out/'inputs/trial_material.npz')
            rs=[read(out/f'midpoint/map0001/block{i:02d}.json') for i in range(76)]
            den=max(math.fsum(r['current_boundary_absolute_scale'] for r in rs),math.fsum(r['mapped_boundary_absolute_scale'] for r in rs))
            l1=math.fsum(r['boundary_spectrum_l1_numerator'] for r in rs)/den
            np.testing.assert_allclose(l1,val['actual_map']['boundary_l1'],rtol=1e-12,atol=0)
            assert val['worker_maximum_proc_kib']==max(resources)
            result.update(affinity_pass=passed,affinity_l2=lr,affinity_linf=ir,actual_map=val['actual_map'],maps=maps,
                map_process_receipts=len(resources),maximum_proc_kib=max(resources),field_squares=ss.tolist())
        results[mode]=result
        Path(f'handoff/evidence/20260929-x20-{mode}-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    np.testing.assert_allclose(results['scan']['gram'][0][0],results['midpoint']['field_squares'][0],rtol=1e-12,atol=0)
    np.testing.assert_allclose(results['scan']['gram'][2][2],results['midpoint']['field_squares'][4],rtol=1e-12,atol=0)
    import matplotlib.pyplot as plt
    p=read(ROOT/'x20-scan-80826-received/prediction.json');r=p['slabs'];g=results['scan']['gram']
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for i,label in [(0,'late map defect'),(2,'history difference')]:axes[0].plot([x['first_group'] for x in r],[x['gram'][i][i]/g[i][i] for x in r],label=label)
    axes[0].set(xlabel='First frequency group of 32-group slab',ylabel='Fraction of unweighted squared L2');axes[0].legend()
    a=results['scan'];labels=['L2 defect','Linf defect','Boundary L1','Boundary bolometric']
    axes[1].bar(labels,[a['l2_ratio'],a['linf_ratio']]+[a['predicted_boundary'][k]/a['original_boundary'][k] for k in ('boundary_l1','boundary_bolometric')]);axes[1].set_yscale('log');axes[1].axhline(1,color='k',ls='--');axes[1].set_ylabel('Predicted quantity / original late endpoint');axes[1].tick_params(axis='x',labelrotation=15)
    fig.savefig('handoff/evidence/20260929-x20-operator-review.png',dpi=150);plt.close(fig)
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
