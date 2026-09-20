"""Replay new feedback only; diagnose material and frequency-block heating changes."""
from __future__ import annotations
import argparse
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
from operations.radiation_history_diagnostic import identical_material,difference_metrics,require_ownership
from operations.audit_half_step_histories import verify_feedback
from operations.audit_mixture_material_residual import verify_gate_inventory
from operations.audit_outer_contraction import decomposition
from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
from diagnostics.material_energy_ledger import ledger,endpoint_report,mass_weights,heating_decomposition

CURRENT='outputs/hpc/half-four-map-feedback-20260920'
CURRENT_SHA='d9e92da7e394c772e1ced2874a78ce5b57609bc2a692329fae96e870c29234ad'
PREVIOUS='outputs/hpc/half-history-feedback-20260920'
CACHE='outputs/hpc/mixture-material-residual-audit-20260920'
CACHE_SHA={'audit.json':'48082cef1c1148b57b657084337759dd42c193084d628b58e66fee6b24cf415f',
 'replayed_arrays.npz':'aed80578004465c94d13c32c8f189b313f28af14e270f41f50d3ecf19fd4415f',
 'snapshot-manifest.json':'cb333edb87ca4720a6e832dff398219b83354c2af1f59facd4aa209499e0d2ad'}


def block_heating_change(a,b,widths,full_a,full_b):
    """All norms use the same full-column depth measure, before any folding."""
    a,b,w,x,y=map(lambda v:np.asarray(v,dtype=float),(a,b,widths,full_a,full_b))
    if (a.ndim!=2 or a.shape!=b.shape or w.shape!=(a.shape[1],) or x.shape!=w.shape or y.shape!=w.shape
            or not all(np.isfinite(v).all() for v in (a,b,w,x,y)) or np.any(w<=0)):
        raise ValueError('invalid heating arrays or depth measure')
    delta=b-a; combined=delta.sum(axis=0); exact=y-x
    l1=float(np.sum(abs(exact)*w)); error=float(np.sum(abs(combined-exact)*w))
    relative=error/l1 if l1 else (0. if error==0 else None)
    if relative is None or relative>1e-8:
        raise ArithmeticError('frequency-block difference does not reconstruct total heating difference')
    block_l1=np.sum(abs(delta)*w[None,:],axis=1); total=float(block_l1.sum())
    # 中文：正式门先逐深度取两态绝对值最大，再按同一宽度积分，不能先积分再取最大。
    denominator=float(np.sum(np.maximum(abs(x),abs(y))*w))
    if not np.isfinite([l1,error,total,denominator]).all():raise ArithmeticError('nonfinite heating integral')
    return {'block_l1':block_l1.tolist(),'block_signed_integral':np.sum(delta*w[None,:],axis=1).tolist(),
        'sum_block_l1':total,'net_depth_l1':l1,'net_over_sum_block_l1':l1/total if total else None,
        'heating_ratio':l1/denominator if denominator else 0.,'closure_relative_l1':relative,
        'top_block_indices':np.argsort(-block_l1)[:8].tolist(),
        'units':'column integrals erg s^-1 cm^-2; ratios dimensionless',
        'limitation':'Frequency-block cancellation at each depth; not a certified error bound or physical luminosity.'}


