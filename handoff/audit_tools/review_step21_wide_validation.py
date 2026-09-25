"""Audit six-state true-map evidence and optional fixed-matter feedback windows."""
import argparse
import csv
import json
import math
import tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_step21_control_windows as cw
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close,guarded_ratio
read,digest,arrays=cw.read,cw.digest,cw.arrays


def field_checks(v,aggregate,latest):
    f=v['field_comparison'];slabs=f['slabs']
    assert [(q['start'],q['stop']) for q in slabs]==[(i,i+16) for i in range(0,9632,16)]
    for q in slabs:
        assert all(np.isfinite(x) and x>=0 for x in q.values())
        assert_close(q['error_relative_to_local_field'],guarded_ratio(q['error_max'],q['field_scale']))
    e=max(q['error_max'] for q in slabs);z=max(q['field_scale'] for q in slabs);delta=max(q['actual_change_max'] for q in slabs)
    assert_close(guarded_ratio(e,z),f['max_error_over_field']);assert_close(guarded_ratio(e,delta),f['max_error_over_actual_change'])
    assert_close(f['actual_global_residual'],aggregate['residual']);assert f['full_intensity_prediction_error_evaluated']
    for k in ('l2_error_over_actual_field','l2_error_over_actual_change'):assert np.isfinite(f[k]) and f[k]>=0
    # 工件没有逐片平方和，不能从极值重建L2；仅保留有来源的记录，明确不独立核验该两项。
    checks=dict(actual_maximum_norm_improves=aggregate['residual']/latest<.99,
        actual_boundary_spectrum_pass=aggregate['boundary_l1']<1e-3,actual_boundary_bolometric_pass=aggregate['boundary_bolometric']<1e-3,
        worker_memory_pass=v['actual_map']['maximum_worker_rss_mib']<6144,strict_inner_pass=0<=aggregate['residual']<1e-4,
        full_field_prediction_error_small=0<=guarded_ratio(e,z)<1e-7,
        prediction_error_below_tenth_actual_change=0<=guarded_ratio(e,delta)<.1,actual_cost_gain_pass=aggregate['residual']/latest<.8)
    assert checks==v['checks'] and v['validated']==all(checks.values())
    worst=max(slabs,key=lambda q:q['error_relative_to_local_field'])
    return dict(actual_over_prior=aggregate['residual']/latest,prediction_error_over_field=guarded_ratio(e,z),
        prediction_error_over_actual_change=guarded_ratio(e,delta),worst_slab=worst,checks=checks,
        full_field_l2_recomputed_on_mac=False)


def verify_basis(plan,scan,prior):
    s=read(scan/'declaration.json');prediction=read(scan/'prediction.json');name=plan['selected']
    assert name=='x6-x14-x15' and plan['basis']==s['cases'][name]['basis'] and plan['prediction']==prediction[name]
    rows=read(prior/'control/state.json')['history'];assert len(rows)==16
    ret={n:read(prior/f'control/endpoints-map{n:02d}/manifest.json') for n in (8,16)}
    expected=[ret[8]['endpoints']['previous'],ret[16]['endpoints']['previous'],ret[16]['endpoints']['final'],
              ret[8]['endpoints']['final'],ret[16]['endpoints']['final'],ret[16]['endpoints']['mapped_final']]
    assert plan['basis']==expected
    assert [c['sha256'] for c in expected]==[rows[i]['input_sha256'] if i<16 else rows[-1]['output_sha256'] for i in (6,14,15,7,15,16)]
    assert plan['latest_actual_residual']==rows[-1]['residual']
    assert prediction[name]['feasible'] and prediction[name]['cost_eligible']
    assert all(prediction[name]['rounds'][-1]['result']['gates'].values())
    return prediction[name]['rounds'][-1]['result']


