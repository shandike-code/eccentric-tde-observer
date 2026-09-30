"""Independent small-artifact audit of the two real maps in Slurm 81679."""
import json,math
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_operator import old,cw,read,arrays,slab_coverage
from handoff.audit_tools.review_x20_histories import source_archive

ROOT=Path('outputs/review-20260925')
OUT=ROOT/'x20-expanded-81679-received'
BASE='complete-1790732954355330907'


def norms(rows,n):
    slab_coverage(rows)
    ss=np.asarray([r['squared_l2'] for r in rows]);pp=np.asarray([r['linf'] for r in rows])
    assert ss.shape==pp.shape==(301,n) and np.isfinite(ss).all() and np.isfinite(pp).all()
    assert np.all(ss>=0) and np.all(pp>=0)
    totals=np.array([math.fsum(ss[:,i]) for i in range(n)]);peaks=pp.max(axis=0)
    assert totals[0]>0 and peaks[0]>0
    return totals,peaks,np.sqrt(totals/totals[0]),peaks/peaks[0]


def gates(l2,linf,boundary):
    result=dict(full_l2_benefit=bool(l2[1]<=.8),full_linf_nonincrease=bool(linf[1]<=1+1e-10),
                half_l2_nonincrease=bool(l2[2]<=1+1e-10),half_linf_nonincrease=bool(linf[2]<=1+1e-10))
    for i,name in ((1,'full'),(2,'half')):
        assert all(math.isfinite(boundary[i][k]) and boundary[i][k]>=0 for k in ('residual','boundary_l1','boundary_bolometric'))
        result[name+'_radiation']=boundary[i]['residual']<1e-4
        for k in ('boundary_l1','boundary_bolometric'):
            result[name+'_'+k]=boundary[i][k]<1e-3 and boundary[i][k]<=boundary[0][k]*(1+1e-10)
    return {k:bool(v) for k,v in result.items()}


def prediction_numbers(p,gram,candidate):
    selected=np.asarray(candidate['selected_coefficients']);assert p['selected_coefficients']==candidate['selected_coefficients']
    m=p['prediction'];rows=m['slabs'];ss,peaks,l2,linf=norms(rows,3)
    for r in rows:
        for k in ('scales','minima','boundary_flux','boundary_l1_numerator'):
            assert np.isfinite(r[k]).all() and np.all(np.asarray(r[k])>=0)
        assert len(r['minima'])==4 and np.isfinite(r['boundary_signed']).all()
    for i,t in enumerate((0,1,.5)):
        u=np.r_[1,t*selected];np.testing.assert_allclose(ss[i],u@gram@u,rtol=2e-9,atol=0)
    flux=[math.fsum(r['boundary_flux'][i] for r in rows) for i in range(6)];boundary=[]
    for i in range(3):
        den=max(flux[2*i:2*i+2]);scale=max(r['scales'][i] for r in rows);assert den>0 and scale>0
        boundary.append(dict(boundary_l1=math.fsum(r['boundary_l1_numerator'][i] for r in rows)/den,
            boundary_bolometric=abs(math.fsum(r['boundary_signed'][i] for r in rows))/den,residual=peaks[i]/scale))
    old.same_record(boundary,m['boundary'])
    np.testing.assert_allclose(l2,m['fixed_scale_l2_ratios'],rtol=1e-12,atol=0)
    np.testing.assert_allclose(linf,m['fixed_scale_linf_ratios'],rtol=1e-12,atol=0)
    checks=dict(full_field_nonnegative=True,**gates(l2,linf,boundary))
    assert checks==m['checks'] and all(checks.values())==m['passed']==p['all_predicted_checks_passed']
    assert not p['candidate_written']  # 文件是写大候选之前的预测快照，不是终态文件清单。
    return dict(l2_ratios=l2.tolist(),linf_ratios=linf.tolist(),boundary=boundary,checks=checks,squared_l2=ss.tolist(),linf=peaks.tolist())


