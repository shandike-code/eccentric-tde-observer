"""Mac byte/array/pair-diagnostic audit; does not re-solve Linux populations."""
import argparse
from dataclasses import asdict
from pathlib import Path
import json
import tarfile
import numpy as np
from operations.review_common_frequency import arrays,read,digest,metrics
from eccentric_tde_observer.formal_feedback_pair import trial_feedback_pair_diagnostics,trial_feedback_pair_gate_checks,encoded_residual_norms
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
import matplotlib.pyplot as plt


def review(archive,receipt,out,original,common,report):
    c=read(receipt);assert archive.stat().st_size==c['size_bytes'] and digest(archive)==c['sha256']
    out.mkdir(exist_ok=False)
    with tarfile.open(archive) as t:
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers())
        t.extractall(out,filter='data')
    files=read(out/'MANIFEST.json')['files']
    for c in files:
        p=out/c['path'];assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    summary=read(out/'feedback_summary.json');proto=read(out/'feedback_protocol.json');assessment=read(out/'reassessment.json')
    assert summary['protocol_sha256']==digest(out/'feedback_protocol.json')
    assert read(out/'process.json')['returncode']==0 and read(out/'process.json')['memory_guard_passed']
    assert read(out/'scheduler/scheduler-terminal.json')['state']=='COMPLETED'
    assert (out/'scheduler/job.err').stat().st_size==0
    assert assessment['native_peak_mib']<6144 and read(out/'process.json')['native_observed_peak_kib']<6144*1024
    t=arrays(out/'inputs/trial_material.npz');b=arrays(out/'inputs/outer_base_material.npz');old=arrays(out/'inputs/physical_old_time_level.npz')
    r=np.load(out/'inputs/base_residual.npy',allow_pickle=False);phase=int(t['phase_index']);mass=old['cell_mass_g_cm2']
    assert np.array_equal(t['base_encoded_state'],b['encoded_state']) and np.array_equal(t['base_residual'],r)
    assert np.array_equal(t['finite_direction'],r) and np.array_equal(t['encoded_state'],b['encoded_state']+r/64)
    assert np.array_equal(t['density_g_cm3'],old['density_g_cm3'][phase]) and float(t['step_duration_s'])==float(old['step_duration_s'][phase])
    feedbacks={};responses={};results={};fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    formal='source_formal_heating_erg_s_cm3';codec=GroundStateLogSimplexCodec(128)
    for label in ('previous','final'):
        m=read(out/f'feedback/{label}_manifest.json');fb=arrays(out/f'{label}_feedback.npz');prior=arrays(original/f'{label}_feedback.npz')
        assert m['status']=='complete' and m['state_gate_passed'] and all(m['gate_checks'].values())
        assert m['protocol_sha256']==digest(out/'origin_protocol.json')==proto['configuration']['feedback_origin_protocol_sha256']
        assert m['feedback_artifact_sha256']==digest(out/f'{label}_feedback.npz')
        assert m['state_sha256']==proto['sources'][label+'_radiation']['sha256']
        total={};ownership=np.zeros(9632,int)
        assert [row['block_index'] for row in m['completed_blocks']]==list(range(76))
        for row in m['completed_blocks']:
            i=row['block_index'];p=out/f'feedback/{label}/block{i:02d}.npz';assert digest(p)==row['partial_sha256'];a=arrays(p)
            oldblock=arrays(original/f'feedback/{label}/block{i:02d}.npz')
            expected=arrays(common/f'{label}/block{i:02d}.npz')['common_formal_erg_s_cm3']
            assert np.array_equal(a[formal],expected)
            for k in a:
                if k!=formal:assert np.array_equal(a[k],oldblock[k])
            ownership[row['core_group_start']:row['core_group_stop']]+=1
            if not total:total={k:np.zeros_like(v) for k,v in a.items()}
            for k in total:total[k]+=a[k]
        assert np.all(ownership==1)
        for k,v in total.items():
            assert np.array_equal(v,fb[k]);parent=v.reshape(256,16,*v.shape[1:]).mean(axis=1)
            assert np.array_equal(parent,fb['parent_'+k]) and np.array_equal(parent[:128],fb['half_'+k])
        for k in fb:
            assert np.isfinite(fb[k]).all()
            if k not in (formal,'parent_'+formal,'half_'+formal):assert np.array_equal(fb[k],prior[k])
        sm=metrics(fb['atomic_rate_heating_erg_s_cm3'],fb[formal],fb['subcell_width_cm'])
        assert sm['volume_l1']<1e-3 and sm['net_fraction']<1e-3
        assert m['accumulated_wall_runtime_s']<900 and m['maximum_process_peak_rss_mib']<6144
        book=arrays(out/f'{label}_energy_ledger.npz');response=arrays(out/f'{label}_response.npz')
        assert all(np.isfinite(v).all() for v in book.values()) and np.all(book['remaining']>0)
        assert np.array_equal(book['target']-book['ion_new'],book['remaining'])
        assert np.array_equal(book['total_old']+float(t['step_duration_s'])*book['q']/t['density_g_cm3'],book['target'])
        for k,v in [('target',response['target_specific_material_energy_erg_g']),('new_h',response['hydrogen_fraction']),('new_he',response['helium_fraction'])]:np.testing.assert_allclose(book[k],v,rtol=1e-12,atol=0)
        encoded=codec.encode(response['temperature_k'],response['hydrogen_fraction'],response['helium_fraction'])
        np.testing.assert_allclose(encoded-t['encoded_state'],response['residual'],rtol=1e-10,atol=2e-14)
        norms=asdict(encoded_residual_norms(response['residual'],mass))
        for k,v in norms.items():assert np.isclose(v,assessment['responses'][label]['norms'][k],rtol=1e-12,atol=0)
        results[label]={'norms':norms,'source_metrics':sm,'minimum_gas_erg_g':float(book['remaining'].min()),'failed_gas_cells':int(np.count_nonzero(book['remaining']<=0))}
        feedbacks[label]=fb;responses[label]=response
        axes[0].plot(book['remaining']/1e12,label=label);axes[1].plot(np.linalg.norm(response['residual'].reshape(128,4),axis=1),label=label)
    d=trial_feedback_pair_diagnostics(previous_feedback=feedbacks['previous'],final_feedback=feedbacks['final'],previous_encoded_residual=responses['previous']['residual'],final_encoded_residual=responses['final']['residual'],base_encoded_residual=r,cell_width=feedbacks['final']['subcell_width_cm'],cell_mass=mass)
    checks=trial_feedback_pair_gate_checks(d,proto['acceptance_gates'])
    assert all(summary['gate_checks'][k]==v for k,v in checks.items())
    for k in ('atomic_heating_volume_l1','direct_heating_volume_l1','formal_heating_volume_l1','inner_noise_to_trial_signal_l2_ratio'):assert np.isclose(getattr(d,k),summary['comparison'][k],rtol=1e-12,atol=0)
    assert not any([assessment['material_step_promoted'],summary['decision']['finite_trial_accepted_as_one_nonlinear_step']])
    axes[0].set(xlabel='Half-column cell',ylabel='Gas energy / 1e12 erg g^-1');axes[0].legend()
    axes[1].set(xlabel='Half-column cell',ylabel='Encoded residual cell norm');axes[1].legend()
    axes[2].bar(['Heat / gate','Noise / gate'],[d.atomic_heating_volume_l1/.001,d.inner_noise_to_trial_signal_l2_ratio/.1]);axes[2].axhline(1,color='black')
    fig.suptitle('Common-frequency bridge: positive response, trial NOT accepted');fig.savefig(report.with_suffix('.png'),dpi=160);plt.close(fig)
    record={'verified_files':len(files),'endpoints':results,'gate_checks':summary['gate_checks'],'comparison':summary['comparison'],'accepted_outer_steps':15,'physical_response_replayed_on_mac':False,'new_source_and_old_atomic_fields_verified_bitwise':True,'archive':read(receipt)}
    report.with_suffix('.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');print(json.dumps(record,indent=2))


def main():
    p=argparse.ArgumentParser()
    for name in ('archive','receipt','received','original','common','report'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();review(a.archive,a.receipt,a.received,a.original,a.common,a.report)


if __name__=='__main__':main()