def audit_maps(out):
    folder=out/'control';state=read(folder/'state.json');history=state['history']
    assert 1<=len(history)<=11 and state['active_map'] is None
    assert [r['iteration'] for r in history]==list(range(1,len(history)+1))
    assert all(a['output_sha256']==b['input_sha256'] for a,b in zip(history,history[1:]))
    assert digest(folder/'config.json')==state['config_sha256'] and read(folder/'initialized_identity.json')['passed']
    reports=[];peaks=[]
    for row in history:
        work=folder/f"map{row['iteration']:04d}";rows=[read(work/f'block{i:02d}.json') for i in range(76)]
        assert len({b['protocol_sha256'] for b in rows})==1
        ownership=np.zeros(9632,int)
        for i,b in enumerate(rows):
            assert b['block_index']==i and b['input_state_sha256']==row['input_sha256']
            assert b['minimum_input_intensity']>=0 and b['minimum_mapped_intensity']>=0
            assert all(np.isfinite(v) for v in b.values() if isinstance(v,(float,int))) and b['peak_process_rss_mib']<6144
            lo,hi=b['core_group_start'],b['core_group_stop'];assert 0<=lo<hi<=9632;ownership[lo:hi]+=1
            files=list(work.glob(f'block{i:02d}.process-*.json'));assert len(files)==1
            q=read(files[0]);assert q['returncode']==0 and q['memory_guard_passed'] and q['native_observed_peak_kib']<6144*1024
            peaks.append(q['native_observed_peak_kib'])
        assert np.all(ownership==1)
        assert row['maximum_worker_rss_mib']==max(b['peak_process_rss_mib'] for b in rows)
        scale=max(b['maximum_radiation_scale'] for b in rows);assert scale>0
        residual=max(b['maximum_absolute_radiation_change'] for b in rows)/scale
        l1=sum(b['boundary_spectrum_l1_numerator'] for b in rows)/max(sum(b['current_boundary_absolute_scale'] for b in rows),sum(b['mapped_boundary_absolute_scale'] for b in rows))
        before=sum(b['current_boundary_bolometric'] for b in rows);after=sum(b['mapped_boundary_bolometric'] for b in rows)
        bol=abs(after-before)/max(abs(before),abs(after))
        for k,v in [('residual',residual),('boundary_l1',l1),('boundary_bolometric',bol)]:assert v==row[k]
        worst=max(rows,key=lambda b:b['block_relative_radiation_change'])
        reports.append({'iteration':row['iteration'],'residual':residual,'boundary_l1':l1,'boundary_bolometric':bol,
                        'worst_self_scaled_block':worst['block_index'],'worst_self_scaled_change':worst['block_relative_radiation_change'],'wall_s':row['wall_s']})
    return reports,peaks


