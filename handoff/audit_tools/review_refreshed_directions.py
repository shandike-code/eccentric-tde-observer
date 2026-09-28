"""Audit 78950 paired material directions; independent full-vector signal reduction.

Adapted endpoint/map checks from review_step21_control_windows. Original gate
kernels are reused explicitly; production response_measurement is never called.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tarfile
import numpy as np
from handoff.audit_tools import review_step21_control_windows as cw
from operations.common_feedback_bridge import state_checks
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms,trial_feedback_pair_diagnostics,trial_feedback_pair_gate_checks
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec,ground_state_material_trial_within_trust_region
from eccentric_tde_observer.radiation_matter_feedback import ground_state_material_specific_energy_erg_g
from scripts import phase7b9_formal_feedback_pair_adapter as pair
read,digest,arrays,metrics=cw.read,cw.digest,cw.arrays,cw.metrics
NAMES=('control','thermal','population')

def audit_pair(out,n,reference,physical_old,input_trial,child="control"):
    assert child in ('control','thermal','population')
    peaks=[];formal='source_formal_heating_erg_s_cm3'
    folder=out/child/f'pair{n:02d}';p=read(folder/'feedback_protocol.json');s=read(folder/('baseline_summary.json' if child=='control' else 'feedback_summary.json'));post=read(folder/'postcheck.json')
    assert digest(folder/'feedback_protocol.json')==s['protocol_sha256']
    assert 'reuse_completed_feedback_manifests' not in p['configuration']
    for key in ('outer_base_material','physical_old_time_level','base_residual'):
        c=p['sources'][key];f=physical_old if key=='physical_old_time_level' else reference/(key+Path(c['path']).suffix);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    t=arrays(out/child/'trial_material.npz');assert digest(out/child/'trial_material.npz')==p['sources']['trial_material']['sha256'];base=arrays(reference/'outer_base_material.npz');old=arrays(physical_old);r=np.load(reference/'base_residual.npy',allow_pickle=False)
    # 只投影候选位移；全部四分量反馈与残差保留，原r20不变。
    direction=r.copy().reshape(128,4)
    if child=='thermal':direction[:,1:]=0
    if child=='population':direction[:,0]=0
    direction=direction.ravel();alpha=0. if child=='control' else 1/256
    assert np.array_equal(t['base_encoded_state'],base['encoded_state']) and np.array_equal(t['base_residual'],r)
    assert np.array_equal(t['finite_direction'],direction) and float(t['relaxation'])==alpha
    assert np.array_equal(t['encoded_state'],base['encoded_state']+alpha*direction)
    if child=='control':assert set(t)==set(base) and all(np.array_equal(t[k],base[k]) for k in t)
    decoded=GroundStateLogSimplexCodec(128).decode(t['encoded_state'])
    # 只容许跨CPU指数/softmax的8个机器epsilon；字节/向量身份与科学门不放宽。
    for key in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        np.testing.assert_allclose(t[key],getattr(decoded,key),rtol=8*np.finfo(float).eps,atol=0)

    assert ground_state_material_trial_within_trust_region(GroundStateLogSimplexCodec(128),base['encoded_state'],t['encoded_state'],maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,maximum_population_fraction_change=.05)
    state=read(out/child/'state.json');assert n<=len(state['history'])<=16 and state['active_map'] is None
    rows=state['history'][n-2:n]
    retained=read(out/child/f'endpoints-map{n:02d}/manifest.json')
    assert retained['history_rows']==rows
    for e in ('previous','final'):assert p['sources'][e+'_radiation']==retained['endpoints'][e]
    assert digest(input_trial)==digest(out/child/'trial_material.npz')
    assert rows[0]['output_sha256']==rows[1]['input_sha256']
    for e,row in zip(('previous','final'),rows):
        assert p['sources'][e+'_radiation']['sha256']==row['input_sha256']
        for key,field in [('global_original_operator_residual','residual'),('boundary_spectrum_l1','boundary_l1'),('boundary_bolometric_fraction','boundary_bolometric')]:assert p['configuration'][e+'_'+key]==row[field]
    mass=old['cell_mass_g_cm2'];phase=int(t['phase_index']);assert float(t['step_duration_s'])==float(old['step_duration_s'][phase]) and np.array_equal(t['density_g_cm3'],old['density_g_cm3'][phase])
    feedbacks={};vectors={};ends={};responses={};codec=GroundStateLogSimplexCodec(128)
    for label in ('previous','final'):
        m=read(folder/f'feedback/{label}_manifest.json');fb=arrays(folder/f'{label}_feedback.npz')
        assert m['status']=='complete' and m['state_gate_passed'] and m['protocol_sha256']==s['protocol_sha256']
        assert m['feedback_artifact_sha256']==digest(folder/f'{label}_feedback.npz') and m['state_sha256']==p['sources'][label+'_radiation']['sha256']
        assert [v['block_index'] for v in m['completed_blocks']]==list(range(76))
        total={};ownership=np.zeros(9632,int);maxproc=0
        for row in m['completed_blocks']:
            i=row['block_index'];work=folder/f'feedback/{label}';a=arrays(work/f'block{i:02d}.npz');raw=arrays(work/f'block{i:02d}.legacy.npz');common=arrays(work/f'block{i:02d}.common.npz')
            assert digest(work/f'block{i:02d}.npz')==row['partial_sha256']
            for name in ('legacy_partial','legacy_report','common_arrays'):
                c=row[name];f=work/Path(c['path']).name;assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
            assert set(a)==set(raw) and all(np.array_equal(v,common['common_formal_erg_s_cm3'] if k==formal else raw[k]) for k,v in a.items())
            assert all(np.isfinite(v).all() for d in (a,raw,common) for v in d.values())
            ownership[row['core_group_start']:row['core_group_stop']]+=1
            if not total:total={k:np.zeros_like(v) for k,v in a.items()}
            for k in a:total[k]+=a[k]
            qs=list(work.glob(f'block{i:02d}.process-*.json'));assert len(qs)==1;q=read(qs[0])
            assert q['returncode']==0 and q['memory_guard_passed'] and q['native_observed_peak_kib']<6144*1024
            peaks.append(q['native_observed_peak_kib']);maxproc=max(maxproc,q['native_observed_peak_kib'])
        for k,v in total.items():
            assert np.array_equal(v,fb[k]);parent=v.reshape(256,16,*v.shape[1:]).mean(axis=1)
            assert np.array_equal(parent,fb['parent_'+k]) and np.array_equal(parent[:128],fb['half_'+k])
        checks,*_=state_checks(fb,m['completed_blocks'],ownership,m['accumulated_wall_runtime_s'],m['maximum_process_peak_rss_mib'],p['formal_state_gates'])
        assert all(checks.values()) and checks==post['responses'][label]['full_state_checks']
        book=arrays(folder/f'{label}_energy_ledger.npz');response=arrays(folder/f'{label}_response.npz')
        assert all(np.isfinite(v).all() for d in (fb,book,response) for v in d.values()) and np.all(book['remaining']>0)
        assert np.array_equal(book['old_h'],old['hydrogen_fraction'][phase]) and np.array_equal(book['old_he'],old['helium_fraction'][phase])
        old_energy=ground_state_material_specific_energy_erg_g(old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
        np.testing.assert_allclose(book['total_old'],old_energy,rtol=1e-12,atol=0)
        assert np.array_equal(book['gas_old']+book['ion_old'],book['total_old'])
        assert np.array_equal(book['target']-book['ion_new'],book['remaining'])
        assert np.array_equal(book['total_old']+float(t['step_duration_s'])*fb['half_atomic_rate_heating_erg_s_cm3']/t['density_g_cm3'],book['target'])
        for k,v in [('target',response['target_specific_material_energy_erg_g']),('new_h',response['hydrogen_fraction']),('new_he',response['helium_fraction'])]:np.testing.assert_allclose(book[k],v,rtol=1e-12,atol=0)
        encoded=codec.encode(response['temperature_k'],response['hydrogen_fraction'],response['helium_fraction'])
        np.testing.assert_allclose(encoded-t['encoded_state'],response['residual'],rtol=1e-10,atol=2e-14)
        norms=asdict(encoded_residual_norms(response['residual'],mass))
        for k,v in norms.items():assert np.isclose(v,post['responses'][label]['norms'][k],rtol=1e-12,atol=0)
        vectors[label]=response['residual'];feedbacks[label]=fb;responses[label]=response
        ends[label]={'norms':norms,'minimum_gas_erg_g':float(book['remaining'].min()),'maximum_proc_kib':maxproc,
            'source':metrics(fb['atomic_rate_heating_erg_s_cm3'],fb[formal],fb['subcell_width_cm'])}
    assert not s.get('material_response_failures')
    if child=='control':
        comparison=pair._feedback_stability_comparison(feedbacks['previous'],feedbacks['final'])
        checks=pair._feedback_stability_gate_checks(comparison,p['acceptance_gates'])
        checks.update(inner_pair_ready=all(0<=row['residual']<1e-4 and 0<=row['boundary_l1']<1e-3 and 0<=row['boundary_bolometric']<1e-3 for row in rows),physical_response_pass=True)
        assert checks==s['gate_checks'] and len(checks)==7 and all(checks.values())
        assert s['decision']['baseline_control_only'] and not s['decision']['finite_trial_accepted_as_one_nonlinear_step']
        for key in ('accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass','accept_finite_trial_only_if_all_acceptance_gates_pass','accept_material_step'):
            assert p['authorization'][key] is False
        assert p['authorization']['zero_displacement_control'] is True
    else:
        pair._require_exact_acceptance_gates({'gates':p['acceptance_gates'],'authorization':p['authorization']})
        d=trial_feedback_pair_diagnostics(previous_feedback=feedbacks['previous'],final_feedback=feedbacks['final'],
            previous_encoded_residual=vectors['previous'],final_encoded_residual=vectors['final'],base_encoded_residual=r,
            cell_width=feedbacks['final']['subcell_width_cm'],cell_mass=mass)
        gates=p['acceptance_gates'];checks=trial_feedback_pair_gate_checks(d,gates)
        checks.update(two_formal_feedback_states_pass=True,
            two_inner_radiation_residuals_pass=max(row['residual'] for row in rows)<gates['each_global_original_operator_residual_below'],
            two_boundary_spectra_pass=max(row['boundary_l1'] for row in rows)<gates['each_boundary_spectrum_l1_below'],
            two_boundary_bolometric_pass=max(row['boundary_bolometric'] for row in rows)<gates['each_boundary_bolometric_fraction_below'],
            candidate_state_bytes_pass=True,
            population_nonnegative_pass=bool(min(float(responses[e][k].min()) for e in responses for k in ('hydrogen_fraction','helium_fraction'))>=gates['minimum_population_fraction_at_least']),
            all_residual_components_finite_pass=all(np.isfinite(v).all() for v in vectors.values()))
        assert set(checks)==REQUIRED_GATES and checks==s['gate_checks']
        assert s['decision']['finite_trial_accepted_as_one_nonlinear_step']==all(checks.values())
        comparison={k:getattr(d,k) for k in ('photoionization_volume_l1','total_recombination_volume_l1',
            'atomic_heating_volume_l1','direct_heating_volume_l1','formal_heating_volume_l1','inner_noise_to_trial_signal_l2_ratio')}
    for k,value in comparison.items():np.testing.assert_allclose(value,s['comparison'][k],rtol=1e-12,atol=0)
    assert post['material_step_promoted'] is False and post['accepted_outer_steps_remain']==20
    assert np.array_equal(vectors['final'],np.load(folder/'material_residual.npy',allow_pickle=False))
    return {'endpoints':ends,'comparison':comparison,'gate_checks':checks},vectors,peaks


def audit_maps(out,child):
    folder=out/child;state=read(folder/'state.json');history=state['history']
    assert 1<=len(history)<=16 and state['active_map'] is None
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


def independent_signals(candidate,control,mass,earlier=None):
    if set(candidate)!={'previous','final'} or set(control)!={'previous','final'}:
        raise ValueError('missing endpoint')
    for v in list(candidate.values())+list(control.values()):
        if np.asarray(v).shape!=(4*len(mass),) or not np.isfinite(v).all():raise ValueError('invalid vector')
    signals={a+'_vs_'+b:np.asarray(x)-np.asarray(y) for a,x in candidate.items() for b,y in control.items()}
    norms={k:cw.independent_norms(v,mass) for k,v in signals.items()}
    minimum=np.min(list(norms.values()),axis=0)
    spread=cw.independent_norms(candidate['final']-candidate['previous'],mass)+cw.independent_norms(control['final']-control['previous'],mass)
    ratios=[float(x/y) if y>0 else None for x,y in zip(spread,minimum)]
    report=dict(signal_norms={k:dict(zip(cw.NAMES,v.tolist())) for k,v in norms.items()},
        finite_response_norms={k:dict(zip(cw.NAMES,cw.independent_norms(256*v,mass).tolist())) for k,v in signals.items()},
        minimum_signal_norms=dict(zip(cw.NAMES,minimum.tolist())),endpoint_spread_over_signal=dict(zip(cw.NAMES,ratios)),
        endpoint_signal_resolved=all(x is not None and x<.1 for x in ratios),signal_tolerance=.1,
        strict_error_bound=False,exact_jacobian=False,baseline_replaced=False,material_step_promoted=False)
    if earlier is not None:
        if set(earlier)!=set(signals):raise ValueError('earlier inventory')
        drift=np.max([cw.independent_norms(x-y,mass) for x in signals.values() for y in earlier.values()],axis=0)
        ratios=[float(x/y) if y>0 else None for x,y in zip(drift,minimum)]
        report.update(eight_map_signal_drift_over_signal=dict(zip(cw.NAMES,ratios)),
            eight_map_signal_persistent=all(x is not None and x<.1 for x in ratios))
    return report,signals


def same_record(actual,saved):
    """Compare scalars recursively without treating null as a small positive floor."""
    if isinstance(actual,dict):
        assert set(actual)==set(saved)
        for k in actual:same_record(actual[k],saved[k])
    elif isinstance(actual,(list,tuple)):
        assert len(actual)==len(saved)
        for a,b in zip(actual,saved):same_record(a,b)
    elif actual is None or isinstance(actual,(bool,str)):
        assert actual==saved and type(actual) is type(saved)
    else:
        assert np.isfinite(actual) and np.isfinite(saved)
        np.testing.assert_allclose(actual,saved,rtol=1e-12,atol=0)


def independent_cross(candidate,control,mass):
    ratios={}
    for a,x in candidate.items():
        for b,y in control.items():
            denom=cw.independent_norms(y,mass)
            if np.any(denom<=0):raise ValueError('zero control norm')
            ratios[a+'_vs_'+b]=dict(zip(cw.NAMES,(cw.independent_norms(x,mass)/denom).tolist()))
    return dict(ratios=ratios,passed=all(v<1 for row in ratios.values() for v in row.values()))


def verify_plan(d,seed):
    assert d['source_job']==78594 and d['source']=='outputs/hpc/step21-stationarity-confirmation-20260927'
    assert d['seed']==seed and d['maximum_maps']==48 and d['maximum_feedback_pairs']==6
    assert d['limits']==dict(control=16,thermal=16,population=16) and d['cadence']==[8,16]
    assert d['case_order']==list(NAMES) and set(d['cases'])==set(NAMES)
    assert d['amplitudes']==dict(control=0.,thermal=1/256,population=1/256)
    assert d['matched_initial_radiation'] and d['signal_tolerance']==.1 and d['control_window_tolerance']==.001
    assert d['accepted_outer_steps']==20
    assert not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed'))


def verify_claim(c,path):
    assert path.stat().st_size==c['size_bytes'] and digest(path)==c['sha256']


def review(archive,receipt,received,source,reference,physical_old,accepted,output,terminal=None):
    manifest=cw.receive(archive,receipt,received);out=received;d=read(out/'declaration.json')
    source_audit=read(Path('handoff/evidence/20260928-stationarity-complete-review.json'))
    assert source_audit['job_id']==78594 and source_audit['final_summary_present']
    old_archive=archive.parent/Path(source_audit['archive']['path']).name
    verify_claim(source_audit['archive'],old_archive)
    with tarfile.open(old_archive) as t:
        assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(source/'ARCHIVE_MANIFEST.json')
    cw.verified_inventory(source)
    seed=read(source/'control/endpoints-map16/manifest.json')['endpoints']['mapped_final'];verify_plan(d,seed)
    status=read(out/'status.json');assert status['accepted_outer_steps']==20 and status['new_material_steps']==0
    for c in d['code']:verify_claim(c,Path(c['path']))
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r=np.load(reference/'base_residual.npy',allow_pickle=False)
    base=arrays(reference/'outer_base_material.npz');x20=arrays(accepted/'trial_material.npz')
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[k],x20[k])
    assert np.array_equal(r,arrays(accepted/'common-feedback/final_response.npz')['residual'])
    zero=read(source/'control/pair16/feedback_protocol.json')
    source_vectors={e:arrays(source/f'control/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    previous_control=source_vectors;controls={};signals={};maps={};peaks=[];results={};map_receipts=0;fb_receipts=0
    for name in NAMES:
        for c in d['cases'][name].values():verify_claim(c,out/'inputs'/name/Path(c['path']).name)
        t=arrays(out/'inputs'/name/'trial_material.npz');direction=r.copy().reshape(128,4)
        if name=='thermal':direction[:,1:]=0
        if name=='population':direction[:,0]=0
        alpha=0 if name=='control' else 1/256
        for k,v in [('base_residual',r),('finite_direction',direction.ravel()),('base_encoded_state',base['encoded_state']),
                ('encoded_state',base['encoded_state']+alpha*direction.ravel())]:assert np.array_equal(t[k],v)
        assert float(t['relaxation'])==alpha
        decoded=GroundStateLogSimplexCodec(128).decode(t['encoded_state'])
        for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
            np.testing.assert_allclose(t[k],getattr(decoded,k),rtol=8*np.finfo(float).eps,atol=0)
        for k in ('density_g_cm3','phase_index','step_duration_s'):assert np.array_equal(t[k],base[k])
        if not (out/name/'state.json').exists():continue
        cfg=read(out/name/'config.json');state=read(out/name/'state.json')
        assert cfg['warm_seed']==seed and cfg['workers']==16 and cfg['maximum_maps']==16 and cfg['radiation_threshold']==1e-4
        assert state['history'][0]['input_sha256']==seed['sha256']
        assert digest(out/name/'trial_material.npz')==digest(out/'inputs'/name/'trial_material.npz')
        maps[name],resources=audit_maps(out,name);peaks+=resources;map_receipts+=len(resources)
    events=[];expected=[(n,name) for n in (8,16) for name in NAMES]
    for n,name in expected:
        folder=out/name/f'pair{n:02d}';dp=folder/'decision.json';missing=out/name/f'inner-not-ready-map{n:02d}.json'
        if not dp.exists():
            if missing.exists():
                row=read(missing);assert row==dict(feedback_evaluated=False,inner_pair_ready=False,promoted=False)
                history=read(out/name/'state.json')['history'];rows=history[n-2:n];assert len(rows)==2
                assert not all(v['residual']<1e-4 and v['boundary_l1']<1e-3 and v['boundary_bolometric']<1e-3 for v in rows)
                results[f'{name}{n:02d}']=row;events.append((n,name))
            continue
        events.append((n,name));p=read(folder/'feedback_protocol.json');decision=read(dp)
        for k in ('acceptance_gates','formal_state_gates'):assert p[k]==zero[k]
        for key,path in [('refreshed_direction_declaration',out/'declaration.json'),('retained_manifest',out/name/f'endpoints-map{n:02d}/manifest.json')]:
            verify_claim(p['sources'][key],path)
        for c in p['common_code_claims']:verify_claim(c,Path(c['path']))
        assert decision['feedback_evaluated'] and not decision['promoted'] and not decision['baseline_replaced']
        assert not decision['physical_response_failures'] and decision['parent_peak_rss_bytes']<6*1024**3
        report,vectors,resources=audit_pair(out,n,reference,physical_old,out/'inputs'/name/'trial_material.npz',name)
        peaks+=resources;fb_receipts+=len(resources);assert decision['original_gates']==report['gate_checks']
        if name=='control':
            window=cw.recompute_window(vectors,previous_control,r,mass);total=cw.recompute_window(vectors,source_vectors,r,mass)
            cw.verify_window(window,decision['window_comparison']);cw.verify_window(total,decision['from_78594_comparison'])
            assert decision['zero_control_stable']==all(report['gate_checks'].values())
            passed=all(report['gate_checks'].values()) and window['passed'] and total['passed']
            assert decision['control_pass']==passed
            report.update(window=window,cumulative=total,control_pass=passed)
            controls[n]=vectors;previous_control=vectors
        else:
            assert results[f'control{n:02d}']['control_pass']
            measure,vec=independent_signals(vectors,controls[n],mass,signals.get(name))
            same_record(measure,decision['response_measurement']);saved=arrays(folder/'direction_response_vectors.npz')
            assert set(saved)==set(vec) and all(np.array_equal(saved[k],vec[k]) for k in vec)
            cross=independent_cross(vectors,controls[n],mass);same_record(cross,decision['fresh_baseline_comparison'])
            assert decision['all_16_pair_gates']==all(report['gate_checks'].values())
            report.update(response_measurement=measure,fresh_baseline_comparison=cross)
            signals[name]=vec
        results[f'{name}{n:02d}']=report
    assert events and events==expected[:len(events)]
    complete=(out/'summary.json').exists()
    if complete:
        assert terminal is not None;term=read(terminal)
        assert term['job_id']==78950 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
        s=read(out/'summary.json');assert s['status']==status['status']
        assert s['maps']==sum(len(v) for v in maps.values())<=48 and s['accepted_outer_steps']==20 and s['new_material_steps']==0
        assert not s['baseline_replaced'] and not s['strict_error_bound']
        for n,name in events:
            dp=out/name/f'pair{n:02d}/decision.json';fp=dp if dp.exists() else out/name/f'inner-not-ready-map{n:02d}.json'
            assert s['cases'][name][str(n)]==read(fp)
        if s['status']=='refreshed_direction_measurement_requires_review':assert events==expected
        elif s['status'].startswith('stopped_at_control_map'):
            n=int(s['status'].rsplit('map',1)[1]);assert events[-1]==(n,'control') and not results[f'control{n:02d}']['control_pass']
        else:raise AssertionError('physical/code/resource failure requires dedicated failure audit')
    result=dict(job_id=78950,archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
        maps=maps,pairs=results,events=events,final_summary_present=complete,map_process_receipts=map_receipts,
        feedback_process_receipts=fb_receipts,maximum_proc_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,
        baseline_replaced=False,strict_error_bound=False,production_signal_reducer_reused=False,
        original_gate_kernels_reused=True,material_ode_recomputed_on_mac=False,full_large_fields_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    for i,metric in enumerate(cw.NAMES):
        ax.plot(range(len(results)),[v['endpoints']['final']['norms'][metric]/cw.independent_norms(r,mass)[i] if 'endpoints' in v else np.nan for v in results.values()], 'o-',label=metric)
    ax.set_xticks(range(len(results)),list(results));ax.axhline(1,color='black',ls='--')
    ax.set(ylabel='Residual norm / original r20 norm',title='Finite direction diagnostics; no material promotion');ax.legend()
    fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','source','reference','physical-old','accepted','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--terminal',type=Path);r=review(**vars(p.parse_args()))
    print(json.dumps({k:r[k] for k in ('verified_files','events','map_process_receipts','feedback_process_receipts','maximum_proc_kib')},indent=2))
