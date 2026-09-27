"""Independent 78594 stationarity audit; no production window reducer reused."""
import argparse,json,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_step21_control_windows as cw
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close
read,digest,arrays=cw.read,cw.digest,cw.arrays

def audit_maps(out):
    folder=out/'control';state=read(folder/'state.json');history=state['history']
    assert 1<=len(history)<=16 and state['active_map'] is None
    assert [r['iteration'] for r in history]==list(range(1,len(history)+1))
    assert all(a['output_sha256']==b['input_sha256'] for a,b in zip(history,history[1:]))
    assert digest(folder/'config.json')==state['config_sha256'] and read(folder/'initialized_identity.json')['passed']
    reports=[];peaks=[]
    for row in history:
        work=folder/f"map{row['iteration']:04d}";rows=[read(work/f'block{i:02d}.json') for i in range(76)]
        assert len({b['protocol_sha256'] for b in rows})==1
        ownership=np.zeros(9632,int)
        for i,b in enumerate(rows):
            assert b['block_index']==i and b['input_state_sha256']==row['input_sha256']
            assert b['minimum_input_intensity']>=0 and b['minimum_mapped_intensity']>=0
            assert all(np.isfinite(v) for v in b.values() if isinstance(v,(float,int))) and b['peak_process_rss_mib']<6144
            lo,hi=b['core_group_start'],b['core_group_stop'];assert 0<=lo<hi<=9632;ownership[lo:hi]+=1
            files=list(work.glob(f'block{i:02d}.process-*.json'));assert len(files)==1
            q=read(files[0]);assert q['returncode']==0 and q['memory_guard_passed'] and q['native_observed_peak_kib']<6144*1024
            peaks.append(q['native_observed_peak_kib'])
        assert np.all(ownership==1)
        assert row['maximum_worker_rss_mib']==max(b['peak_process_rss_mib'] for b in rows)
        scale=max(b['maximum_radiation_scale'] for b in rows);assert scale>0
        residual=max(b['maximum_absolute_radiation_change'] for b in rows)/scale
        l1=sum(b['boundary_spectrum_l1_numerator'] for b in rows)/max(sum(b['current_boundary_absolute_scale'] for b in rows),sum(b['mapped_boundary_absolute_scale'] for b in rows))
        before=sum(b['current_boundary_bolometric'] for b in rows);after=sum(b['mapped_boundary_bolometric'] for b in rows)
        bol=abs(after-before)/max(abs(before),abs(after))
        for k,v in [('residual',residual),('boundary_l1',l1),('boundary_bolometric',bol)]:assert v==row[k]
        worst=max(rows,key=lambda b:b['block_relative_radiation_change'])
        reports.append({'iteration':row['iteration'],'residual':residual,'boundary_l1':l1,'boundary_bolometric':bol,
                        'worst_self_scaled_block':worst['block_index'],'worst_self_scaled_change':worst['block_relative_radiation_change'],'wall_s':row['wall_s']})
    return reports,peaks