def review(archive,receipt,received,prior,scan,reference,physical_old,prior_confirmed,output):
    manifest=cw.receive(archive,receipt,received)
    for directory,report_path in [(prior,Path('handoff/evidence/20260925-control-recovery-complete-review.json')),(scan,Path('handoff/evidence/20260925-wide-plane-review.json'))]:
        c=read(report_path)['archive'];original=archive.parent/Path(c['path']).name
        assert digest(original)==c['sha256'] and original.stat().st_size==c['size_bytes']
        with tarfile.open(original) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(directory/'ARCHIVE_MANIFEST.json')
        cw.verified_inventory(directory)
    out=received;d=read(out/'declaration.json');status=read(out/'status.json');folder=out/'control';v=read(folder/'validation.json')
    assert status['accepted_outer_steps']==20 and status['new_material_steps']==0
    assert (d['maximum_maps'],d['maximum_feedback_pairs'],d['cadence'],d['accepted_outer_steps'])==(11,2,[3,11],20)
    assert d['automatic_promotion'] is False and d['baseline_replacement_authorized'] is False and d['physical_dt_changed'] is False
    assert set(d['cases'])=={'control'}
    prediction=verify_basis(d,scan,prior)
    claims={(c['path'],c['size_bytes'],c['sha256']) for c in d['claims']}
    for c in read(scan/'declaration.json')['claims']+read(scan/'declaration.json')['code']:
        assert (c['path'],c['size_bytes'],c['sha256']) in claims
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    for c in d['cases']['control'].values():
        f=out/'inputs'/Path(c['path']).name;assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    trial=arrays(folder/'trial_material.npz');base=arrays(reference/'outer_base_material.npz');accepted=arrays(prior_confirmed/'trial_material.npz')
    assert (folder/'trial_material.npz').read_bytes()==(prior/'control/trial_material.npz').read_bytes()==(out/'inputs/trial_material.npz').read_bytes()
    assert set(trial)==set(base) and all(np.array_equal(trial[k],base[k]) for k in trial)
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[k],accepted[k])
    r=np.load(reference/'base_residual.npy',allow_pickle=False);assert np.array_equal(r,arrays(prior_confirmed/'common-feedback/final_response.npz')['residual'])
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];phase=int(trial['phase_index'])
    assert float(trial['step_duration_s'])==float(old['step_duration_s'][phase]) and np.array_equal(trial['density_g_cm3'],old['density_g_cm3'][phase])
    state=read(folder/'state.json');cfg=read(folder/'config.json');assert state['history'][0]==v['actual_map']
    assert digest(folder/'trial_material.npz')==state['trial_sha256']
    assert cfg['workers']==16 and cfg['maximum_maps']==11 and cfg['radiation_threshold']==1e-4
    assert cfg['warm_seed']==v['candidate'] and v['candidate']['sha256']==v['actual_map']['input_sha256'] and v['candidate']['size_bytes']==10099884032
    assert v['selected']==d['selected'] and v['effective_uv']==prediction['uv']
    assert v['parent_peak_rss_bytes']<6*1024**3 and v['minimum_candidate']>=0 and v['accepted_material_step'] is False
    maps,peaks=audit_maps(out);field=field_checks(v,maps[0],d['latest_actual_residual'])
    if not all(field['checks'].values()):assert len(maps)==1
    if len(maps)>1:assert all(field['checks'].values())
    source_protocol=read(prior/'control/pair16/feedback_protocol.json')
    for key in ('outer_base_material','base_residual','physical_old_time_level'):
        c=source_protocol['sources'][key];f=physical_old if key=='physical_old_time_level' else reference/(key+Path(c['path']).suffix)
        assert digest(f)==c['sha256'] and f.stat().st_size==c['size_bytes']
    origin={e:arrays(prior/f'control/pair16/{e}_response.npz')['residual'] for e in ('previous','final')};previous=origin
    selected=[n for n in (3,11) if (folder/f'pair{n:02d}/decision.json').exists()];reports={};feedback_count=0
    assert selected in ([],[3],[3,11])
    for n in selected:
        rd=folder/f'pair{n:02d}';p=read(rd/'feedback_protocol.json');decision=read(rd/'decision.json')
        assert p['acceptance_gates']==source_protocol['acceptance_gates'] and p['formal_state_gates']==source_protocol['formal_state_gates']
        assert p['outer_iteration']==source_protocol['outer_iteration']
        assert p['sources']['control_window_declaration']['sha256']==digest(out/'declaration.json')
        assert p['sources']['wide_plane_validation']['sha256']==digest(folder/'validation.json')
        assert p['sources']['retained_manifest']['sha256']==digest(folder/f'endpoints-map{n:02d}/manifest.json')
        assert p['numerical_backtracking']==dict(alpha=0.,fixed_base_accepted_index=20,direction_family='control',diagnostic_only=True,physical_time_advanced=False)
        for c in p['common_code_claims']:
            f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
        report,vectors,resources=cw.audit_pair(out,n,reference,physical_old,out/'inputs/trial_material.npz')
        peaks.extend(resources);feedback_count+=len(resources)
        window=cw.recompute_window(vectors,previous,r,mass);total=cw.recompute_window(vectors,origin,r,mass)
        cw.verify_window(window,decision['window_comparison']);cw.verify_window(total,decision['from_77299_comparison'])
        kind='post_extrapolation_shift' if n==3 else 'eight_map_drift';assert decision['comparison_kind']==kind
        drift=dict(zip(cw.NAMES,cw.independent_norms(vectors['final']-r,mass)))
        for k,x in drift.items():assert_close(x,decision['fresh_control_minus_r20_norms'][k])
        assert decision['feedback_evaluated'] and decision['zero_control_stable'] and decision['original_gates']==report['gate_checks']
        assert decision['baseline_replaced'] is False and decision['promoted'] is False and decision['parent_peak_rss_bytes']<6*1024**3
        reports[str(n)]={**report,'comparison_kind':kind,'window':window,'from_77299':total,'final_minus_r20':drift,
            'adjacent_vector_difference':dict(zip(cw.NAMES,cw.independent_norms(vectors['final']-vectors['previous'],mass)))}
        previous=vectors
    complete=(out/'summary.json').exists()
    if complete:
        summary=read(out/'summary.json');assert summary['accepted_outer_steps']==20 and summary['new_material_steps']==0
        assert summary['baseline_replaced'] is False and summary['strict_error_bound'] is False and summary['maps']==len(maps)
        if summary['status']=='wide_plane_validation_complete_requires_review':assert len(maps)==11 and selected==[3,11]
        elif summary['status']=='true_map_not_validated':assert len(maps)==1 and not all(field['checks'].values()) and not selected
        else:raise AssertionError('stopped feedback needs a dedicated failed-gate audit before scientific conclusions')
        for n in selected:assert summary['cases'][str(n)]==read(folder/f'pair{n:02d}/decision.json')
    else:assert manifest['stage'] in ('true-map-validation','control-map03-feedback','control-map11-feedback')
    result=dict(archive=read(receipt),final_summary_present=complete,verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
        maps=maps,field_validation=field,feedback_rounds=selected,windows=reports,map_process_receipts=76*len(maps),
        feedback_process_receipts=feedback_count,maximum_proc_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,
        full_large_fields_recomputed_on_mac=False,material_ode_recomputed_on_mac=False,full_field_l2_recomputed_on_mac=False,
        production_window_reducer_reused=False,baseline_replaced=False,strict_error_bound=False)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(maps[0]));w.writeheader();w.writerows(maps)
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    ax[0].plot([m['iteration'] for m in maps],[m['residual']/d['latest_actual_residual'] for m in maps],'o-');ax[0].axhline(.8,color='black',ls='--');ax[0].set(xlabel='New map index',ylabel='Actual / source map16 residual')
    slabs=v['field_comparison']['slabs'];ax[1].plot([s['start'] for s in slabs],[s['error_relative_to_local_field'] for s in slabs]);ax[1].set(xlabel='Frequency group start',ylabel='Prediction error / local field scale')
    if selected:
        for i,label in enumerate(cw.NAMES):ax[2].plot(selected,[max(x[i] for x in reports[str(n)]['window']['vector_difference_over_frozen_r20_norms'].values()) for n in selected],'o-',label=label)
        ax[2].axhline(.001,color='black',ls='--');ax[2].legend();ax[2].set(xlabel='3: extrapolation shift; 11: eight-map drift',ylabel='Vector difference / fixed r20 norm')
    else:ax[2].text(.5,.5,'Feedback not yet in this archive',ha='center');ax[2].set_axis_off()
    fig.suptitle('Measured fixed-matter radiation validation; no material acceptance');fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','receipt','received','prior','scan','reference','physical-old','prior-confirmed','output'):p.add_argument('--'+n,type=Path,required=True)
    x=vars(p.parse_args());result=review(**x)
    print(json.dumps({k:result[k] for k in ('verified_files','verified_code_claims','feedback_rounds','field_validation')},indent=2))
