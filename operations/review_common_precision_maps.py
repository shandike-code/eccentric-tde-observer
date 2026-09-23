"""Reassemble scalar map diagnostics and audit a retained eight-map archive."""
import argparse
import json
from pathlib import Path
import tarfile
import numpy as np
from operations.review_common_frequency import read,digest,arrays
from operations.common_precision_maps import allow_second_half
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','reference','output'):p.add_argument('--'+k,type=Path,required=True)
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
    assert status['status']=='maps_complete_feedback_required' and status['completed_maps']==8 and status['new_material_steps']==0
    assert not state['active_map'] and not state.get('pending_feedback') and len(state['history'])==8
    assert digest(a.received/'maps/config.json')==state['config_sha256']
    assert digest(a.received/'maps/trial_material.npz')==state['trial_sha256']==digest(a.reference)
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
    assert allow_second_half(histories[:4]) and read(a.received/'second-stage-decision.json')['continue']
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
        'retained_dat_rehashed_on_mac':False,'trial_bitwise_equal_to_bridge':True,'new_material_steps':0,'feedback_evaluated':False}
    a.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained');x=np.arange(1,9)
    axes[0].semilogy(x,[r['residual'] for r in histories],'o-');axes[0].axhline(1e-4,color='black',ls='--');axes[0].set(xlabel='Additional map',ylabel='Radiation residual')
    for field in ('boundary_l1','boundary_bolometric'):axes[1].semilogy(x,[r[field] for r in histories],'o-',label=field)
    axes[1].axhline(1e-3,color='black',ls='--');axes[1].set(xlabel='Additional map',ylabel='Boundary relative change');axes[1].legend()
    fig.suptitle('Fixed matter precision: feedback not yet evaluated');fig.savefig(a.output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k not in ('history','retained_pairs')},indent=2))


if __name__=='__main__':main()
