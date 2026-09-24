"""Reassemble scalar map diagnostics and audit a retained eight-map archive."""
import argparse
import json
from pathlib import Path
import tarfile
import numpy as np
from operations.review_common_frequency import read,digest,arrays
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec,ground_state_material_trial_within_trust_region
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','reference','physical-old','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();c=read(a.receipt)
    assert a.archive.stat().st_size==c['size_bytes'] and digest(a.archive)==c['sha256']
    a.received.mkdir(exist_ok=False)
    with tarfile.open(a.archive) as t:
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers())
        t.extractall(a.received,filter='data')
    manifest=read(a.received/'ARCHIVE_MANIFEST.json')
    for c in manifest['files']:
        f=a.received/c['path'];assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    state=read(a.received/'maps/state.json');cfg=read(a.received/'maps/config.json');status=read(a.received/'status.json')
    assert status['status']=='budget_complete_not_accepted' and status['accepted_outer_steps']==17 and status['new_material_steps']==0
    assert not state['active_map'] and not state.get('pending_feedback') and len(state['history'])==8
    assert digest(a.received/'maps/config.json')==state['config_sha256']
    assert digest(a.received/'maps/trial_material.npz')==state['trial_sha256']==digest(a.received/'inputs/trial_material.npz')
    trial=arrays(a.received/'maps/trial_material.npz');base=arrays(a.received/'inputs/outer_base_material.npz')
    accepted=arrays(a.reference/'trial_material.npz');old=arrays(a.physical_old)
    residual=np.load(a.received/'inputs/base_residual.npy',allow_pickle=False)
    assert np.array_equal(residual,arrays(a.reference/'common-feedback/final_response.npz')['residual'])
    assert np.array_equal(trial['base_residual'],residual) and np.array_equal(trial['finite_direction'],residual)
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[k],accepted[k])
    assert np.array_equal(trial['base_encoded_state'],base['encoded_state'])
    assert np.array_equal(trial['encoded_state'],base['encoded_state']+residual/64) and float(trial['relaxation'])==1/64
    codec=GroundStateLogSimplexCodec(128);decoded=codec.decode(trial['encoded_state'])
    for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        np.testing.assert_allclose(trial[k],getattr(decoded,k),rtol=8*np.finfo(float).eps,atol=0)
    assert ground_state_material_trial_within_trust_region(codec,base['encoded_state'],trial['encoded_state'],maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,maximum_population_fraction_change=.05)
    phase=int(trial['phase_index']);assert phase==int(base['phase_index'])
    assert np.array_equal(trial['density_g_cm3'],old['density_g_cm3'][phase]) and float(trial['step_duration_s'])==float(old['step_duration_s'][phase])
    source=read(a.received/'inputs/feedback_reference.json')['sources']['physical_old_time_level']
    assert digest(a.physical_old)==source['sha256'] and a.physical_old.stat().st_size==source['size_bytes']
    assert state['history'][0]['input_sha256']==read(a.reference/'state.json')['current_sha256']
    summary=read(a.received/'summary.json')
    assert summary['status']==status['status'] and summary['accepted_outer_steps']==17 and summary['new_material_steps']==0
    assert summary['pairs']=={str(n):dict(inner_pair_ready=False,feedback_evaluated=False) for n in (4,8)}
    assert not list(a.received.glob('pair*/feedback_summary.json'))
    assert read(a.received/'maps/initialized_identity.json')['passed']
    assert cfg['workers']==16 and cfg['maximum_maps']==8 and cfg['radiation_threshold']==1e-4
    histories=state['history'];peaks=[];times=[]
    for row in histories:
        n=row['iteration'];folder=a.received/f'maps/map{n:04d}';rows=[read(folder/f'block{i:02d}.json') for i in range(76)]
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
    for before,after in zip(histories,histories[1:]):assert before['output_sha256']==after['input_sha256']
    assert histories[-1]['output_sha256']==state['current_sha256']
    assert histories[-1]['output_path']==state['slots'][state['current_slot']]
    assert all(histories[i+1]['residual']<histories[i]['residual'] for i in range(7))
    assert all(r['residual']>=1e-4 for r in histories)
    assert all(0<=r[k]<1e-3 for r in histories for k in ('boundary_l1','boundary_bolometric'))
    pairs={}
    for n in (4,8):
        m=read(a.received/f'endpoints-map{n:02d}/manifest.json');assert m['history_rows']==histories[n-2:n]
        for label,row,kind in [('previous',histories[n-2],'input'),('final',histories[n-1],'input'),('mapped_final',histories[n-1],'output')]:
            c=m['endpoints'][label];assert c['sha256']==row[kind+'_sha256'] and c['size_bytes']==10099884032
            assert f'endpoints-map{n:02d}/' in c['path'] and '/maps/state_' not in c['path']
        pairs[str(n)]=m['endpoints']
    result={'verified_files':len(manifest['files']),'maps':8,'map_blocks':608,'independent_process_receipts':len(peaks),
        'history':histories,'maximum_proc_kib':max(peaks),'maximum_native_mib':max(r['maximum_worker_rss_mib'] for r in histories),
        'total_map_wall_s':sum(times),'map_wall_range_s':[min(times),max(times)],'retained_pairs':pairs,
        'retained_dat_rehashed_on_mac':False,'candidate_identity_verified':True,'accepted_outer_steps':17,'archive':read(a.receipt),'new_material_steps':0,'feedback_evaluated':False}
    a.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained');x=np.arange(1,9)
    axes[0].semilogy(x,[r['residual'] for r in histories],'o-');axes[0].axhline(1e-4,color='black',ls='--');axes[0].set(xlabel='Additional map',ylabel='Radiation residual')
    for field in ('boundary_l1','boundary_bolometric'):axes[1].semilogy(x,[r[field] for r in histories],'o-',label=field)
    axes[1].axhline(1e-3,color='black',ls='--');axes[1].set(xlabel='Additional map',ylabel='Boundary relative change');axes[1].legend()
    fig.suptitle('Fixed matter precision: feedback not yet evaluated');fig.savefig(a.output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k not in ('history','retained_pairs')},indent=2))


if __name__=='__main__':main()
