"""Read-only mixture residual audit with pinned history replay and zero-step control."""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays,audit_native_trial
from operations.material_direction_diagnostic import latest_pair
from operations.radiation_history_diagnostic import identical_material,difference_metrics
from operations.audit_half_step_histories import verify_feedback
from operations.audit_outer_contraction import decomposition
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
from diagnostics.material_energy_ledger import ledger,endpoint_report,mass_weights,heating_decomposition

CURRENT='outputs/hpc/half-history-feedback-20260920'
ZERO='outputs/hpc/baseline-zero-control-20260919'
CACHE='outputs/hpc/half-history-replay-20260920'
CACHE_HASHES={'audit.json':'78fbaf77c3f6d2e143f4e989ef1739c3709d1f83263641fb1ed9fee71ac63d53',
              'replayed_arrays.npz':'f5f4fe126fca9b40cddad7133d3d4b9d57ed2975753a61e2bb793402c06ce772',
              'snapshot-manifest.json':'8c9e2453e99d61eed40124739e01878fbaea17e16b686b4b9abedf13a76d34fa'}


def zero_matches_candidate(zero,trial):
    if float(zero['relaxation'])!=0 or not np.array_equal(zero['encoded_state'],trial['base_encoded_state']):
        raise ValueError('zero material does not equal the frozen candidate base')
    for k in ('base_encoded_state','base_residual','finite_direction','density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(zero[k],trial[k]):raise ValueError('zero physical baseline differs: '+k)


def verify_gate_inventory(summary):
    gates=summary['gate_checks']
    if set(gates)!=REQUIRED_GATES or any(type(v) is not bool for v in gates.values()):
        raise ValueError('formal gate inventory must be complete and boolean')
    # 中文：审计保留所有正式失败门，不要求恰好某两个门失败，也不替代原判决。
    return sorted(k for k,v in gates.items() if not v)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True);args=parser.parse_args()
    pipeline.require_allocation(1)
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'status.json',{'status':'running','new_maps':0})
    try:
        for name in ('audit_mixture_material_residual.py','audit_mixture_material_residual.sbatch',
                     'audit_half_step_histories.py','audit_outer_contraction.py','radiation_history_diagnostic.py',
                     'material_direction_diagnostic.py','review_small_step_evidence.py','prepare_encoded_backtrack.py',
                     'prepare_half_step_after_audit.py'):
            snap.save('operations/'+name)
        snap.save('diagnostics/material_energy_ledger.py')
        cached=snap.read(CACHE+'/audit.json',CACHE_HASHES['audit.json'])
        arrays=load_arrays(snap.save(CACHE+'/replayed_arrays.npz',CACHE_HASHES['replayed_arrays.npz']))
        cache_manifest=snap.read(CACHE+'/snapshot-manifest.json',CACHE_HASHES['snapshot-manifest.json'])
        cached_claims={r['path']:r for r in cache_manifest}
        if not all(cached[k] is True for k in ('same_material_all_fields','same_platform_final_replay_exact','all_feedback_blocks_reassembled_exact')):
            raise RuntimeError('pinned history replay was not fully verified')
        states={};trials={};protos={};summary=None
        for label,run in [('mixture',CURRENT),('zero_control',ZERO)]:
            state=snap.read(run+'/state.json');states[label]=state
            cfg=snap.read(run+'/config.json',state['config_sha256'])
            trial=load_arrays(snap.save(run+'/trial_material.npz',state['trial_sha256']));trials[label]=trial
            audit_native_trial(cfg,trial)
            if label=='mixture':
                pair=latest_pair(state);folder=str(Path(pair['ledger']).parent)
                summary=snap.read(folder+'/feedback_summary.json');verify_gate_inventory(summary)
                if summary['protocol_sha256']!=pair['protocol_sha256']:raise RuntimeError('mixture summary lineage mismatch')
                digest=pair['protocol_sha256'];proto=snap.read(folder+'/feedback_protocol.json',digest)
            else:
                status=snap.read(run+'/control_status.json');control=snap.read(run+'/control_result.json')
                if status['status']!='complete' or status['new_maps']!=2 or len(state['history'])!=2 or state.get('active_map') or state.get('pending_feedback'):
                    raise RuntimeError('zero control is not complete and settled')
                claim=control['feedback_protocol'];digest=claim['sha256'];proto=snap.read(claim['path'],digest);folder=run
            protos[label]=(proto,digest,folder)
            if proto['sources']['trial_material']['sha256']!=state['trial_sha256']:raise RuntimeError('trial source mismatch')
            for claim in list(cfg['sources'])+list(proto['sources'].values()):
                if not claim['path'].endswith('.dat'):snap.save(claim['path'],claim['sha256'])
        trial=trials['mixture'];zero_matches_candidate(trials['zero_control'],trial)
        old_run='outputs/hpc/half-step-base-seeded-20260920'
        c=cached_claims[old_run+'/trial_material.npz']
        identical_material(trial,load_arrays(snap.save(c['path'],c['sha256'])))
        proto=protos['mixture'][0]
        for p,_,_ in protos.values():
            for k in ('physical_old_time_level','base_residual'):
                if p['sources'][k]!=proto['sources'][k]:raise RuntimeError('physical baseline declaration differs')
        c=proto['sources']['physical_old_time_level'];old=load_arrays(snap.save(c['path'],c['sha256']))
        c=proto['sources']['base_residual'];archived=np.load(snap.save(c['path'],c['sha256']),allow_pickle=False)
        if not np.array_equal(archived,trial['base_residual']):raise RuntimeError('formal baseline residual differs from trial')
        mass=old['cell_mass_g_cm2'];weights=mass_weights(mass);phase=int(trial['phase_index'])
        if not np.array_equal(mass,arrays['cell_mass_g_cm2']):raise RuntimeError('cached mass measure differs')
        vectors={};feedbacks={};ledgers={};pairs={}
        for label,(p,digest,folder) in protos.items():
            vectors[label]={};feedbacks[label]={};ledgers[label]={};pairs[label]={}
            for i,endpoint in enumerate(('previous','final')):
                m=snap.read(folder+'/feedback/'+endpoint+'_manifest.json');claim=p['sources'][endpoint+'_radiation']
                row=states[label]['history'][-2:][i]
                if (m['status']!='complete' or not m['state_gate_passed'] or m['protocol_sha256']!=digest
                    or m['state_sha256']!=claim['sha256'] or m['state_path']!=claim['path']
                    or row['input_sha256']!=claim['sha256'] or row['input_path']!=claim['path']):
                    raise RuntimeError('feedback input endpoint lineage mismatch')
                if label=='mixture':
                    rec=summary[endpoint+'_feedback']
                    if rec['feedback_artifact_sha256']!=m['feedback_artifact_sha256'] or rec['feedback_artifact_path']!=m['feedback_artifact_path']:
                        raise RuntimeError('summary feedback artifact mismatch')
                fb=load_arrays(snap.save(m['feedback_artifact_path'],m['feedback_artifact_sha256']))
                verify_feedback(m,fb,snap)
                response,residual,context=adapter._material_response_residual(p,fb)
                if not np.array_equal(mass,context['cell_mass']):raise RuntimeError('response mass differs')
                led=ledger(fb,trial['density_g_cm3'],float(trial['step_duration_s']),
                           old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
                if not all(np.isfinite(v).all() for v in led.values()):raise RuntimeError('nonfinite energy ledger')
                for got,want in ((led['target'],response.target_specific_material_energy_erg_g),
                                 (led['new_h'],response.hydrogen_fraction),(led['new_he'],response.helium_fraction)):
                    if not np.allclose(got,want,rtol=1e-12,atol=0):raise RuntimeError('ledger and response differ')
                vectors[label][endpoint]=residual;feedbacks[label][endpoint]=fb;ledgers[label][endpoint]=led
                pairs[label][endpoint]={'norms':asdict(encoded_residual_norms(residual,mass)),
                    'energy':endpoint_report(led,weights,endpoint),'radiation_residual':row['residual']}
                if label=='mixture' and endpoint=='final':
                    stored=np.load(snap.save(summary['encoded_residual_path'],summary['encoded_residual_sha256']),allow_pickle=False)
                    if not np.array_equal(stored,residual):raise RuntimeError('mixture final replay not exact')
        comparisons={e:{'formal_archived':decomposition(archived,vectors['mixture'][e],mass)} for e in ('previous','final')}
        for e in comparisons:
            for z in ('previous','final'):
                comparisons[e]['zero_control_'+z]=decomposition(vectors['zero_control'][z],vectors['mixture'][e],mass)
        for key,field in [('l2','candidate_to_base_residual_l2_ratio'),('mass_weighted','candidate_to_base_mass_weighted_norm_ratio'),('maximum_cell','candidate_to_base_maximum_cell_norm_ratio')]:
            if not np.isclose(comparisons['final']['formal_archived']['candidate_over_base'][key],summary['comparison'][field],rtol=1e-12,atol=0):
                raise RuntimeError('independent norms fail to reproduce formal ratio')
        cross={};heating={};width=feedbacks['mixture']['final']['subcell_width_cm']
        for label,run in [('base_seed','outputs/hpc/half-step-base-seeded-20260920'),('prior_seed','outputs/hpc/half-step-precision-20260920')]:
            path=run+'/feedback-round2/final_feedback.npz';claim=cached_claims[path]
            fb=load_arrays(snap.save(path,claim['sha256']))
            if not np.array_equal(width,fb['subcell_width_cm']):raise RuntimeError('radiation measure differs')
            cross[label]=difference_metrics(vectors['mixture']['final'],arrays[label+'_final_encoded_residual'],mass)
            heating[label]=heating_decomposition(fb,feedbacks['mixture']['final'])
        drift={k:difference_metrics(v['final'],v['previous'],mass) for k,v in vectors.items()}
        heating['mixture_adjacent']=heating_decomposition(feedbacks['mixture']['previous'],feedbacks['mixture']['final'])
        result={'environment':pipeline.environment(),'pairs':pairs,'formal_gates':summary['gate_checks'],
            'formal_decision':summary['decision'],'failed_gates':verify_gate_inventory(summary),
            'comparisons':comparisons,'observed_adjacent_drifts':drift,'cross_history':cross,'heating':heating,
            'cached_history_hashes':CACHE_HASHES,'cached_replays_recomputed':False,
            'new_maps':0,'formal_acceptance_changed':False,'mixture_final_replay_exact':True,
            'limitation':'Swapping the baseline below is diagnostic only. Observed adjacent or cross-history drift is not a certified error bound; no new acceptance or Jacobian claim.'}
        pipeline.write_json(out/'audit.json',result)
        saved={'cell_mass_g_cm2':mass,'formal_archived':archived}
        for label in vectors:
            for e in vectors[label]:
                saved[label+'_'+e+'_encoded_residual']=vectors[label][e]
                for k,v in ledgers[label][e].items():saved[label+'_'+e+'_ledger_'+k]=v
        np.savez(out/'replayed_arrays.npz',**saved)
        with (out/'cells.csv').open('x',newline='') as f:
            w=csv.writer(f,lineterminator='\n');w.writerow(['cell_index','mass_g_cm2','remaining_erg_g','formal_squared_l2_excess','formal_squared_mass_excess'])
            comp=comparisons['final']['formal_archived']
            for i in range(len(mass)):w.writerow([i,mass[i],ledgers['mixture']['final']['remaining'][i],comp['cell_l2_excess'][i],comp['cell_mass_excess'][i]])
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(3,1,figsize=(10,9),layout='constrained')
        for label in ('base_seed','prior_seed'):axes[0].plot(arrays[label+'_final_ledger_remaining']/1e12,label=label)
        axes[0].plot(ledgers['mixture']['final']['remaining']/1e12,label='mixture')
        for label in cross:axes[1].plot(cross[label]['cell_squared_l2'],label='mixture minus '+label)
        axes[1].plot(drift['mixture']['cell_squared_l2'],label='mixture adjacent')
        for key,c in comparisons['final'].items():axes[2].plot(c['cell_mass_excess'],label=key)
        axes[2].axhline(0,color='black',lw=.6)
        for ax,y in zip(axes,('Target gas heat (1e12 erg/g)','Squared encoded difference','Signed squared mass-norm excess')):
            ax.set(xlabel='Material half-column cell index (not height)',ylabel=y);ax.legend()
        fig.suptitle('Mixture audit: alternative baselines are diagnostic only')
        fig.savefig(out/'mixture_audit.png',dpi=150);plt.close(fig)
        pipeline.write_json(out/'status.json',{'status':'complete','new_maps':0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
