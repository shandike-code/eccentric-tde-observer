"""Independent fixed-x20 long-window audit; no production window reducer imported."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import tarfile
import numpy as np
import matplotlib.pyplot as plt
from operations.review_common_frequency import read,digest,arrays,metrics
from operations.common_feedback_bridge import state_checks
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec,ground_state_material_trial_within_trust_region
from eccentric_tde_observer.radiation_matter_feedback import ground_state_material_specific_energy_erg_g
from scripts import phase7b9_formal_feedback_pair_adapter as pair

NAMES=('l2','mass_weighted','maximum_cell')


def independent_norms(vector,mass):
    """Recompute norms with explicit cell sums; not the production window function."""
    mass=np.asarray(mass,float);v=np.asarray(vector,float)
    if mass.ndim!=1 or v.size!=4*mass.size or not np.isfinite(v).all() or not np.isfinite(mass).all() or np.any(mass<=0):
        raise ValueError('invalid full residual or masses')
    v=v.reshape(-1,4)
    # 全部四分量先在每层求平方和；质量只作用于质量加权范数。
    squares=[math.fsum(float(x)*float(x) for x in row) for row in v]
    result=np.array([math.sqrt(math.fsum(squares)),math.sqrt(math.fsum(float(m)*s for m,s in zip(mass,squares))/math.fsum(mass)),math.sqrt(max(squares))])
    if not np.isfinite(result).all():raise ValueError('nonfinite norm')
    return result


def recompute_window(current,previous,r20,mass):
    if set(current)!={'previous','final'} or set(previous)!={'previous','final'}:raise ValueError('missing endpoint')
    denom=independent_norms(r20,mass)
    if np.any(denom<=0):raise ValueError('zero frozen reference norm')
    # 不相减标量范数、不归一化至新control；方向变化也必须计入。
    values={a+'_vs_'+b:(independent_norms(np.asarray(x)-np.asarray(y),mass)/denom).tolist() for a,x in current.items() for b,y in previous.items()}
    if not np.isfinite(list(values.values())).all():raise ValueError('nonfinite window ratio')
    return {'vector_difference_over_frozen_r20_norms':values,'passed':all(x<1e-3 for row in values.values() for x in row),
            'tolerance':1e-3,'strict_error_bound':False,'baseline_replaced':False}


def verify_window(actual,saved):
    for key in ('passed','tolerance','strict_error_bound','baseline_replaced'):assert actual[key]==saved[key],key
    a=actual['vector_difference_over_frozen_r20_norms'];b=saved['vector_difference_over_frozen_r20_norms']
    assert set(a)==set(b)
    for key in a:np.testing.assert_allclose(a[key],b[key],rtol=1e-12,atol=0)


def verify_declaration(d,seed):
    assert d['maximum_maps']==16 and d['cadence']==[8,16] and d['maximum_feedback_pairs']==2
    assert d['window_tolerance']==1e-3 and d['accepted_outer_steps']==20
    assert d['automatic_promotion'] is False and d['baseline_replacement_authorized'] is False
    assert set(d['cases'])=={'control'} and d['seed']==seed


def verified_inventory(root):
    manifest=read(root/'ARCHIVE_MANIFEST.json');seen=set()
    for c in manifest['files']:
        p=Path(c['path']);assert not p.is_absolute() and '..' not in p.parts and c['path'] not in seen
        seen.add(c['path']);f=root/p;assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert actual==seen|{'ARCHIVE_MANIFEST.json'}
    return manifest


def receive(archive,receipt,out):
    c=read(receipt);assert archive.stat().st_size==c['size_bytes'] and digest(archive)==c['sha256']
    if not out.exists():
        with tarfile.open(archive) as t:
            members=t.getmembers();names=[m.name for m in members]
            assert len(names)==len(set(names)) and all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
            out.mkdir();t.extractall(out,filter='data')
    return verified_inventory(out)


def audit_pair(out,n,reference,physical_old,input_trial):
    child='control';peaks=[];formal='source_formal_heating_erg_s_cm3'
    folder=out/child/f'pair{n:02d}';p=read(folder/'feedback_protocol.json');s=read(folder/'baseline_summary.json');post=read(folder/'postcheck.json')
    assert digest(folder/'feedback_protocol.json')==s['protocol_sha256']
    assert 'reuse_completed_feedback_manifests' not in p['configuration']
    for key in ('outer_base_material','physical_old_time_level','base_residual'):
        c=p['sources'][key];f=physical_old if key=='physical_old_time_level' else reference/(key+Path(c['path']).suffix);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    t=arrays(out/child/'trial_material.npz');assert digest(out/child/'trial_material.npz')==p['sources']['trial_material']['sha256'];base=arrays(reference/'outer_base_material.npz');old=arrays(physical_old);r=np.load(reference/'base_residual.npy',allow_pickle=False)
    # 零位移控制必须逐位保持原基态，残差仍完整保留四分量。
    assert np.array_equal(t['base_encoded_state'],base['encoded_state']) and np.array_equal(t['base_residual'],r) and np.array_equal(t['finite_direction'],r)
    assert float(t['relaxation'])==0 and np.array_equal(t['encoded_state'],base['encoded_state'])
    assert set(t)==set(base) and all(np.array_equal(t[k],base[k]) for k in t)
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
    feedbacks={};vectors={};ends={};codec=GroundStateLogSimplexCodec(128)
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
        vectors[label]=response['residual'];feedbacks[label]=fb
        ends[label]={'norms':norms,'minimum_gas_erg_g':float(book['remaining'].min()),'maximum_proc_kib':maxproc,
            'source':metrics(fb['atomic_rate_heating_erg_s_cm3'],fb[formal],fb['subcell_width_cm'])}
    comparison=pair._feedback_stability_comparison(feedbacks['previous'],feedbacks['final'])
    checks=pair._feedback_stability_gate_checks(comparison,p['acceptance_gates'])
    checks.update(inner_pair_ready=all(0<=row['residual']<1e-4 and 0<=row['boundary_l1']<1e-3 and 0<=row['boundary_bolometric']<1e-3 for row in rows),physical_response_pass=True)
    assert checks==s['gate_checks'] and len(checks)==7 and all(checks.values())
    assert not s['material_response_failures'] and s['decision']['baseline_control_only']
    assert not s['decision']['finite_trial_accepted_as_one_nonlinear_step'] and not s['decision']['accept_dynamic_nlte_solution']
    for key in ('accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass','accept_finite_trial_only_if_all_acceptance_gates_pass','accept_material_step'):
        assert p['authorization'][key] is False
    assert p['authorization']['zero_displacement_control'] is True
    for k,value in comparison.items():np.testing.assert_allclose(value,s['comparison'][k],rtol=1e-12,atol=0)
    assert post['material_step_promoted'] is False and post['accepted_outer_steps_remain']==20
    assert np.array_equal(vectors['final'],np.load(folder/'material_residual.npy',allow_pickle=False))
    return {'endpoints':ends,'comparison':comparison,'gate_checks':checks},vectors,peaks


def audit_maps(out):
    folder=out/'control';state=read(folder/'state.json');history=state['history']
    assert 8<=len(history)<=16 and state['active_map'] is None
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


def review(archive,receipt,out,reference,physical_old,prior_confirmed,prior_control,output):
    manifest=receive(archive,receipt,out);complete=(out/'summary.json').exists();d=read(out/'declaration.json')
    status=read(out/'status.json');assert status['accepted_outer_steps']==20 and status['new_material_steps']==0
    # 旧包已独立审过；再次核清单和来源字节，不能把新窗口基准偷换为旧target。
    verified_inventory(prior_control)
    prior_state=read(prior_control/'control/state.json');prior_ret=read(prior_control/'control/endpoints-map03/manifest.json')
    prior_protocol=read(prior_control/'control/pair03/feedback_protocol.json')
    assert len(prior_state['history'])==3 and prior_state['active_map'] is None
    seed=prior_ret['endpoints']['mapped_final'];assert seed['sha256']==prior_state['history'][-1]['output_sha256']
    verify_declaration(d,seed)
    history=read(out/'control/state.json')['history'];assert history[0]['input_sha256']==seed['sha256']
    assert read(out/'control/config.json')['warm_seed']==seed
    assert digest(out/'control/trial_material.npz')==digest(prior_control/'control/trial_material.npz')
    for c in d['cases']['control'].values():
        f=out/'inputs'/Path(c['path']).name;assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    base=arrays(reference/'outer_base_material.npz');accepted=arrays(prior_confirmed/'trial_material.npz');r=np.load(reference/'base_residual.npy',allow_pickle=False)
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):assert np.array_equal(base[k],accepted[k])
    assert np.array_equal(r,arrays(prior_confirmed/'common-feedback/final_response.npz')['residual'])
    old=arrays(physical_old);mass=old['cell_mass_g_cm2']
    origin={e:arrays(prior_control/f'control/pair03/{e}_response.npz')['residual'] for e in ('previous','final')};previous=origin
    selected=[n for n in (8,16) if (out/f'control/pair{n:02d}/decision.json').exists()]
    assert selected in ([8],[8,16])
    if complete:
        summary=read(out/'summary.json');assert selected==[8,16] and len(history)==16
        assert summary['status']=='control_window_diagnostic_complete' and summary['accepted_outer_steps']==20 and summary['new_material_steps']==0
        assert summary['baseline_replaced'] is False and summary['strict_error_bound'] is False
        assert set(summary['windows'])=={'8','16'}
    else:assert manifest['stage'] in ('control-map08-feedback','control-map16-feedback')
    reports={};peaks=[];residuals={}
    for n in selected:
        folder=out/f'control/pair{n:02d}';p=read(folder/'feedback_protocol.json');decision=read(folder/'decision.json')
        assert p['acceptance_gates']==prior_protocol['acceptance_gates'] and p['formal_state_gates']==prior_protocol['formal_state_gates']
        assert p['outer_iteration']==prior_protocol['outer_iteration']
        for c in p['common_code_claims']:
            f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
        assert p['sources']['control_window_declaration']['sha256']==digest(out/'declaration.json')
        assert p['sources']['retained_manifest']['sha256']==digest(out/f'control/endpoints-map{n:02d}/manifest.json')
        assert p['numerical_backtracking']=={'alpha':0.,'fixed_base_accepted_index':20,'direction_family':'control','diagnostic_only':True,'physical_time_advanced':False}
        report,vectors,processes=audit_pair(out,n,reference,physical_old,out/'inputs/trial_material.npz');peaks.extend(processes)
        window=recompute_window(vectors,previous,r,mass);total=recompute_window(vectors,origin,r,mass)
        verify_window(window,decision['window_comparison']);verify_window(total,decision['from_77126_comparison'])
        drift=dict(zip(NAMES,independent_norms(vectors['final']-r,mass)))
        for k,value in drift.items():np.testing.assert_allclose(value,decision['fresh_control_minus_r20_norms'][k],rtol=1e-12,atol=0)
        assert decision['zero_control_stable'] is True and decision['original_gates']==report['gate_checks']
        assert decision['promoted'] is False and decision['baseline_replaced'] is False and decision['parent_peak_rss_bytes']<6*1024**3
        if complete:assert summary['windows'][str(n)]==decision
        reports[str(n)]={**report,'window':window,'from_77126':total,'final_minus_r20':drift,'adjacent_vector_difference':dict(zip(NAMES,independent_norms(vectors['final']-vectors['previous'],mass)))}
        residuals[n]=vectors;previous=vectors
    if complete:assert summary['both_windows_stable']==all(x['window']['passed'] for x in reports.values())
    feedback_count=len(peaks);maps,map_peaks=audit_maps(out);peaks+=map_peaks
    for c in d['code']:
        f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    fig,axs=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    axs[0].plot([m['iteration'] for m in maps],[m['residual'] for m in maps],marker='o');axs[0].set(xlabel='New map',ylabel='Global radiation residual')
    for k,name in enumerate(NAMES):axs[1].plot(selected,[max(v[k] for v in reports[str(n)]['window']['vector_difference_over_frozen_r20_norms'].values()) for n in selected],marker='o',label=name)
    axs[1].axhline(.001,color='black',linestyle='--');axs[1].set(xlabel='Window end map',ylabel='Worst vector drift / frozen r20 norm');axs[1].legend()
    for n in selected:axs[2].plot(np.linalg.norm(residuals[n]['final'].reshape(128,4),axis=1),label=f'pair{n:02d}')
    axs[2].set(xlabel='Half-column cell',ylabel='Encoded residual cell norm');axs[2].legend()
    fig.suptitle('Fixed x20 control: observed window drift, not an error bound');fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    result={'archive':read(receipt),'final_summary_present':complete,'verified_files':len(manifest['files']),'verified_code_claims':len(d['code']),
            'audited_windows':selected,'windows':reports,'maps':maps,'feedback_process_receipts':feedback_count,'map_process_receipts':len(map_peaks),'maximum_proc_kib':max(peaks),
            'production_window_function_reused':False,'large_radiation_field_recomputed':False,'material_response_recomputed_on_mac':False,
            'accepted_outer_steps':20,'new_material_steps':0,'baseline_replaced':False,'strict_error_bound':False}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('final_summary_present','verified_files','audited_windows','maximum_proc_kib')},indent=2))
    return result


def main():
    parser=argparse.ArgumentParser()
    for k in ('archive','receipt','received','reference','physical-old','prior-confirmed','prior-control','output'):parser.add_argument('--'+k,type=Path,required=True)
    a=parser.parse_args();review(a.archive,a.receipt,a.received,a.reference,a.physical_old,a.prior_confirmed,a.prior_control,a.output)

if __name__=='__main__':main()
