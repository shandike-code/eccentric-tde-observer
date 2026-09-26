"""Independent reduction of 77927 full/half map evidence, including all neighbors."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,read,digest,verified_inventory,arrays


def main():
    root=Path('outputs/review-20260925');out=root/'tapered-joint-77927-received'
    receipt=root/'complete-1790437815275524374-receipt.json'
    manifest=receive(root/'complete-1790437815275524374.tar.gz',receipt,out)
    prior=root/'heating-validation-77577-complete-received';local=root/'joint-blocks-77817-received'
    cost=root/'joint-line-cost-77905-received'
    for source,ev in [(prior,'20260926-heating-validation-complete-review'),(local,'20260926-joint-block-pilot-review'),(cost,'20260926-joint-line-cost-review')]:
        claim=read(Path('handoff/evidence')/(ev+'.json'))['archive'];archive=root/Path(claim['path']).name
        assert digest(archive)==claim['sha256']
        with tarfile.open(archive) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(source/'ARCHIVE_MANIFEST.json')
        verified_inventory(source)
    d=read(out/'declaration.json');s=read(out/'summary.json');val=read(out/'control/validation.json')
    assert d['taper']=={'kind':'sin_squared_midpoint','groups_per_core':384,'formula':'sin(pi*(j+0.5)/384)^2','free_parameters':0}
    assert d['gates']['full_l2_ratio_max']==.8
    assert d['selected']=='tapered-joint-cores23-to25-and47-to49'
    assert val['field_comparison']['selected_blocks']==[23,24,25,47,48,49]
    terminal=read(Path('handoff/evidence/20260926-tapered-joint-77927-terminal.json'))
    assert terminal['job_id']==77927 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['child_limits']=={'control':10,'half':1} and d['maximum_maps']==11 and d['cadence']==[2,10]
    assert d['maximum_feedback_pairs']==2 and d['accepted_outer_steps']==20 and not d['automatic_promotion'] and not d['baseline_replacement_authorized'] and not d['physical_dt_changed']
    assert s['maps']==2 and s['control_maps']==s['half_maps']==1 and s['new_material_steps']==0 and not s['cases']
    assert not list(out.glob('*/pair*/feedback_protocol.json'))
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    ret=read(prior/'control/endpoints-map10/manifest.json')
    assert d['source_pair']==[ret['endpoints']['final'],ret['endpoints']['mapped_final']]==val['source_pair']
    assert d['source_row']==read(prior/'control/state.json')['history'][-1]
    for i in (24,48):assert d['replacements'][str(i)]==read(local/f'control-block{i:02d}.json')['local_arrays']
    source_trial=arrays(prior/'control/trial_material.npz');peaks=[];rows={};blockmax={}
    for name,key in [('control','actual_map'),('half','half_map')]:
        folder=out/name;trial=arrays(folder/'trial_material.npz')
        assert set(trial)==set(source_trial) and all(np.array_equal(trial[k],source_trial[k]) for k in trial)
        state=read(folder/'state.json');assert state['active_map'] is None and len(state['history'])==1
        assert state['history'][0]==val[key];row=state['history'][0];rows[name]=row
        seed=val['candidate' if name=='control' else 'half_candidate'];assert row['input_sha256']==seed['sha256']
        cfg=read(folder/'config.json');assert digest(folder/'config.json')==state['config_sha256'] and cfg['workers']==16 and cfg['warm_seed']==seed
        reports=[read(folder/f'map0001/block{i:02d}.json') for i in range(76)]
        assert [r['block_index'] for r in reports]==list(range(76))
        assert [(r['core_group_start'],r['core_group_stop']) for r in reports]==[(128*i,min(128*(i+1),9632)) for i in range(76)]
        for r in reports:
            assert r['input_state_sha256']==seed['sha256'] and r['minimum_input_intensity']>=0 and r['minimum_mapped_intensity']>=0
            assert all(np.isfinite(v) for v in r.values() if isinstance(v,(float,int)))
        blockmax[name]=[r['maximum_absolute_radiation_change'] for r in reports]
        maxchange=max(blockmax[name]);scale=max(r['maximum_radiation_scale'] for r in reports)
        rel=maxchange/scale
        l1=math.fsum(r['boundary_spectrum_l1_numerator'] for r in reports)/max(math.fsum(r[k] for r in reports) for k in ('current_boundary_absolute_scale','mapped_boundary_absolute_scale'))
        a,b=[math.fsum(r[k] for r in reports) for k in ('current_boundary_bolometric','mapped_boundary_bolometric')]
        bol=abs(a-b)/max(abs(a),abs(b))
        np.testing.assert_allclose([rel,l1,bol],[row[k] for k in ('residual','boundary_l1','boundary_bolometric')],rtol=2e-9,atol=0)
        processes=list((folder/'map0001').glob('block*.process-*.json'));assert len(processes)==76
        for p in processes:
            r=read(p);assert not r['returncode'] and r['memory_guard_passed'] and r['native_observed_peak_kib']<6*1024**2;peaks.append(r['native_observed_peak_kib'])
    f=val['field_comparison'];slabs=f['slabs'];assert [x['first_group'] for x in slabs]==list(range(0,9632,32))
    assert all(x['group_count']==32 and x['block']==x['first_group']//128 and x['selected_input']==(x['block'] in (23,24,25,47,48,49)) for x in slabs)
    assert all(np.isfinite(x['squared_l2']+x['linf']).all() and min(x['squared_l2']+x['linf'])>=0 for x in slabs)
    sums=[math.fsum(x['squared_l2'][i] for x in slabs) for i in range(4)];maxima=[max(x['linf'][i] for x in slabs) for i in range(4)]
    l2=[math.sqrt(z/sums[0]) for z in sums];linf=[z/maxima[0] for z in maxima]
    np.testing.assert_allclose(l2,f['fixed_scale_l2_ratios'],rtol=1e-13);np.testing.assert_allclose(linf,f['fixed_scale_linf_ratios'],rtol=1e-13)
    for name,i in [('control',1),('half',2)]:
        for block in range(76):np.testing.assert_allclose(max(x['linf'][i] for x in slabs if x['block']==block),blockmax[name][block],rtol=1e-13,atol=0)
    old=d['source_row'];checks=dict(full_l2_benefit=l2[1]<=.8,full_linf_nonincrease=linf[1]<=1.0000000001,half_l2_nonincrease=l2[2]<=1.0000000001,half_linf_nonincrease=linf[2]<=1.0000000001,independent_half_affinity=l2[3]<=1e-6)
    for name,label in [('control','full'),('half','half')]:
        row=rows[name];checks[label+'_radiation']=row['residual']<1e-4
        for k in ('boundary_l1','boundary_bolometric'):checks[label+'_'+k]=row[k]<1e-3 and row[k]<=old[k]*1.0000000001
    assert checks==val['checks'] and val['validated']==all(checks.values())==False
    assert s['status']==read(out/'status.json')['status']=='true_map_not_validated'
    assert val['parent_peak_rss_bytes']<6*1024**3
    ranked=sorted(slabs,key=lambda x:x['linf'][1],reverse=True)[:8]
    result=dict(archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),process_receipts=len(peaks),maximum_worker_peak_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,maps=2,feedback_pairs=0,
        fixed_scale_l2_ratios=l2,fixed_scale_linf_ratios=linf,checks=checks,validated=False,worst_full_slabs=ranked,
        original_defect_l2=math.sqrt(sums[0]),original_defect_linf=maxima[0],rows=rows,
        independent_slab_and_block_reduction=True,raw_global_arrays_recomputed_on_mac=False,operator_recomputed_on_mac=False)
    target=Path('handoff/evidence/20260926-tapered-joint-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained');indices=np.arange(76)
    for name,label in [('control','Full'),('half','Half')]:ax.plot(indices,np.array(blockmax[name])/maxima[0],label=label)
    ax.axhline(1.,color='black',ls='--');ax.set(xlabel='Frequency block',ylabel='Block maximum defect / original GLOBAL maximum',title='Tapered correction: largest defect lies inside selected core');ax.legend()
    fig.savefig(target.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k not in ('worst_full_slabs','rows')},indent=2))


if __name__=='__main__':main()
