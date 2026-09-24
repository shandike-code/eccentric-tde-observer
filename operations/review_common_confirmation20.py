"""Independent step20 six-endpoint audit against fixed x19 and r19."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tarfile
import numpy as np
from operations.review_common_frequency import read,digest,arrays,metrics
from operations.common_feedback_bridge import state_checks
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms,trial_feedback_pair_diagnostics,trial_feedback_pair_gate_checks
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
import matplotlib.pyplot as plt
from operations.common_confirmation_batch import cross_comparisons,validate_zero
from operations.common_feedback_bridge import validate_identity
from scripts import phase7b9_formal_feedback_pair_adapter as pair
from eccentric_tde_observer.coupled_material_newton_krylov import ground_state_material_trial_within_trust_region


def review(archive,receipt,out,reference,physical_old,prior_confirmed,candidate_root,output):
    claim=read(receipt);assert archive.stat().st_size==claim['size_bytes'] and digest(archive)==claim['sha256']
    if not out.exists():
        out.mkdir()
        with tarfile.open(archive) as t:
            assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers());t.extractall(out,filter='data')
    manifest=read(out/'ARCHIVE_MANIFEST.json')
    for c in manifest['files']:
        f=out/c['path'];assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    root=read(out/'summary.json');assert root['new_material_steps']==0 and root['accepted_outer_steps']==19 and root['status']=='confirmed_requires_mac_review'
    results={};residuals={};peaks=[];formal='source_formal_heating_erg_s_cm3'
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for case in ('control','confirm1','confirm2'):
        folder=out/case/'common-feedback';p=read(folder/'feedback_protocol.json');s=read(folder/('baseline_summary.json' if case=='control' else 'feedback_summary.json'));post=read(folder/'postcheck.json')
        assert digest(folder/'feedback_protocol.json')==s['protocol_sha256']
        assert 'reuse_completed_feedback_manifests' not in p['configuration']
        assert 'retained_manifest' not in p['sources']
        assert p['numerical_backtracking']==dict(alpha=0. if case=='control' else 1/128,fixed_base_accepted_index=19,fixed_direction='r19',physical_time_advanced=False)
        for key in ('outer_base_material','physical_old_time_level','base_residual'):
            c=p['sources'][key];f=physical_old if key=='physical_old_time_level' else reference/(key+Path(c['path']).suffix);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
        t=arrays(out/case/'trial_material.npz');assert digest(out/case/'trial_material.npz')==p['sources']['trial_material']['sha256'];base=arrays(reference/'outer_base_material.npz');old=arrays(physical_old);r=np.load(reference/'base_residual.npy',allow_pickle=False)
        assert np.array_equal(t['base_encoded_state'],base['encoded_state']) and np.array_equal(t['base_residual'],r) and np.array_equal(t['finite_direction'],r)
        assert float(t['relaxation'])==(0 if case=='control' else 1/128)
        assert np.array_equal(t['encoded_state'],base['encoded_state']+float(t['relaxation'])*r)
        if case=='control':
            assert set(t)==set(base) and all(np.array_equal(t[k],base[k]) for k in t)
        else:
            assert np.array_equal(t['finite_direction'],r)
            frozen=arrays(candidate_root/'maps/trial_material.npz');assert set(t)==set(frozen) and all(np.array_equal(t[k],frozen[k]) for k in t)
        decoded=GroundStateLogSimplexCodec(128).decode(t['encoded_state'])
        # 只容许跨CPU指数/softmax的8个机器epsilon；字节/向量身份与科学门不放宽。
        for key in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
            np.testing.assert_allclose(t[key],getattr(decoded,key),rtol=8*np.finfo(float).eps,atol=0)

        assert ground_state_material_trial_within_trust_region(GroundStateLogSimplexCodec(128),base['encoded_state'],t['encoded_state'],maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,maximum_population_fraction_change=.05)
        state=read(out/case/'state.json');assert len(state['history'])==(4 if case=='control' else 2) and state['active_map'] is None
        rows=state['history'][-2:]
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
        if case=='control':
            comparison=pair._feedback_stability_comparison(feedbacks['previous'],feedbacks['final'])
            checks=pair._feedback_stability_gate_checks(comparison,p['acceptance_gates'])
            assert all(checks.values()) and all(s['gate_checks'].values()) and not s['decision']['finite_trial_accepted_as_one_nonlinear_step']
            assert not p['authorization']['accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass']
        else:
            d=trial_feedback_pair_diagnostics(previous_feedback=feedbacks['previous'],final_feedback=feedbacks['final'],previous_encoded_residual=vectors['previous'],final_encoded_residual=vectors['final'],base_encoded_residual=r,cell_width=feedbacks['final']['subcell_width_cm'],cell_mass=mass)
            checks=trial_feedback_pair_gate_checks(d,p['acceptance_gates']);assert all(checks.values()) and all(s['gate_checks'][k]==v for k,v in checks.items())
            assert set(s['gate_checks'])==REQUIRED_GATES and all(s['gate_checks'].values()) and s['decision']['finite_trial_accepted_as_one_nonlinear_step']
            comparison={k:getattr(d,k) for k in ('atomic_heating_volume_l1','direct_heating_volume_l1','formal_heating_volume_l1','inner_noise_to_trial_signal_l2_ratio')}
            cross=cross_comparisons(vectors,residuals['control'],mass)
            assert cross['passed']
            saved=root['cases'][case]['fresh_baseline_comparison']['ratios']
            for k,v in cross['ratios'].items():
                for n,x in v.items():assert np.isclose(x,saved[k][n],rtol=1e-12,atol=0)
        cfg=p['configuration'];assert all(cfg[e+'_global_original_operator_residual']<1e-4 and cfg[e+'_boundary_spectrum_l1']<1e-3 and cfg[e+'_boundary_bolometric_fraction']<1e-3 for e in vectors)
        for k,v in comparison.items():np.testing.assert_allclose(v,s['comparison'][k],rtol=1e-12,atol=0)
        assert not post['material_step_promoted'] and post['accepted_outer_steps_remain']==19
        assert np.array_equal(vectors['final'],np.load(folder/'material_residual.npy',allow_pickle=False))
        results[case]={'endpoints':ends,'comparison':s['comparison'],'required_gates_passed':True};residuals[case]=vectors
        if case!='control':results[case]['fresh_baseline_comparison']=cross
        axes[0].plot(np.linalg.norm(vectors['final'].reshape(128,4),axis=1),label=case)
    # The new zero control retains accepted x19 exactly, not its response target.
    accepted=arrays(prior_confirmed/'trial_material.npz')
    for key in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction',
                'specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[key],accepted[key])
    assert np.array_equal(np.load(reference/'base_residual.npy',allow_pickle=False),
                          arrays(prior_confirmed/'common-feedback/final_response.npz')['residual'])
    prior_vectors={e:arrays(candidate_root/'pair08'/(e+'_response.npz'))['residual'] for e in ('previous','final')}
    prior_cross=cross_comparisons(prior_vectors,residuals['control'],mass)
    saved_cross=root['cases']['control']['prior_candidates']['pair08']
    assert prior_cross['passed'] and saved_cross['passed']
    for endpoint,norms in prior_cross['ratios'].items():
        for key,value in norms.items():
            np.testing.assert_allclose(value,saved_cross['ratios'][endpoint][key],rtol=8*np.finfo(float).eps,atol=0)
    results['control']['prior_pair08_comparison']=prior_cross
    seeds=read(out/'declaration.json')['seeds']
    assert seeds['control']['sha256']==read(prior_confirmed/'state.json')['history'][-1]['output_sha256']
    assert seeds['confirm1']==read(candidate_root/'endpoints-map08/manifest.json')['endpoints']['mapped_final']
    for case in ('control','confirm1','confirm2'):
        first=read(out/case/'state.json')['history'][0]
        expected=(read(out/'confirm1/state.json')['current_sha256'] if case=='confirm2' else seeds[case]['sha256'])
        assert first['input_sha256']==expected
    feedback_receipts=len(peaks);times=[]
    for case in ('control','confirm1','confirm2'):
      state=read(out/case/'state.json');histories=state['history']
      assert digest(out/case/'config.json')==state['config_sha256']
      assert read(out/case/'initialized_identity.json')['passed']
      for row in histories:
          n=row['iteration'];folder=out/case/f'map{n:04d}';rows=[read(folder/f'block{i:02d}.json') for i in range(76)]
          ownership=np.zeros(9632,int)
          for i,r in enumerate(rows):
              assert r['block_index']==i and r['minimum_input_intensity']>=0 and r['minimum_mapped_intensity']>=0
              assert all(np.isfinite(v) for v in r.values() if isinstance(v,(float,int))) and r['peak_process_rss_mib']<6144
              ownership[r['core_group_start']:r['core_group_stop']]+=1
              paths=list(folder.glob(f'block{i:02d}.process-*.json'));assert len(paths)==1
              process=read(paths[0]);assert process['returncode']==0 and process['memory_guard_passed'] and process['native_observed_peak_kib']<6144*1024
              peaks.append(process['native_observed_peak_kib'])
          assert np.all(ownership==1)
          scale=max(r['maximum_radiation_scale'] for r in rows);assert scale>0
          residual=max(r['maximum_absolute_radiation_change'] for r in rows)/scale
          l1=sum(r['boundary_spectrum_l1_numerator'] for r in rows)/max(sum(r['current_boundary_absolute_scale'] for r in rows),sum(r['mapped_boundary_absolute_scale'] for r in rows))
          before=sum(r['current_boundary_bolometric'] for r in rows);after=sum(r['mapped_boundary_bolometric'] for r in rows)
          bol=abs(after-before)/max(abs(before),abs(after))
          for k,v in [('residual',residual),('boundary_l1',l1),('boundary_bolometric',bol)]:assert v==row[k]
          times.append(row['wall_s'])
    drift=asdict(encoded_residual_norms(residuals['confirm2']['final']-residuals['confirm1']['final'],mass))
    baseline_drift=asdict(encoded_residual_norms(residuals['control']['final']-residuals['control']['previous'],mass))
    for ax,k,limit in [(axes[1],'atomic_heating_volume_l1',.001),(axes[2],'inner_noise_to_trial_signal_l2_ratio',.1)]:
        selected={c:v for c,v in results.items() if k in v['comparison']};ax.bar(list(selected),[v['comparison'][k]/limit for v in selected.values()]);ax.axhline(1,color='black');ax.set(title=k,ylabel='Metric / original gate')
    axes[0].set(xlabel='Half-column cell',ylabel='Encoded residual cell norm');axes[0].legend()
    fig.suptitle('Fresh baseline and two confirmations pass; coupled solution not established');fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    record={'archive':read(receipt),'verified_files':len(manifest['files']),'pairs':results,'feedback_process_receipts':feedback_receipts,'map_process_receipts':len(peaks)-feedback_receipts,'total_map_wall_s':sum(times),'maximum_proc_kib':max(peaks),
        'same_material_confirmation_drift':drift,'baseline_pair_drift':baseline_drift,'drift_is_error_bound':False,'material_response_recomputed_on_mac':False,'accepted_outer_steps':19,'cross_platform_decode_rtol':8*np.finfo(float).eps}
    output.with_suffix('.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');print(json.dumps(record,indent=2))


def main():
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','reference','physical-old','prior-confirmed','candidate-root','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();review(a.archive,a.receipt,a.received,a.reference,a.physical_old,a.prior_confirmed,a.candidate_root,a.output)


if __name__=='__main__':main()
