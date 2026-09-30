"""Independent reductions and source/worker audit for Slurm 82214."""
import argparse,json,math
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_operator import old,cw,read,arrays
from handoff.audit_tools.review_x20_expanded_validation import norms,gates
from handoff.audit_tools.review_x20_window_prediction import local_path

ROOT=Path('outputs/review-20260925')


def actual_numbers(v,original):
    r=v['field_comparison'];ss,peaks,l2,linf=norms(r['slabs'],4)
    assert r['all_groups_evaluated']==9632 and r['selected_blocks']==list(range(76))
    assert all(z['selected_input'] and z['block']==z['first_group']//128 and math.isfinite(z['output_change_linf']) and z['output_change_linf']>=0 for z in r['slabs'])
    np.testing.assert_allclose([math.sqrt(ss[0]),peaks[0]],[r['original_defect_l2'],r['original_defect_linf']],rtol=1e-12)
    np.testing.assert_allclose(l2,r['fixed_scale_l2_ratios'],rtol=1e-12)
    np.testing.assert_allclose(linf,r['fixed_scale_linf_ratios'],rtol=1e-12)
    boundary=[original,v['actual_maps']['full'],v['actual_maps']['half']]
    checks=gates(l2,linf,boundary)
    checks.update(independent_half_affinity=bool(l2[3]<=1e-6),independent_half_linf_affinity=bool(linf[3]<=1e-6))
    p=v['prediction_affinity'];ps,pp,pl2,pli=norms(p['slabs'],3)
    np.testing.assert_allclose(ps[0],ss[0],rtol=1e-12);np.testing.assert_array_equal(pp[0],peaks[0])
    np.testing.assert_allclose(pl2,p['l2_ratios'],rtol=1e-12);np.testing.assert_allclose(pli,p['linf_ratios'],rtol=1e-12)
    pc={name+'_'+norm:bool(value<=1e-6) for name,i in [('full',1),('half',2)] for norm,value in [('l2_affinity',pl2[i]),('linf_affinity',pli[i])]}
    assert pc==p['checks'] and all(pc.values())==p['passed'];checks.update(pc)
    assert checks==v['checks'] and all(checks.values())==v['validated']
    assert not v['baseline_replaced'] and not v['material_step_promoted']
    return dict(l2_ratios=l2.tolist(),linf_ratios=linf.tolist(),squared_l2=ss.tolist(),linf=peaks.tolist(),
        prediction_error_l2_ratios=pl2.tolist(),prediction_error_linf_ratios=pli.tolist(),checks=checks,validated=all(checks.values()),
        boundary_ratios={k:[row[k]/original[k] for row in boundary[1:]] for k in ('boundary_l1','boundary_bolometric')})


def main(base):
    out=ROOT/'x20-window-82214-received'
    inventory=cw.receive(ROOT/(base+'.tar.gz'),ROOT/(base+'-receipt.json'),out)
    assert inventory==read(ROOT/(base+'.json'))
    d=read(out/'declaration.json');s=read(out/'summary.json');term=read('handoff/evidence/20260930-x20-window-82214-terminal.json')
    assert term['job_id']==82214 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
    sched=d['environment']['scheduler'];assert sched['SLURM_JOB_ID']=='82214' and sched['SLURM_CPUS_PER_TASK']=='32' and sched['SLURM_MEM_PER_NODE']=='131072'
    assert 'QOS=qos_stu_cpu_long' in term['scontrol']
    assert d['maximum_maps']==s['new_maps']==2 and d['maximum_feedback_pairs']==s['new_feedback_pairs']==0 and d['maximum_candidates']==1
    assert d['source_jobs']==[81769,82166,82187] and d['full_fraction']==.9 and d['half_fraction']==.45
    for x in (d,s):
        assert x['accepted_outer_steps']==20 and x['new_material_steps']==0 and not x['baseline_replaced'] and not x['strict_error_bound']
    assert s['status']==read(out/'status.json')['status']
    assert s['status'] in ('true_maps_validated_requires_review','true_map_validation_rejected')
    assert 0<s['parent_peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<7200
    for c in d['code']:old.verify_claim(c,Path(c['path']))
    parent=ROOT/'x20-feedback-81769-complete-received';pd=read(parent/'declaration.json')
    prev=read('handoff/evidence/20260930-x20-82187-review.json')
    assert d['basis']==prev['fields'] and d['selected_coefficients']==prev['selected_coefficients'] and d['raw_coefficients']==prev['raw_coefficients']
    assert d['source_row']==read(parent/'accelerated/state.json')['history'][-1]
    checked=0;external=[];prefix='outputs/hpc/x20-window-validation-20260930/'
    for c in d['claims']:
        if c['path'].endswith('.dat'):
            assert c in d['basis'];external.append(c);continue
        if c['path'].startswith(prefix):p=out/c['path'][len(prefix):]
        elif c['path'].startswith('outputs/hpc/x20-window-prediction-20260930/'):p=ROOT/'x20-prediction-82187-received'/Path(c['path']).name
        else:p=local_path(c['path'])
        if p.is_file():old.verify_claim(c,p);checked+=1
        else:assert c in pd['claims'],c['path'];external.append(c)
    for c in d['cases']['control'].values():old.verify_claim(c,out/'inputs'/Path(c['path']).name)
    trial=out/'inputs/trial_material.npz'
    assert old.digest(trial)==old.digest(parent/'accelerated/trial_material.npz')
    arr=arrays(trial);assert int(arr['phase_index'])==1367 and float(arr['step_duration_s'])==889.419892762322
    seeds=read(out/'candidate-claims.json');v=read(out/'validation.json');maps={};peaks=[];roundoff={}
    for name in ('full','half'):
        cfg=read(out/name/'config.json');state=read(out/name/'state.json');native=read(out/name/'native_trial_audit.json')
        assert cfg['workers']==16 and cfg['maximum_maps']==1 and cfg['warm_seed']==seeds[name]
        assert cfg['radiation_threshold']==1e-4 and cfg['boundary_threshold']==1e-3 and cfg['shape']==[9632,32,4096]
        assert old.digest(out/name/'trial_material.npz')==old.digest(trial)==state['trial_sha256']
        old.verify_claim(native['trial_source'],out/name/'trial_material.npz')
        assert native['native_mirrored_material_exact'] and native['physical_phase_and_dt_exact']
        identity=read(out/name/'initialized_identity.json');assert identity['passed'] and identity['native']==native
        assert state['history']==[v['actual_maps'][name]] and state['current_sha256']==state['history'][0]['output_sha256']
        assert seeds[name]['sha256']==state['history'][0]['input_sha256'] and seeds[name]['size_bytes']==10099884032
        maps[name],resources=old.audit_maps(out,name,max_maps=1);peaks+=resources
        blocks=[read(out/name/f'map0001/block{i:02d}.json') for i in range(76)];row=state['history'][0]
        assert [(z['core_group_start'],z['core_group_stop']) for z in blocks]==[(128*i,min(128*(i+1),9632)) for i in range(76)]
        before,after=[math.fsum(z[k] for z in blocks) for k in ('current_boundary_bolometric','mapped_boundary_bolometric')]
        bol=abs(after-before)/max(abs(before),abs(after));eps=np.finfo(float).eps;gamma=76*eps/(1-76*eps)
        bound=4*gamma*math.fsum(abs(z[k]) for z in blocks for k in ('current_boundary_bolometric','mapped_boundary_bolometric'))/max(abs(before),abs(after))*(1+bol)
        assert abs(bol-row['boundary_bolometric'])<=bound
        l1=math.fsum(z['boundary_spectrum_l1_numerator'] for z in blocks)/max(math.fsum(z['current_boundary_absolute_scale'] for z in blocks),math.fsum(z['mapped_boundary_absolute_scale'] for z in blocks))
        np.testing.assert_allclose(l1,row['boundary_l1'],rtol=4*gamma,atol=0)
        roundoff[name]=dict(fsum_bolometric=bol,reported=row['boundary_bolometric'],roundoff_bound=bound)
    actual=actual_numbers(v,d['source_row']);assert actual['validated']==s['validated']
    np.testing.assert_allclose(actual['squared_l2'][0],prev['squared_l2'][0],rtol=1e-12)
    np.testing.assert_array_equal(actual['linf'][0],prev['linf'][0])
    result=dict(job_id=82214,archive=read(ROOT/(base+'-receipt.json')),verified_files=len(inventory['files']),verified_code_claims=len(d['code']),
        verified_source_claims=checked,external_claims_bound_to_prior_audit=external,actual=actual,actual_maps=v['actual_maps'],candidate_claims=seeds,
        maps=maps,map_process_receipts=len(peaks),maximum_proc_kib=max(peaks),parent_peak_rss_bytes=s['parent_peak_rss_bytes'],wall_s=s['wall_s'],
        map_bolometric_roundoff=roundoff,new_maps=2,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20,baseline_replaced=False,
        independent_small_statistic_reduction=True,large_fields_recomputed_on_mac=False,native_identity_batch_receipt_verified=True,
        strict_physical_error_bound=False,true_maps_independently_validated=actual['validated'],material_response_not_yet_evaluated=True)
    Path('handoff/evidence/20260930-x20-window-validation-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(actual=actual,wall_s=s['wall_s'],verified_files=len(inventory['files']),receipts=len(peaks)),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);main(p.parse_args().base)