def load_blocks(manifest,snap):
    require_ownership(manifest['completed_blocks'])
    rows=manifest['completed_blocks']
    if [r['block_index'] for r in rows]!=list(range(76)):
        raise ValueError('original frequency-block order differs')
    return np.stack([load_arrays(snap.save(r['partial_path'],r['partial_sha256']))['atomic_rate_heating_erg_s_cm3'] for r in rows])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);args=p.parse_args()
    pipeline.require_allocation(1)
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'status.json',{'status':'running','new_maps':0})
    try:
        for name in ('audit_four_map_response.py','audit_four_map_response.sbatch','audit_mixture_material_residual.py',
                     'audit_half_step_histories.py','audit_outer_contraction.py','radiation_history_diagnostic.py',
                     'material_direction_diagnostic.py','prepare_encoded_backtrack.py','review_small_step_evidence.py'):
            snap.save('operations/'+name)
        snap.save('diagnostics/material_energy_ledger.py')
        cached=snap.read(CACHE+'/audit.json',CACHE_SHA['audit.json'])
        if cached['mixture_final_replay_exact'] is not True:raise RuntimeError('cached replay not verified')
        arrays=load_arrays(snap.save(CACHE+'/replayed_arrays.npz',CACHE_SHA['replayed_arrays.npz']))
        claims={x['path']:x for x in snap.read(CACHE+'/snapshot-manifest.json',CACHE_SHA['snapshot-manifest.json'])}
        def old_read(path):return snap.read(path,claims[path]['sha256'])
        state=snap.read(CURRENT+'/state.json',CURRENT_SHA);pair=latest_pair(state)
        cfg=snap.read(CURRENT+'/config.json',state['config_sha256'])
        trial=load_arrays(snap.save(CURRENT+'/trial_material.npz',state['trial_sha256']));audit_native_trial(cfg,trial)
        old_trial=load_arrays(snap.save(PREVIOUS+'/trial_material.npz',claims[PREVIOUS+'/trial_material.npz']['sha256']))
        identical_material(trial,old_trial)
        folder=str(Path(pair['ledger']).parent);digest=pair['protocol_sha256']
        summary=snap.read(folder+'/feedback_summary.json');verify_gate_inventory(summary)
        if summary['protocol_sha256']!=digest:raise RuntimeError('summary protocol differs')
        proto=snap.read(folder+'/feedback_protocol.json',digest)
        old_folder=PREVIOUS+'/feedback-round1';old_proto=old_read(old_folder+'/feedback_protocol.json')
        for k in ('physical_old_time_level','base_residual'):
            if proto['sources'][k]!=old_proto['sources'][k]:raise RuntimeError('physical baseline differs')
        for k in ('angular_direction_count','physical_frequency_groups','radiation_depth_cell_count','material_cell_count',
                  'block_count','core_frequency_groups','rate_quadrature_order_per_group'):
            if proto['configuration'][k]!=old_proto['configuration'][k]:raise RuntimeError('feedback discretization differs')
        if proto['sources']['trial_material']['sha256']!=state['trial_sha256']:raise RuntimeError('trial declaration differs')
        for c in list(cfg['sources'])+list(proto['sources'].values()):
            if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
        c=proto['sources']['physical_old_time_level'];old=load_arrays(snap.save(c['path'],c['sha256']))
        mass=old['cell_mass_g_cm2'];weight=mass_weights(mass);phase=int(trial['phase_index']);archived=arrays['formal_archived']
        if not np.array_equal(mass,arrays['cell_mass_g_cm2']) or not np.array_equal(archived,trial['base_residual']):
            raise RuntimeError('cached mass or formal base differs')
        vectors={};feedback={};energy={};reports={};blocks={};old_feedback={};old_blocks={}
        for i,e in enumerate(('previous','final')):
            m=snap.read(folder+'/feedback/'+e+'_manifest.json');c=proto['sources'][e+'_radiation'];row=state['history'][-2:][i]
            rec=summary[e+'_feedback']
            if (m['status']!='complete' or not m['state_gate_passed'] or m['protocol_sha256']!=digest
                or (m['state_sha256'],m['state_path'])!=(c['sha256'],c['path'])
                or (row['input_sha256'],row['input_path'])!=(c['sha256'],c['path'])
                or (rec['feedback_artifact_sha256'],rec['feedback_artifact_path'])!=(m['feedback_artifact_sha256'],m['feedback_artifact_path'])):
                raise RuntimeError('feedback endpoint lineage differs')
            fb=load_arrays(snap.save(m['feedback_artifact_path'],m['feedback_artifact_sha256']));verify_feedback(m,fb,snap)
            response,v,context=adapter._material_response_residual(proto,fb)
            if not np.array_equal(mass,context['cell_mass']):raise RuntimeError('response mass differs')
            led=ledger(fb,trial['density_g_cm3'],float(trial['step_duration_s']),old['temperature_k'][phase],
                       old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            if not all(np.isfinite(x).all() for x in led.values()):raise RuntimeError('nonfinite ledger')
            for got,want in ((led['target'],response.target_specific_material_energy_erg_g),(led['new_h'],response.hydrogen_fraction),(led['new_he'],response.helium_fraction)):
                if not np.allclose(got,want,rtol=1e-12,atol=0):raise RuntimeError('ledger/response mismatch')
            vectors[e]=v;feedback[e]=fb;energy[e]=led;blocks[e]=load_blocks(m,snap)
            reports[e]={'norms':asdict(encoded_residual_norms(v,mass)),'energy':endpoint_report(led,weight,e)}
            om=old_read(old_folder+'/feedback/'+e+'_manifest.json')
            old_feedback[e]=load_arrays(snap.save(om['feedback_artifact_path'],om['feedback_artifact_sha256']))
            old_blocks[e]=load_blocks(om,snap)
        stored=np.load(snap.save(summary['encoded_residual_path'],summary['encoded_residual_sha256']),allow_pickle=False)
        if not np.array_equal(stored,vectors['final']):raise RuntimeError('final response replay not exact')
        width=feedback['final']['subcell_width_cm']
        for fb in list(feedback.values())+list(old_feedback.values()):
            if not np.array_equal(width,fb['subcell_width_cm']):raise RuntimeError('depth measure differs')
        comparison={e:decomposition(archived,vectors[e],mass) for e in vectors}
        for k,f in [('l2','candidate_to_base_residual_l2_ratio'),('mass_weighted','candidate_to_base_mass_weighted_norm_ratio'),('maximum_cell','candidate_to_base_maximum_cell_norm_ratio')]:
            if not np.isclose(comparison['final']['candidate_over_base'][k],summary['comparison'][f],rtol=1e-12,atol=0):raise RuntimeError('formal norm ratio not reproduced')
        drift=difference_metrics(vectors['final'],vectors['previous'],mass)
        cross=difference_metrics(vectors['final'],arrays['mixture_final_encoded_residual'],mass)
        heating={};block_reports={}
        for label,a,b,qa,qb in [('new_adjacent',feedback['previous'],feedback['final'],blocks['previous'],blocks['final']),
                               ('old_adjacent',old_feedback['previous'],old_feedback['final'],old_blocks['previous'],old_blocks['final']),
                               ('cross_final',old_feedback['final'],feedback['final'],old_blocks['final'],blocks['final'])]:
            heating[label]=heating_decomposition(a,b)
            block_reports[label]=block_heating_change(qa,qb,width,a['atomic_rate_heating_erg_s_cm3'],b['atomic_rate_heating_erg_s_cm3'])
            if not np.isclose(block_reports[label]['heating_ratio'],heating[label]['metrics']['atomic_rate_heating_erg_s_cm3']['ratio'],rtol=1e-12,atol=0):
                raise RuntimeError('block diagnostic and formal heating normalization differ')
        result={'environment':pipeline.environment(),'endpoints':reports,'formal_gates':summary['gate_checks'],
            'formal_decision':summary['decision'],'failed_gates':verify_gate_inventory(summary),'formal_comparison':comparison,
            'new_adjacent_drift':drift,'cross_final_vs_74057':cross,'heating':heating,'frequency_block_heating':block_reports,
            'old_replay_recomputed':False,'new_maps':0,'new_final_replay_exact':True,'all_new_feedback_blocks_reassembled_exact':True,
            'formal_acceptance_changed':False,'cache_hashes':CACHE_SHA,
            'limitation':'Observed drifts and frequency-block cancellation are diagnostics, not certified inner errors, Jacobians, or physical nonexistence evidence.'}
        pipeline.write_json(out/'audit.json',result)
        saved={'cell_mass_g_cm2':mass}
        for e in vectors:
            saved[e+'_encoded_residual']=vectors[e]
            for k,v in energy[e].items():saved[e+'_ledger_'+k]=v
        np.savez(out/'replayed_arrays.npz',**saved)
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(3,1,figsize=(10,9),layout='constrained')
        axes[0].plot(arrays['mixture_final_ledger_remaining']/1e12,label='74057');axes[0].plot(energy['final']['remaining']/1e12,label='74157')
        axes[0].set(xlabel='Material cell index (not height)',ylabel='Target gas energy (1e12 erg/g)')
        axes[1].plot(cross['cell_squared_l2'],label='cross-final');axes[1].plot(drift['cell_squared_l2'],label='new adjacent')
        axes[1].set(xlabel='Material cell index (not height)',ylabel='Squared encoded difference')
        for k in ('old_adjacent','new_adjacent'):axes[2].plot(block_reports[k]['block_l1'],label=k)
        axes[2].set(xlabel='Frequency-block index',ylabel='Block heating-change L1 (erg/s/cm2)',yscale='symlog')
        for ax in axes:ax.legend()
        fig.suptitle('Four-map response audit; formal rejection unchanged');fig.savefig(out/'response_audit.png',dpi=150);plt.close(fig)
        pipeline.write_json(out/'status.json',{'status':'complete','new_maps':0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