def actual_numbers(v,original):
    r=v['field_comparison'];rows=r['slabs'];ss,peaks,l2,linf=norms(rows,4)
    assert r['all_groups_evaluated']==9632 and r['selected_blocks']==list(range(76))
    assert all(z['selected_input'] and z['block']==z['first_group']//128 and math.isfinite(z['output_change_linf']) and z['output_change_linf']>=0 for z in rows)
    np.testing.assert_allclose([math.sqrt(ss[0]),peaks[0]],[r['original_defect_l2'],r['original_defect_linf']],rtol=1e-12,atol=0)
    np.testing.assert_allclose(l2,r['fixed_scale_l2_ratios'],rtol=1e-12,atol=0)
    np.testing.assert_allclose(linf,r['fixed_scale_linf_ratios'],rtol=1e-12,atol=0)
    boundary=[original,v['actual_maps']['full'],v['actual_maps']['half']]
    checks=gates(l2,linf,boundary)
    checks.update(independent_half_affinity=bool(l2[3]<=1e-6),independent_half_linf_affinity=bool(linf[3]<=1e-6))
    assert checks==v['checks'] and all(checks.values())==v['validated']
    assert not v['baseline_replaced'] and not v['material_step_promoted']
    return dict(l2_ratios=l2.tolist(),linf_ratios=linf.tolist(),checks=checks,squared_l2=ss.tolist(),linf=peaks.tolist(),
                boundary_ratios={k:[row[k]/original[k] for row in boundary[1:]] for k in ('boundary_l1','boundary_bolometric')})


def main():
    inventory=cw.receive(ROOT/(BASE+'.tar.gz'),ROOT/(BASE+'-receipt.json'),OUT)
    assert inventory==read(ROOT/(BASE+'.json')) and len(inventory['files'])==328
    d=read(OUT/'declaration.json');s=read(OUT/'summary.json');pre=read(OUT/'source-preflight/declaration.json')
    term=read(Path('handoff/evidence/20260930-x20-expanded-81679-terminal.json'))
    assert term['job_id']==81679 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
    sched=d['environment']['scheduler'];assert sched['SLURM_JOB_ID']=='81679' and sched['SLURM_CPUS_PER_TASK']=='32' and sched['SLURM_MEM_PER_NODE']=='131072'
    assert d['maximum_maps']==s['new_maps']==2 and d['maximum_feedback_pairs']==s['new_feedback_pairs']==0
    assert d['maximum_field_scans']==3 and d['maximum_proposals']==1 and d['coefficient_dimension']==4
    assert d['coefficient_l1_cap']==17 and d['full_fraction']==.9 and d['half_fraction']==.45
    assert d['source_jobs']==[80554,81647] and d['accepted_outer_steps']==s['accepted_outer_steps']==20 and s['new_material_steps']==0
    assert d['fixed_material_x20'] and d['historical_failures_retained'] and not any(d[k] for k in ('baseline_replaced','automatic_promotion','strict_error_bound'))
    assert s['status']==read(OUT/'status.json')['status']=='true_maps_validated_requires_review'
    assert s['validated'] and s['all_predicted_checks_passed'] and s['parent_peak_rss_bytes']<6*1024**3
    for c in d['code']+pre['code']:old.verify_claim(c,Path(c['path']))
    source=ROOT/'x20-long-chord-81647-received';history=ROOT/'x20-history-80554-received'
    source_archive(source,'20260930-x20-long-chord-review.json',ROOT)
    source_archive(history,'20260929-x20-history-review.json',ROOT)
    expanded=read(source/'expanded-basis.json');assert d['basis']==expanded['original_basis']+expanded['new_pair']
    assert pre['field_pairs']==[d['basis'][i] for i in (1,2,4,5)]
    assert d['source_row']==pre['source_rows'][0]==read(history/'late/state.json')['history'][-1]
    candidate=read(Path('handoff/evidence/20260930-x20-expanded-candidate-result.json'))
    audit=read(Path('handoff/evidence/20260930-x20-expanded-candidate-review.json'))
    assert audit['independent_70digit_spectral_witness'] and audit['result_sha256']==old.digest(Path('handoff/evidence/20260930-x20-expanded-candidate-result.json'))
    assert d['raw_coefficients']==candidate['raw_coefficients'] and d['selected_coefficients']==candidate['selected_coefficients']
    raw=np.array(d['raw_coefficients']);assert math.fsum(abs(np.r_[raw[0],1-math.fsum(raw),raw[1:]]))<=17
    np.testing.assert_array_equal(d['selected_coefficients'],.9*raw)
    prefixes={'outputs/hpc/x20-long-chord-20260930/':source,'outputs/hpc/x20-radiation-history-calibration-20260929/':history,'outputs/hpc/x20-expanded-validation-20260930/':OUT}
    parent_claims=read(source/'declaration.json')['claims'];external=[];verified=0
    for c in d['claims']:
        if c['path'].endswith('.dat'):
            assert c in d['basis'];external.append(c);continue
        path=Path(c['path'])
        for prefix,folder in prefixes.items():
            if c['path'].startswith(prefix):path=folder/c['path'][len(prefix):];break
        if '/archives/' in c['path']:path=ROOT/Path(c['path']).name
        if path.is_file():old.verify_claim(c,path);verified+=1
        else:assert c in parent_claims;external.append(c)
    trial=OUT/'source-preflight/inputs/trial_material.npz'
    for c in d['cases']['control'].values():old.verify_claim(c,OUT/'source-preflight/inputs'/Path(c['path']).name)
    assert old.digest(trial)==old.digest(source/'chord/trial_material.npz')==old.digest(history/'late/trial_material.npz')
    t=arrays(trial);assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    geometry=arrays(OUT/'source-preflight/boundary_geometry.npz');previous_geometry=arrays(source/'source-preflight/boundary_geometry.npz')
    for k in geometry:np.testing.assert_array_equal(geometry[k],previous_geometry[k])
    seeds=read(OUT/'candidate-claims.json');v=read(OUT/'validation.json');maps={};peaks=[]
    for name in ('full','half'):
        cfg=read(OUT/name/'config.json');state=read(OUT/name/'state.json');native=read(OUT/name/'native_trial_audit.json')
        assert cfg['workers']==16 and cfg['maximum_maps']==1 and cfg['warm_seed']==seeds[name]
        assert cfg['radiation_threshold']==1e-4 and cfg['boundary_threshold']==1e-3 and cfg['shape']==[9632,32,4096]
        assert old.digest(OUT/name/'trial_material.npz')==old.digest(trial)==state['trial_sha256']
        old.verify_claim(native['trial_source'],OUT/name/'trial_material.npz')
        assert native['native_mirrored_material_exact'] and native['physical_phase_and_dt_exact']
        identity=read(OUT/name/'initialized_identity.json');assert identity['passed'] and identity['native']==native
        assert state['history']==[v['actual_maps'][name]] and state['current_sha256']==state['history'][0]['output_sha256']
        assert seeds[name]['sha256']==state['history'][0]['input_sha256'] and seeds[name]['size_bytes']==10099884032
        maps[name],resources=old.audit_maps(OUT,name,max_maps=1);peaks+=resources
        blocks=[read(OUT/name/f'map0001/block{i:02d}.json') for i in range(76)]
        assert [(z['core_group_start'],z['core_group_stop']) for z in blocks]==[(128*i,min(128*(i+1),9632)) for i in range(76)]
    p=prediction_numbers(read(OUT/'prediction.json'),arrays(source/'expanded-system.npz')['gram'],candidate)
    a=actual_numbers(v,d['source_row']);np.testing.assert_allclose(a['squared_l2'][0],p['squared_l2'][0],rtol=1e-12,atol=0)
    np.testing.assert_array_equal(a['linf'][0],p['linf'][0])
    result=dict(job_id=81679,archive=read(ROOT/(BASE+'-receipt.json')),verified_files=len(inventory['files']),verified_code_claims=len(d['code']),verified_source_claims=verified,
        external_claims_bound_to_prior_audit=external,prediction=p,actual=a,actual_maps=v['actual_maps'],candidate_claims=seeds,
        maps=maps,map_process_receipts=len(peaks),maximum_proc_kib=max(peaks),parent_peak_rss_bytes=s['parent_peak_rss_bytes'],wall_s=s['wall_s'],
        new_maps=2,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20,baseline_replaced=False,
        independent_small_statistic_reduction=True,large_fields_recomputed_on_mac=False,native_identity_batch_receipt_verified=True,
        strict_physical_error_bound=False,true_maps_independently_validated=True,material_response_not_yet_evaluated=True)
    Path('handoff/evidence/20260930-x20-expanded-validation-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(actual=a,wall_s=s['wall_s'],verified_files=len(inventory['files']),receipts=len(peaks)),indent=2))


if __name__=='__main__':main()
