"""Audit a completed fixed-material confirmation stage using its actual source replay."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--received',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--title',required=True);a=p.parse_args();root=a.received
    read=lambda p:json.loads(p.read_text())
    manifest=read(root/'ARCHIVE_MANIFEST.json')
    for c in manifest['files']:
        f=root/c['path']
        assert f.stat().st_size==c['size_bytes']
        assert hashlib.file_digest(f.open('rb'),'sha256').hexdigest()==c['sha256']
    result=read(root/'confirmation.json');assert result['precision_confirmation_passed'] is True
    source=read(root/'source-gate-replay.json')
    assert source['final_residual_bitwise_equal'] is True and all(source['checks'].values())
    plan=read(root/'declaration.json')
    audits={};maps=[];processes=[]
    for name in ('control','confirm2','confirm4'):
        child=root/name;state=read(child/'state.json');rd=child/'feedback-round1'
        assert not state.get('pending_feedback') and not state.get('active_map') and len(state['history'])==2
        source_claim=plan['cases']['base' if name=='control' else 'trial']['trial']
        assert hashlib.file_digest((child/'trial_material.npz').open('rb'),'sha256').hexdigest()==source_claim['sha256']
        proto=read(rd/('baseline_control_protocol.json' if name=='control' else 'feedback_protocol.json'))
        assert proto['sources']['trial_material']['sha256']==source_claim['sha256']
        denominator=root/'inputs'/proto['sources']['base_residual']['path']
        assert hashlib.file_digest(denominator.open('rb'),'sha256').hexdigest()==proto['sources']['base_residual']['sha256']
        with np.load(child/'trial_material.npz',allow_pickle=False) as trial:
            assert np.array_equal(trial['base_residual'],np.load(denominator,allow_pickle=False))
        ledger=read(rd/'material_energy_ledger.json')
        assert all(e['failing_cells']==0 for e in ledger['endpoints'].values())
        audits[name]={'status':state['status'],'history':state['history'],
            'gas_domain_failed_cells':{k:v['failing_cells'] for k,v in ledger['endpoints'].items()},
            'minimum_gas_energy_erg_g':{k:v['absolute_worst_cell_ledger']['remaining_gas_heat_erg_g'] for k,v in ledger['endpoints'].items()}}
        for mp in sorted(child.glob('map[0-9]*')):
            reports=[read(f) for f in sorted(mp.glob('block[0-9][0-9].json'))]
            assert sorted(r['block_index'] for r in reports)==list(range(76))
            assert all(np.isfinite(v) for r in reports for v in r.values() if isinstance(v,(int,float)))
            assert all(r['minimum_input_intensity']>=0 and r['minimum_mapped_intensity']>=0 and r['peak_process_rss_mib']<6144 for r in reports)
            maps.extend(reports)
        records=[read(f) for f in child.rglob('*.process-*.json')];assert records
        assert all(r['memory_guard_passed'] and r['returncode']==0 for r in records);processes.extend(records)
        if name!='control':
            summary=read(rd/'feedback_summary.json');assert len(summary['gate_checks'])==16 and all(summary['gate_checks'].values())
            assert summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] is True
            comparison=read(rd/'fresh_control_comparison.json')
            ratios={k:{q:v['candidate_over_base'] for q,v in cs.items()} for k,cs in comparison['comparisons'].items()}
            assert all(x<1 for cs in ratios.values() for rs in cs.values() for x in rs.values())
            audits[name].update(gates=summary['gate_checks'],fresh_control_ratios=ratios)
    result.update(verified_files=len(manifest['files']),audits=audits,resources={
        'map_reports':len(maps),'process_receipts':len(processes),
        'maximum_native_rss_mib':max(r['peak_process_rss_mib'] for r in maps),
        'maximum_observed_proc_kib':max(r['native_observed_peak_kib'] for r in processes)})
    a.output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    labels=['Accepted','+2 maps','+4 maps']
    axes[0].plot(labels,[source['atomic_heating_volume_l1']]+[result['cases'][k]['formal_comparison']['atomic_heating_volume_l1'] for k in ('confirm2','confirm4')],'o-')
    axes[0].axhline(.001,color='black',lw=.8);axes[0].set(title='Heating pair change',ylabel='Relative L1 change')
    axes[1].plot(labels,[source['inner_noise_to_trial_signal_l2_ratio']]+[result['cases'][k]['formal_comparison']['inner_noise_to_trial_signal_l2_ratio'] for k in ('confirm2','confirm4')],'o-')
    axes[1].axhline(.1,color='black',lw=.8);axes[1].set(title='Noise / material-step signal')
    for name in ('confirm2','confirm4'):
        c=result['cases'][name]['formal_comparison']
        axes[2].plot(['L2','Mass','Worst cell'],[c[k] for k in ('candidate_to_base_residual_l2_ratio','candidate_to_base_mass_weighted_norm_ratio','candidate_to_base_maximum_cell_norm_ratio')],'o-',label=name)
    axes[2].axhline(1,color='black',lw=.8);axes[2].set(title='Residual / frozen step baseline');axes[2].legend()
    fig.suptitle(a.title+': fixed accepted material; NOT a converged column')
    fig.savefig(a.output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({'verified_files':result['verified_files'],'resources':result['resources'],'audits':{k:v['gas_domain_failed_cells'] for k,v in audits.items()}}))


if __name__=='__main__':main()
