"""Audit measured heating and optional eight-map window with independent scalar sums."""
import argparse,json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_step21_control_windows as cw
from handoff.audit_tools.review_step21_wide_validation import audit_maps
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close
read,digest,arrays=cw.read,cw.digest,cw.arrays


def thermal_reference(out,prior,old):
    d=read(out/'declaration.json');ref=read(out/'inputs/heating_reference.json');assert d['heating_reference']==ref
    trial=arrays(out/'control/trial_material.npz');q=[];em=[]
    for n in (3,11):
        for e in ('previous','final'):
            f=arrays(prior/f'control/pair{n:02d}/{e}_feedback.npz');b=arrays(prior/f'control/pair{n:02d}/{e}_energy_ledger.npz')
            assert np.array_equal(f['half_atomic_rate_heating_erg_s_cm3'],b['q']);q.append(b['q']);em.append(f['emitted_power_erg_s_cm3']);u=b['remaining']
    assert all(np.array_equal(em[0],x) for x in em) and np.all(u>0)
    mass=old['cell_mass_g_cm2'];rho=trial['density_g_cm3'];dt=float(trial['step_duration_s']);scale=dt/rho/u
    assert q[0].shape==u.shape==mass.shape==rho.shape==(128,)
    assert all(np.isfinite(x).all() for x in [*q,u,mass,rho]) and np.all(mass>0) and np.all(rho>0)
    # 单格求积用Python float，质量总和/内积用fsum；不调用生产热代理归约。
    dot=lambda a,b:math.fsum(float(m)*float(x)*float(y) for m,x,y in zip(mass,a,b))/math.fsum(float(m) for m in mass)
    norm=lambda a:math.sqrt(dot(a,a))
    early=(q[1]-q[0])*scale;late=(q[3]-q[2])*scale;direction=early-late
    independent_alpha=-dot(late,direction)/dot(direction,direction)
    alpha=d['uv'][1];assert d['uv'][0]==0;assert_close(alpha,independent_alpha);assert ref['alpha']==alpha
    expected={'source_q':q,'reference_energy':u,'rho':rho,'mass':mass,'scale':scale,'source_late_s':late,
              'predicted_q':q[2]+alpha*(q[0]-q[2]),'predicted_p':q[3]+alpha*(q[1]-q[3]),'predicted_s':late+alpha*direction}
    for k,x in expected.items():assert np.array_equal(np.asarray(ref[k]),np.asarray(x)),k
    assert ref['dt']==dt and ref['prediction_error_limit']==.001 and ref['actual_cost_ratio_limit']==.8
    denominator=norm(late);maximum=max(abs(float(x)) for x in late)
    assert_close(denominator,ref['source_proxy_norm']);assert_close(maximum,ref['source_proxy_max'])
    assert_close(norm(expected['predicted_s'])/denominator,ref['proxy']['proxy_ratio'])
    pair=out/'control/pair02';feedback=[arrays(pair/f'{e}_feedback.npz') for e in ('previous','final')]
    assert all(np.array_equal(em[0],f['emitted_power_erg_s_cm3']) for f in feedback)
    a,b=[f['half_atomic_rate_heating_erg_s_cm3'] for f in feedback];actual=(b-a)*scale
    assert a.shape==b.shape==(128,) and np.isfinite(actual).all()
    error={'previous':(a-expected['predicted_q'])*scale,'final':(b-expected['predicted_p'])*scale,'difference':actual-expected['predicted_s']}
    metrics={k:dict(mass_over_source=norm(x)/denominator,max_over_source=max(abs(float(y)) for y in x)/maximum) for k,x in error.items()}
    ratio=norm(actual)/denominator;checks={'actual_heating_cost_pass':0<=ratio<.8}
    checks.update({k+'_prediction_error_pass':all(0<=x<.001 for x in v.values()) for k,v in metrics.items()})
    saved=read(pair/'heating_validation.json')
    for k,x in [('previous_q',a),('final_q',b),('actual_s',actual)]:assert np.array_equal(saved[k],x)
    for k,x in [('actual_proxy_norm',norm(actual)),('source_proxy_norm',denominator),('actual_proxy_ratio',ratio)]:assert_close(x,saved[k])
    for k in metrics:
        for label,value in metrics[k].items():assert_close(value,saved['prediction_errors'][k][label])
    assert checks==saved['checks'] and all(checks.values())==saved['validated']
    assert not saved['reference_changed'] and not saved['accepted_material_step']
    return dict(actual_proxy_ratio=ratio,predicted_proxy_ratio=norm(expected['predicted_s'])/denominator,
        source_proxy_norm=denominator,actual_proxy_norm=norm(actual),independent_alpha=independent_alpha,
        prediction_errors=metrics,checks=checks,validated=all(checks.values()),independent_cell_norm_reducer=True),expected['predicted_s'],actual


