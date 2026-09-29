"""Independently compare all ten Slurm replays to already audited source arrays."""
from pathlib import Path
import json, tarfile
import numpy as np
from handoff.audit_tools import review_refreshed_directions as prior
cw,read,arrays=prior.cw,prior.read,prior.arrays


def main():
    root=Path('outputs/review-20260925');out=root/'response-replay-80542-received'
    receipt=root/'complete-1790650114570419376-receipt.json'
    inventory=cw.receive(root/'complete-1790650114570419376.tar.gz',receipt,out)
    d=read(out/'declaration.json');s=read(out/'summary.json')
    terminal=read(Path('handoff/evidence/20260929-response-replay-80542-terminal.json'))
    assert terminal['job_id']==80542 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='80542'
    assert d['source_job']==80195 and d['accepted_job']==76727 and d['maximum_endpoints']==10
    assert d['maximum_maps']==d['maximum_feedback_integrations']==0 and d['tolerance']==1e-12
    assert d['physical_state_x20_unchanged'] and not d['baseline_replacement_authorized'] and not d['automatic_promotion']
    assert read(out/'status.json')['status']==s['status']=='complete_requires_review'
    assert s['all_replays_passed'] and s['material_ode_recomputed'] and s['physical_state_x20_unchanged']
    assert s['accepted_outer_steps']==20 and s['new_material_steps']==s['new_maps']==s['new_feedback_integrations']==0
    assert not s['baseline_replaced'] and not s['old_r20_reinterpreted'] and s['peak_rss_bytes']<6*1024**3
    for c in d['code']:prior.verify_claim(c,Path(c['path']))
    current=root/'boundary-response-80195-received'
    accepted=Path('outputs/review-20260924/common-confirmation20-76727-received')
    # Prove source extraction against its previously reviewed archive, not folder names.
    for folder,ap,archive_root in [(current,'20260929-boundary-response-review.json',root),
            (accepted,'20260924-common-confirmation20-review.json',accepted.parent)]:
        a=read(Path('handoff/evidence')/ap);c=a['archive'];arc=archive_root/Path(c['path']).name
        prior.verify_claim(c,arc)
        with tarfile.open(arc) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(folder/'ARCHIVE_MANIFEST.json')
        cw.verified_inventory(folder)
    groups=[('accepted',accepted/'confirm2/common-feedback')]+[(f'{name}{n:02d}',current/name/f'pair{n:02d}') for n in (2,10) for name in ('control','population')]
    claim_index={c['path']:c for c in d['claims']}
    old=arrays(Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'))
    mass=old['cell_mass_g_cm2'];results={}
    physical=('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s')
    a=arrays(accepted/'confirm2/trial_material.npz');b=arrays(current/'control/trial_material.npz')
    assert all(np.array_equal(a[k],b[k]) for k in physical)
    for tag,folder in groups:
        prefix='outputs/hpc/common-confirmation20-20260924/confirm2/common-feedback' if tag=='accepted' else f'outputs/hpc/step21-boundary-seed-response-20260929/{tag[:-2]}/pair{tag[-2:]}'
        p=read(folder/'feedback_protocol.json')
        for f in ('feedback_protocol.json','previous_feedback.npz','final_feedback.npz','previous_response.npz','final_response.npz'):
            prior.verify_claim(claim_index[prefix+'/'+f],folder/f)
        prior.verify_claim(p['sources']['physical_old_time_level'],Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'))
        for end in ('previous','final'):
            actual=arrays(out/f'{tag}-{end}-response.npz');stored=arrays(folder/f'{end}_response.npz')
            row=read(out/f'{tag}-{end}.json');assert row==s['endpoints'][tag+'/'+end]
            assert set(actual)==set(row['fields'])=={'residual','temperature_k','hydrogen_fraction','helium_fraction','target_specific_material_energy_erg_g'}
            for k,v in actual.items():
                assert np.isfinite(v).all() and np.array_equal(v,stored[k])
                assert row['fields'][k]==dict(bitwise_equal=True,maximum_scaled_error=0.,passed=True)
            book=arrays(folder/f'{end}_energy_ledger.npz')
            assert np.isfinite(book['remaining']).all() and np.all(book['remaining']>0)
            assert np.array_equal(book['target']-book['ion_new'],book['remaining'])
            np.testing.assert_allclose(row['minimum_gas_erg_g'],book['remaining'].min(),rtol=1e-12,atol=0)
            norms=cw.independent_norms(actual['residual'],mass)
            np.testing.assert_allclose(norms,[row['norms'][k] for k in cw.NAMES],rtol=1e-12,atol=0)
            assert row['phase']==1367 and row['duration_s']==889.419892762322 and row['material_ode_recomputed']
            results[tag+'/'+end]=dict(all_five_fields_bitwise_equal=True,independent_norms=dict(zip(cw.NAMES,norms.tolist())),minimum_gas_erg_g=float(book['remaining'].min()))
    assert len(results)==10 and set(results)==set(s['endpoints'])
    result=dict(job_id=80542,archive=read(receipt),verified_files=len(inventory['files']),verified_code_claims=len(d['code']),
        all_ten_endpoints_bitwise_equal=True,independent_array_comparison=True,physical_state_x20_unchanged=True,
        endpoints=results,accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,
        material_ode_recomputed_on_school=True,material_ode_recomputed_on_mac=False,radiation_operator_recomputed=False)
    Path('handoff/evidence/20260929-response-replay-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('job_id','verified_files','verified_code_claims','all_ten_endpoints_bitwise_equal')},indent=2))


if __name__=='__main__':main()