def review(archive,receipt,received,prior,reference,physical_old,output,terminal=None):
    manifest=cw.receive(archive,receipt,received)
    old_audit=read(Path('handoff/evidence/20260927-seven-refresh-short-complete-review.json'))
    claim=old_audit['archive'];arc=archive.parent/Path(claim['path']).name
    assert arc.stat().st_size==claim['size_bytes'] and digest(arc)==claim['sha256']
    with tarfile.open(arc) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(prior/'ARCHIVE_MANIFEST.json')
    cw.verified_inventory(prior)
    out=received;d=read(out/'declaration.json');status=read(out/'status.json')
    assert d['source_job']==78548 and d['source']=='outputs/hpc/step21-seven-refresh-short-validation-20260927'
    assert (d['maximum_maps'],d['maximum_feedback_pairs'],d['cadence'],d['window_tolerance'])==(16,2,[8,16],.001)
    assert d['cumulative_drift_gate'] and d['stop_on_first_failed_window']
    assert not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed'))
    assert d['accepted_outer_steps']==status['accepted_outer_steps']==20 and status['new_material_steps']==0
    assert set(d['cases'])=={'control'} and d['seed']==read(prior/'control/endpoints-map10/manifest.json')['endpoints']['mapped_final']
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    for c in d['cases']['control'].values():
        p=out/'inputs'/Path(c['path']).name;assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    trial=arrays(out/'control/trial_material.npz');source_trial=arrays(prior/'control/trial_material.npz')
    assert set(trial)==set(source_trial) and all(np.array_equal(trial[k],source_trial[k]) for k in trial)
    cfg=read(out/'control/config.json');assert cfg['workers']==16 and cfg['maximum_maps']==16 and cfg['warm_seed']==d['seed']
    maps,peaks=audit_maps(out);state=read(out/'control/state.json')
    assert state['history'][0]['input_sha256']==d['seed']['sha256']
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r=np.load(reference/'base_residual.npy',allow_pickle=False)
    source=read(prior/'control/pair10/feedback_protocol.json')
    origin={e:arrays(prior/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')};previous=origin
    selected=[n for n in (8,16) if (out/f'control/pair{n:02d}/decision.json').exists()]
    assert selected in ([8],[8,16]) and len(maps)==selected[-1]
    results={};receipts=0
    for n in selected:
        folder=out/f'control/pair{n:02d}';p=read(folder/'feedback_protocol.json');decision=read(folder/'decision.json')
        for key in ('acceptance_gates','formal_state_gates','outer_iteration'):assert p[key]==source[key]
        for key,path in [('stationarity_confirmation_declaration',out/'declaration.json'),('control_window_declaration',out/'declaration.json'),
                         ('retained_manifest',out/f'control/endpoints-map{n:02d}/manifest.json')]:
            assert p['sources'][key]['sha256']==digest(path)
        for c in p['common_code_claims']:
            f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
        report,vectors,resources=cw.audit_pair(out,n,reference,physical_old,out/'inputs/trial_material.npz')
        peaks.extend(resources);receipts+=len(resources)
        window=cw.recompute_window(vectors,previous,r,mass);total=cw.recompute_window(vectors,origin,r,mass)
        cw.verify_window(window,decision['window_comparison']);cw.verify_window(total,decision['from_78548_comparison'])
        drift=dict(zip(cw.NAMES,cw.independent_norms(vectors['final']-r,mass)))
        for k,x in drift.items():assert_close(x,decision['fresh_control_minus_r20_norms'][k])
        assert decision['feedback_evaluated'] and decision['zero_control_stable'] and decision['original_gates']==report['gate_checks']
        assert not decision['baseline_replaced'] and not decision['promoted'] and decision['parent_peak_rss_bytes']<6*1024**3
        passed=all(report['gate_checks'].values()) and window['passed'] and total['passed']
        assert passed==decision['confirmation_pass']
        results[str(n)]={**report,'window':window,'from_78548':total,'confirmation_pass':passed,'final_minus_r20':drift}
        previous=vectors
    if len(maps)>8:assert results['8']['confirmation_pass']
    complete=(out/'summary.json').exists()
    if complete:
        assert terminal is not None
        term=read(terminal);assert term['job_id']==78594 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
        s=read(out/'summary.json');assert s['status']==status['status'] and s['maps']==len(maps)
        assert s['accepted_outer_steps']==20 and s['new_material_steps']==0 and not s['baseline_replaced'] and not s['strict_error_bound']
        if s['status']=='persistent_control_stationarity_requires_review':assert selected==[8,16] and all(z['confirmation_pass'] for z in results.values())
        elif s['status']=='stationarity_not_confirmed':assert not results[str(selected[-1])]['confirmation_pass']
        else:raise AssertionError('unexpected failure requires a dedicated audit')
        for n in selected:assert s['windows'][str(n)]==read(out/f'control/pair{n:02d}/decision.json')
    else:assert manifest['stage'] in ('control-map08-feedback','control-map16-feedback')
    result=dict(job_id=78594,archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
        maps=maps,feedback_rounds=selected,windows=results,final_summary_present=complete,
        map_process_receipts=76*len(maps),feedback_process_receipts=receipts,maximum_proc_kib=max(peaks),
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
        production_window_reducer_reused=False,original_seven_gate_reducer_reused=True,
        material_ode_recomputed_on_mac=False,full_large_fields_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax,key,label in zip(axes,('window','from_78548'),('Each eight-map window','Cumulative from 78548')):
        for i,name in enumerate(cw.NAMES):
            ax.plot(selected,[max(v[i] for v in results[str(n)][key]['vector_difference_over_frozen_r20_norms'].values()) for n in selected],'o-',label=name)
        ax.axhline(.001,ls='--',color='black');ax.set(title=label,xlabel='Additional maps',ylabel='Vector difference / original r20 norm');ax.legend(fontsize=8)
    fig.suptitle('Fixed x20 stationarity confirmation; no new material acceptance')
    fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','prior','reference','physical-old','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--terminal',type=Path)
    r=review(**vars(p.parse_args()));print(json.dumps({k:r[k] for k in ('verified_files','feedback_rounds','windows')},indent=2))

