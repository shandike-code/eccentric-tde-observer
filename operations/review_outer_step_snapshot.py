"""Read-only audit of an archived rebased outer-step feedback pair.

Checks bytes, endpoints, the new denominator and numerical reports. Does not
re-solve the material response or claim an independent physical error bound.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src')]
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):return json.loads(path.read_text())


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def arrays(path):
    with np.load(path,allow_pickle=False) as f:return {k:f[k].copy() for k in f.files}


def review(root,source_run,candidate,round_index):
    manifest=read(root/'ARCHIVE_MANIFEST.json')
    for c in manifest['files']:
        p=root/c['path'];assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256'],c['path']
    def resolve(c):
        rel=Path(c['path'])
        p=root/rel.relative_to(source_run) if rel.is_relative_to(source_run) else root/'inputs'/rel
        assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256'],str(p)
        return p
    declaration=read(root/'declaration.json');base_claims=declaration['outer_baseline']
    base=arrays(resolve(base_claims['material']));baseline=np.load(resolve(base_claims['residual']),allow_pickle=False)
    state=read(root/candidate/'state.json');rd=root/candidate/f'feedback-round{round_index}'
    rec=read(rd/'round_summary.json');proto=read(rd/'feedback_protocol.json');summary=read(rd/'feedback_summary.json')
    assert digest(rd/'feedback_protocol.json')==rec['protocol_sha256']==summary['protocol_sha256']
    assert proto['sources']['base_residual']==base_claims['residual']
    assert proto['sources']['outer_base_material']==base_claims['material']
    assert proto['sources']['physical_old_time_level']==base_claims['physical_old_time_level']
    t=arrays(resolve(proto['sources']['trial_material']))
    assert np.array_equal(t['base_encoded_state'],base['encoded_state'])
    assert np.array_equal(t['base_residual'],baseline) and np.array_equal(t['finite_direction'],baseline)
    assert np.array_equal(t['encoded_state'],base['encoded_state']+float(t['relaxation'])*baseline)
    for k in ('density_g_cm3','phase_index','step_duration_s'):assert np.array_equal(t[k],base[k])
    old=arrays(resolve(proto['sources']['physical_old_time_level']));mass=old['cell_mass_g_cm2']
    residual=np.load(resolve({'path':summary['encoded_residual_path'],'sha256':summary['encoded_residual_sha256'],
        'size_bytes':(rd/'material_residual.npy').stat().st_size}),allow_pickle=False)
    bn=asdict(encoded_residual_norms(baseline,mass));cn=asdict(encoded_residual_norms(residual,mass))
    keys={'l2':'candidate_to_base_residual_l2_ratio','mass_weighted':'candidate_to_base_mass_weighted_norm_ratio',
          'maximum_cell':'candidate_to_base_maximum_cell_norm_ratio'}
    for k,field in keys.items():assert np.isclose(cn[k]/bn[k],summary['comparison'][field],rtol=1e-12,atol=0)
    endpoints={}
    for e in ('previous','final'):
        m=read(rd/'feedback'/f'{e}_manifest.json');c=proto['sources'][e+'_radiation']
        assert m['protocol_sha256']==rec['protocol_sha256'] and m['state_sha256']==c['sha256'] and m['state_path']==c['path']
        assert m['status']=='complete' and m['state_gate_passed']
        assert sorted(b['block_index'] for b in m['completed_blocks'])==list(range(76))
        for b in m['completed_blocks']:assert digest(root/Path(b['partial_path']).relative_to(source_run))==b['partial_sha256']
        assert digest(rd/f'{e}_feedback.npz')==m['feedback_artifact_sha256']
        matches=[r for r in state['history'] if r['input_sha256']==c['sha256'] and r['input_path']==c['path']]
        assert len(matches)==1;endpoints[e]=matches[0]
    assert endpoints['previous']['output_sha256']==endpoints['final']['input_sha256']
    assert endpoints['final']['iteration']==endpoints['previous']['iteration']+1
    reports=[read(f) for name in ('control',candidate) for f in (root/name).glob('map*/block[0-9][0-9].json')]
    assert len(reports)==76*(len(read(root/'control/state.json')['history'])+len(state['history']))
    assert all(np.isfinite(v) for r in reports for v in r.values() if isinstance(v,(int,float)))
    assert all(r['minimum_input_intensity']>=0 and r['minimum_mapped_intensity']>=0 and r['peak_process_rss_mib']<6144 for r in reports)
    processes=[read(f) for name in ('control',candidate) for f in (root/name).rglob('*.process-*.json')]
    assert all(r['memory_guard_passed'] and r['returncode']==0 for r in processes)
    ledger=read(rd/'material_energy_ledger.json');fresh=read(rd/'fresh_control_comparison.json')
    ratios={k:{q:v['candidate_over_base'] for q,v in cs.items()} for k,cs in fresh['comparisons'].items()}
    return {'verified_files':len(manifest['files']),'candidate':candidate,'round':round_index,
        'formal_gates':summary['gate_checks'],'formal_comparison':summary['comparison'],
        'accepted':summary['decision']['finite_trial_accepted_as_one_nonlinear_step'],
        'base_norms':bn,'candidate_norms':cn,'fresh_control_ratios':ratios,
        'endpoints':endpoints,'history':state['history'],'new_denominator_verified':True,
        'gas_domain':{k:{'failed_cells':v['failing_cells'],'min_gas_erg_g':v['absolute_worst_cell_ledger']['remaining_gas_heat_erg_g']} for k,v in ledger['endpoints'].items()},
        'resources':{'map_reports':len(reports),'process_receipts':len(processes),
            'native_peak_mib':max(r['peak_process_rss_mib'] for r in reports),
            'proc_peak_kib':max(r['native_observed_peak_kib'] for r in processes)},
        'physical_response_replayed':False,'true_error_bound':False,'coupled_column_accepted':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--received',type=Path,required=True)
    p.add_argument('--source-run',type=Path,required=True);p.add_argument('--candidate',default='full')
    p.add_argument('--round',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=review(a.received,a.source_run,a.candidate,a.round)
    a.output.with_suffix('.json').write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
    c=d['formal_comparison'];fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    keys=['candidate_to_base_residual_l2_ratio','candidate_to_base_mass_weighted_norm_ratio','candidate_to_base_maximum_cell_norm_ratio']
    axes[0].plot(['L2','Mass','Worst cell'],[c[k] for k in keys],'o-',label='Frozen new base')
    axes[0].plot(['L2','Mass','Worst cell'],[d['fresh_control_ratios']['final']['final'][k] for k in ['l2','mass_weighted','maximum_cell']],'s--',label='Fresh control final')
    axes[0].axhline(1,color='black',lw=.8);axes[0].set(title='Residual norm / baseline');axes[0].legend(fontsize=8)
    axes[1].semilogy([r['iteration'] for r in d['history']],[r['residual'] for r in d['history']],'o-')
    axes[1].axhline(1e-4,color='black',lw=.8);axes[1].axvspan(d['endpoints']['previous']['iteration'],d['endpoints']['final']['iteration'],alpha=.15)
    axes[1].set(xlabel='Candidate map',ylabel='Original radiation residual',title='Evaluated pair shaded')
    axes[2].barh(['Atomic heat','Direct heat','Formal heat','Noise / signal'],[c[k]/t for k,t in [('atomic_heating_volume_l1',.001),('direct_heating_volume_l1',.001),('formal_heating_volume_l1',.001),('inner_noise_to_trial_signal_l2_ratio',.1)]])
    axes[2].axvline(1,color='black',lw=.8);axes[2].set(xlabel='Metric / original threshold',title='Feedback precision')
    fig.suptitle(f'Second outer trial, {a.candidate} pair {a.round}: '+('ACCEPTED finite step' if d['accepted'] else 'NOT ACCEPTED'))
    fig.savefig(a.output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({k:d[k] for k in ('verified_files','accepted','base_norms','candidate_norms','gas_domain','resources')}))


if __name__=='__main__':main()