def review(archive,receipt,received,first,prior,reference,physical_old,output):
    manifest=cw.receive(archive,receipt,received)
    for root,name in [(first,'20260926-heating-validation-map1-review'),(prior,'20260925-wide-validation-complete-review')]:
        c=read(Path('handoff/evidence')/(name+'.json'))['archive'];p=archive.parent/Path(c['path']).name
        assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
        with tarfile.open(p) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(root/'ARCHIVE_MANIFEST.json')
        cw.verified_inventory(root)
    out=received;d=read(out/'declaration.json');status=read(out/'status.json')
    assert status['accepted_outer_steps']==20 and status['new_material_steps']==0
    assert (d['maximum_maps'],d['maximum_feedback_pairs'],d['cadence'])==(10,2,[2,10])
    # 首map包已经审过物理身份、basis与初始候选；相同文件必须逐位保留。
    for name in ('declaration.json','inputs/heating_reference.json','inputs/trial_material.npz','inputs/config.json',
                 'control/validation.json','control/config.json','control/trial_material.npz','control/initialized_identity.json'):
        assert (out/name).read_bytes()==(first/name).read_bytes(),name
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    maps,peaks=audit_maps(out);assert len(maps)<=10
    assert read(out/'control/state.json')['history'][0]==read(first/'control/state.json')['history'][0]
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r=np.load(reference/'base_residual.npy',allow_pickle=False)
    source=read(prior/'control/pair11/feedback_protocol.json')
    for k in ('outer_base_material','physical_old_time_level','base_residual'):
        c=source['sources'][k];p=physical_old if k=='physical_old_time_level' else reference/(k+Path(c['path']).suffix)
        assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    thermal,predicted_s,actual_s=thermal_reference(out,prior,old)
    selected=[n for n in (2,10) if (out/f'control/pair{n:02d}/decision.json').exists()];assert selected in ([2],[2,10])
    origin={e:arrays(prior/f'control/pair11/{e}_response.npz')['residual'] for e in ('previous','final')};previous=origin
    reports={};count=0
    for n in selected:
        folder=out/f'control/pair{n:02d}';p=read(folder/'feedback_protocol.json');decision=read(folder/'decision.json')
        for key in ('acceptance_gates','formal_state_gates','outer_iteration'):assert p[key]==source[key]
        for key,path in [('control_window_declaration',out/'declaration.json'),('heating_projection_validation',out/'control/validation.json'),
                         ('retained_manifest',out/f'control/endpoints-map{n:02d}/manifest.json')]:assert p['sources'][key]['sha256']==digest(path)
        for c in p['common_code_claims']:
            f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
        report,vectors,resources=cw.audit_pair(out,n,reference,physical_old,out/'inputs/trial_material.npz')
        peaks.extend(resources);count+=len(resources)
        window=cw.recompute_window(vectors,previous,r,mass);total=cw.recompute_window(vectors,origin,r,mass)
        cw.verify_window(window,decision['window_comparison']);cw.verify_window(total,decision['from_77371_comparison'])
        kind='post_extrapolation_shift' if n==2 else 'eight_map_drift';assert decision['comparison_kind']==kind
        drift=dict(zip(cw.NAMES,cw.independent_norms(vectors['final']-r,mass)))
        for k,x in drift.items():assert_close(x,decision['fresh_control_minus_r20_norms'][k])
        assert decision['feedback_evaluated'] and decision['zero_control_stable'] and decision['original_gates']==report['gate_checks']
        assert not decision['baseline_replaced'] and not decision['promoted'] and decision['parent_peak_rss_bytes']<6*1024**3
        if n==2:
            saved=read(folder/'heating_validation.json');assert decision['heating_validation']==saved
            assert decision['conditional_continuation_pass']==thermal['validated']
            rows=read(out/'control/state.json')['history'];ret=read(out/'control/endpoints-map02/manifest.json')
            assert ret['endpoints']['previous']['sha256']==read(out/'control/validation.json')['candidate']['sha256']
            assert ret['endpoints']['final']['sha256']==rows[0]['output_sha256']
        else:assert decision['conditional_continuation_pass']
        reports[str(n)]={**report,'comparison_kind':kind,'window':window,'from_77371':total,'final_minus_r20':drift}
        previous=vectors
    if len(maps)>2:assert thermal['validated']
    complete=(out/'summary.json').exists()
    if complete:
        s=read(out/'summary.json');assert s['accepted_outer_steps']==20 and s['new_material_steps']==0 and not s['baseline_replaced'] and not s['strict_error_bound']
        assert s['maps']==len(maps)
        if s['status']=='heating_projection_validation_complete_requires_review':assert len(maps)==10 and selected==[2,10] and thermal['validated']
        elif s['status']=='first_control_or_heating_not_validated':assert len(maps)==2 and selected==[2] and not thermal['validated']
        else:raise AssertionError('unexpected terminal requires dedicated failure audit')
        for n in selected:assert s['cases'][str(n)]==read(out/f'control/pair{n:02d}/decision.json')
    else:assert manifest['stage'] in ('control-map02-feedback','control-map10-feedback')
    result=dict(archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),maps=maps,
        thermal_validation=thermal,feedback_rounds=selected,windows=reports,final_summary_present=complete,
        maximum_proc_kib=max(peaks),map_process_receipts=76*len(maps),feedback_process_receipts=count,
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
        production_thermal_reducer_reused=False,production_window_reducer_reused=False,
        original_seven_gate_reducer_reused=True,material_ode_recomputed_on_mac=False,full_large_fields_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    axs[0].plot(predicted_s,label='predicted');axs[0].plot(actual_s,ls='--',label='actual');axs[0].set(xlabel='Material cell index',ylabel='Frozen-scale heating change');axs[0].legend()
    axs[1].plot(actual_s-predicted_s);axs[1].set(xlabel='Material cell index',ylabel='Actual minus predicted')
    for i,label in enumerate(cw.NAMES):axs[2].plot(selected,[max(x[i] for x in reports[str(n)]['window']['vector_difference_over_frozen_r20_norms'].values()) for n in selected],'o-',label=label)
    axs[2].axhline(.001,ls='--',color='black');axs[2].set(xlabel='2: extrapolation shift; 10: eight-map drift',ylabel='Vector difference / original r20 norm');axs[2].legend()
    fig.suptitle('Measured atomic heating; no new material acceptance');fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','receipt','received','first','prior','reference','physical-old','output'):p.add_argument('--'+n,type=Path,required=True)
    r=review(**vars(p.parse_args()));print(json.dumps({k:r[k] for k in ('verified_files','verified_code_claims','thermal_validation','feedback_rounds','windows')},indent=2))
