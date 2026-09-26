"""Independent first real map audit for the frozen heating projection; no feedback verdict."""
import argparse,json,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_step21_control_windows as cw
from handoff.audit_tools.review_step21_wide_validation import audit_maps
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close,guarded_ratio
read,digest,arrays=cw.read,cw.digest,cw.arrays


def review(archive,receipt,received,prior,scan,reference,physical_old,accepted,output):
    inventory=cw.receive(archive,receipt,received)
    # 独立绑定原来源包，不仅相信已解包目录的自报SHA。
    for folder,audit_name in [(prior,'20260925-wide-validation-complete-review'),(scan,'20260926-heating-projection-review')]:
        c=read(Path('handoff/evidence')/(audit_name+'.json'))['archive'];original=archive.parent/Path(c['path']).name
        assert digest(original)==c['sha256'] and original.stat().st_size==c['size_bytes']
        with tarfile.open(original) as t:
            source_inv=json.load(t.extractfile('ARCHIVE_MANIFEST.json'))
            for item in source_inv['files']:
                f=folder/item['path'];assert f.stat().st_size==item['size_bytes'] and digest(f)==item['sha256']
    out=received;d=read(out/'declaration.json');s=read(out/'status.json');v=read(out/'control/validation.json')
    assert s['accepted_outer_steps']==20 and s['new_material_steps']==0
    assert (d['maximum_maps'],d['maximum_feedback_pairs'],d['cadence'])==(10,2,[2,10])
    assert not d['automatic_promotion'] and not d['baseline_replacement_authorized'] and not d['physical_dt_changed']
    prior_scan=read(scan/'declaration.json');pred=read(scan/'prediction.json')
    assert d['source_scan']=='outputs/hpc/step21-heating-projection-20260926'
    assert d['source_control']=='outputs/hpc/step21-wide-plane-validation-20260925'
    assert d['basis']==prior_scan['basis'] and d['prediction']==pred and d['uv']==prior_scan['uv']
    assert all(pred['gates'].values()) and pred['eligible_for_independent_review']
    rows=read(prior/'control/state.json')['history'];assert len(rows)==11
    ret={n:read(prior/f'control/endpoints-map{n:02d}/manifest.json') for n in (3,11)}
    expected=[ret[3]['endpoints']['previous'],ret[11]['endpoints']['previous'],ret[11]['endpoints']['previous'],
              ret[3]['endpoints']['final'],ret[11]['endpoints']['final'],ret[11]['endpoints']['final']]
    assert expected==d['basis'] and [x['sha256'] for x in expected]==[rows[i]['input_sha256'] for i in (1,9,9,2,10,10)]
    assert d['latest_actual_residual']==rows[-1]['residual']
    claims={(c['path'],c['size_bytes'],c['sha256']) for c in d['claims']}
    for c in prior_scan['claims']+prior_scan['code']:assert (c['path'],c['size_bytes'],c['sha256']) in claims
    for c in d['code']:
        p=Path(c['path']);assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    for c in d['cases']['control'].values():
        p=out/'inputs'/Path(c['path']).name;assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    heat=out/'inputs/heating_reference.json'
    assert read(heat)==d['heating_reference'] and any(c['sha256']==digest(heat) and c['path'].endswith('/heating_reference.json') for c in d['claims'])
    trial=arrays(out/'control/trial_material.npz');base=arrays(reference/'outer_base_material.npz');accepted_trial=arrays(accepted/'trial_material.npz')
    assert (out/'control/trial_material.npz').read_bytes()==(prior/'control/trial_material.npz').read_bytes()==(out/'inputs/trial_material.npz').read_bytes()
    assert set(trial)==set(base) and all(np.array_equal(trial[k],base[k]) for k in trial)
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[k],accepted_trial[k])
    r=np.load(reference/'base_residual.npy',allow_pickle=False)
    assert np.array_equal(r,arrays(accepted/'common-feedback/final_response.npz')['residual'])
    old=arrays(physical_old);phase=int(trial['phase_index'])
    assert float(trial['step_duration_s'])==float(old['step_duration_s'][phase]) and np.array_equal(trial['density_g_cm3'],old['density_g_cm3'][phase])
    source_protocol=read(prior/'control/pair11/feedback_protocol.json')
    for key in ('outer_base_material','base_residual','physical_old_time_level'):
        c=source_protocol['sources'][key];f=physical_old if key=='physical_old_time_level' else reference/(key+Path(c['path']).suffix)
        assert digest(f)==c['sha256'] and f.stat().st_size==c['size_bytes']
    state=read(out/'control/state.json');cfg=read(out/'control/config.json')
    assert len(state['history'])==1 and state['history'][0]==v['actual_map']
    assert digest(out/'control/trial_material.npz')==state['trial_sha256']
    assert cfg['workers']==16 and cfg['maximum_maps']==10 and cfg['radiation_threshold']==1e-4
    assert cfg['warm_seed']==v['candidate'] and v['candidate']['sha256']==v['actual_map']['input_sha256'] and v['candidate']['size_bytes']==10099884032
    assert v['selected']==d['selected']=='frozen-heating-projection' and v['effective_uv']==d['uv']
    assert v['parent_peak_rss_bytes']<6*1024**3 and np.isfinite(v['minimum_candidate']) and v['minimum_candidate']>=0 and not v['accepted_material_step']
    maps,peaks=audit_maps(out);m=maps[0];f=v['field_comparison'];slabs=f['slabs']
    assert [(x['start'],x['stop']) for x in slabs]==[(i,i+16) for i in range(0,9632,16)]
    for x in slabs:
        assert all(np.isfinite(y) and y>=0 for y in x.values())
        assert_close(x['error_relative_to_local_field'],guarded_ratio(x['error_max'],x['field_scale']))
    err=max(x['error_max'] for x in slabs);scale=max(x['field_scale'] for x in slabs);change=max(x['actual_change_max'] for x in slabs)
    e=guarded_ratio(err,scale);z=guarded_ratio(err,change)
    assert_close(e,f['max_error_over_field']);assert_close(z,f['max_error_over_actual_change'])
    assert_close(m['residual'],f['actual_global_residual']);assert f['full_intensity_prediction_error_evaluated']
    for key in ('l2_error_over_actual_field','l2_error_over_actual_change'):assert np.isfinite(f[key]) and f[key]>=0
    ratio=m['residual']/d['latest_actual_residual']
    checks=dict(actual_maximum_norm_improves=ratio<.99,actual_boundary_spectrum_pass=m['boundary_l1']<1e-3,
        actual_boundary_bolometric_pass=m['boundary_bolometric']<1e-3,worker_memory_pass=v['actual_map']['maximum_worker_rss_mib']<6144,
        strict_inner_pass=0<=m['residual']<1e-4,full_field_prediction_error_small=0<=e<1e-7,prediction_error_below_tenth_actual_change=0<=z<.1)
    assert checks==v['checks'] and v['validated']==all(checks.values())
    assert inventory['stage']=='true-map-validation'
    report=dict(archive=read(receipt),verified_files=len(inventory['files']),verified_code_claims=len(d['code']),map_process_receipts=76,
        actual_map=m,actual_over_77371_map11=ratio,prediction_error_over_global_field=e,prediction_error_over_actual_change=z,
        worst_local_slab=max(slabs,key=lambda x:x['error_relative_to_local_field']),checks=checks,
        maximum_proc_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,feedback_audited=False,
        thermal_reference_values_independently_recomputed=False,full_large_fields_recomputed_on_mac=False,full_field_l2_recomputed_on_mac=False,
        material_ode_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    ax[0].bar(['Actual radiation'],[ratio]);ax[0].axhline(.99,color='black',ls='--');ax[0].set(ylabel='Residual / 77371 map11')
    ax[1].plot([x['start'] for x in slabs],[x['error_relative_to_local_field'] for x in slabs]);ax[1].set(xlabel='Frequency slab start',ylabel='Prediction error / local field')
    fig.suptitle('One real map validated; actual heating not yet audited');fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','receipt','received','prior','scan','reference','physical-old','accepted','output'):p.add_argument('--'+n,type=Path,required=True)
    print(json.dumps(review(**vars(p.parse_args())),indent=2))
