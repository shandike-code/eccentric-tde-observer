"""Independent reduction of 79631 full/half map evidence, including all neighbors."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,read,digest,verified_inventory,arrays
from handoff.audit_tools.population_global_decomposition import defect_budget,boundary_ledger


def main():
    root=Path('outputs/review-20260925');out=root/'population-defect-global-79878-received'
    receipt=root/'complete-1790606141718302588-receipt.json'
    manifest=receive(root/'complete-1790606141718302588.tar.gz',receipt,out)
    numeric=root/'late-population-global-79631-received'
    prior=root/'late-direction-79151-complete-received';local=root/'population-defect-79747-received'
    for source,ev in [(prior,'20260928-late-direction-complete-review'),(local,'20260928-population-defect-metadata-review'),(numeric,'20260928-late-population-global-review')]:
        claim=read(Path('handoff/evidence')/(ev+'.json'))['archive'];archive=root/Path(claim['path']).name
        assert digest(archive)==claim['sha256']
        with tarfile.open(archive) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(source/'ARCHIVE_MANIFEST.json')
        verified_inventory(source)
    d=read(out/'declaration.json');s=read(out/'summary.json');val=read(out/'population/validation.json')
    assert d['source_job']==79151 and d['pilot_job']==79747 and d['array_job']==79850
    assert d['source']=='outputs/hpc/step21-late-direction-windows-20260928' and d['source_pilot']=='outputs/hpc/step21-population-defect-pilot-20260928'
    assert read(local/'declaration.json')['source_job_id']==79631 and read(local/'declaration.json')['refreshed_halo']
    assert d['gates']['full_l2_ratio_max']==.8
    assert val['field_comparison']['selected_blocks']==list(range(20,34))
    terminal=read(Path('handoff/evidence/20260928-population-defect-global-79878-terminal.json'))
    assert terminal['job_id']==79878 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['child_limits']=={'control':10,'population':10,'half':1} and d['maximum_maps']==21 and d['cadence']==[2,10]
    assert d['maximum_feedback_pairs']==4 and d['accepted_outer_steps']==20 and not d['automatic_promotion'] and not d['baseline_replacement_authorized'] and not d['physical_dt_changed']
    assert s['maps']==2 and s['map_counts']=={'population':1,'half':1} and s['new_material_steps']==0 and s['cases']=={'control':{},'population':{}}
    assert not list(out.glob('*/pair*/feedback_protocol.json'))
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    ret=read(prior/'population/endpoints-map08/manifest.json')
    assert d['original_pair']==[ret['endpoints']['final'],ret['endpoints']['mapped_final']]==val['original_pair']
    assert d['original_row']==read(prior/'population/state.json')['history'][-1]
    nval=read(numeric/'population/validation.json');nr=read(numeric/'population/state.json')['history'][0]
    assert d['source_pair']==[nval['candidate'],dict(path=nr['output_path'],sha256=nr['output_sha256'],size_bytes=10099884032)]==val['source_pair']
    assert d['source_row']==nr and d['numerical_source_job']==79631 and d['source_rejected'] and d['both_references_must_pass']
    assert not nval['validated'] and d['centers']==[23,30]
    assert d['source_pair']==read(local/'declaration.json')['source_pair']
    for i in (23,30):assert d['replacements'][str(i)]==read(local/f'population-block{i:02d}.json')['local_arrays']
    source_trial=arrays(prior/'population/trial_material.npz');peaks=[];rows={};blockmax={};ledgers={};roundoff={}
    for name,key in [('population','actual_map'),('half','half_map')]:
        folder=out/name;trial=arrays(folder/'trial_material.npz')
        assert set(trial)==set(source_trial) and all(np.array_equal(trial[k],source_trial[k]) for k in trial)
        state=read(folder/'state.json');assert state['active_map'] is None and len(state['history'])==1
        assert state['history'][0]==val[key];row=state['history'][0];rows[name]=row
        seed=val['candidate' if name=='population' else 'half_candidate'];assert row['input_sha256']==seed['sha256']
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
        np.testing.assert_allclose([rel,l1],[row[k] for k in ('residual','boundary_l1')],rtol=2e-9,atol=0)
        # 原aggregate用普通sum后大数相减；先逐位复现，再按γ_n验证独立fsum的舍入界。
        native_a,native_b=[sum(r[k] for r in reports) for k in ('current_boundary_bolometric','mapped_boundary_bolometric')]
        assert abs(native_a-native_b)/max(abs(native_a),abs(native_b))==row['boundary_bolometric']
        eps=np.finfo(float).eps;gamma=len(reports)*eps/(1-len(reports)*eps)
        flux_abs=math.fsum(abs(r[k]) for r in reports for k in ('current_boundary_bolometric','mapped_boundary_bolometric'))
        bound=4*gamma*flux_abs/max(abs(a),abs(b))*(1+abs(bol))
        assert abs(bol-row['boundary_bolometric'])<=bound
        roundoff[name]=dict(independent_fsum_bolometric=bol,absolute_difference=abs(bol-row['boundary_bolometric']),gamma_n_bound=bound)
        ledgers[name]=boundary_ledger(reports)
        processes=list((folder/'map0001').glob('block*.process-*.json'));assert len(processes)==76
        for p in processes:
            r=read(p);assert not r['returncode'] and r['memory_guard_passed'] and r['native_observed_peak_kib']<6*1024**2;peaks.append(r['native_observed_peak_kib'])
    f=val['field_comparison'];slabs=f['slabs'];assert [x['first_group'] for x in slabs]==list(range(0,9632,32))
    assert all(x['group_count']==32 and x['block']==x['first_group']//128 and x['selected_input']==(x['block'] in range(20,34)) for x in slabs)
    assert all(np.isfinite(x['squared_l2']+x['linf']).all() and min(x['squared_l2']+x['linf'])>=0 for x in slabs)
    sums=[math.fsum(x['squared_l2'][i] for x in slabs) for i in range(4)];maxima=[max(x['linf'][i] for x in slabs) for i in range(4)]
    l2=[math.sqrt(z/sums[0]) for z in sums];linf=[z/maxima[0] for z in maxima]
    np.testing.assert_allclose(l2,f['fixed_scale_l2_ratios'],rtol=1e-13);np.testing.assert_allclose(linf,f['fixed_scale_linf_ratios'],rtol=1e-13)
    for name,i in [('population',1),('half',2)]:
        for block in range(76):np.testing.assert_allclose(max(x['linf'][i] for x in slabs if x['block']==block),blockmax[name][block],rtol=1e-13,atol=0)
    for block in range(76):
        original=read(numeric/f'population/map0001/block{block:02d}.json')
        np.testing.assert_allclose(max(x['linf'][0] for x in slabs if x['block']==block),original['maximum_absolute_radiation_change'],rtol=1e-13,atol=0)
    original=val['original_comparison'];oslabs=original['slabs']
    assert [r['first_group'] for r in oslabs]==list(range(0,9632,32))
    assert not original['half_is_original_midpoint'] and not original['affinity_tested_here']
    assert all(r['group_count']==32 and r['block']==r['first_group']//128 for r in oslabs)
    assert all(np.isfinite(r['squared_l2']+r['linf']).all() and min(r['squared_l2']+r['linf'])>=0 for r in oslabs)
    osums=[math.fsum(r['squared_l2'][i] for r in oslabs) for i in range(3)]
    omaxima=[max(r['linf'][i] for r in oslabs) for i in range(3)]
    ol2=[math.sqrt(z/osums[0]) for z in osums];olinf=[z/omaxima[0] for z in omaxima]
    np.testing.assert_allclose(ol2,original['fixed_scale_l2_ratios'],rtol=1e-13,atol=0)
    np.testing.assert_allclose(olinf,original['fixed_scale_linf_ratios'],rtol=1e-13,atol=0)
    for a,b in zip(slabs,oslabs,strict=True):
        assert a['squared_l2'][1:3]==b['squared_l2'][1:3] and a['linf'][1:3]==b['linf'][1:3]
    for block in range(76):
        x=read(prior/f'population/map0008/block{block:02d}.json')
        assert max(r['linf'][0] for r in oslabs if r['block']==block)==x['maximum_absolute_radiation_change']
    checks={}
    for prefix,a,b,old in [('current',l2,linf,d['source_row']),('original',ol2,olinf,d['original_row'])]:
        group=dict(full_l2_benefit=a[1]<=.8,full_linf_nonincrease=b[1]<=1.0000000001,
                   half_l2_nonincrease=a[2]<=1.0000000001,half_linf_nonincrease=b[2]<=1.0000000001)
        if prefix=='current':group['independent_half_affinity']=a[3]<=1e-6
        for name,label in [('population','full'),('half','half')]:
            row=rows[name];group[label+'_radiation']=row['residual']<1e-4
            for k in ('boundary_l1','boundary_bolometric'):group[label+'_'+k]=row[k]<1e-3 and row[k]<=old[k]*1.0000000001
        checks.update({prefix+'_'+k:v for k,v in group.items()})
    assert checks==val['checks'] and val['validated']==all(checks.values())==False
    assert s['status']==read(out/'status.json')['status']=='stopped_at_full_half_validation'
    assert val['parent_peak_rss_bytes']<6*1024**3
    ledgers['original']=boundary_ledger([read(prior/f'population/map0008/block{i:02d}.json') for i in range(76)])
    ledgers['current']=boundary_ledger([read(numeric/f'population/map0001/block{i:02d}.json') for i in range(76)])
    budget=defect_budget(slabs,selected=tuple(range(20,34)))
    ranked=sorted(slabs,key=lambda x:x['linf'][1],reverse=True)[:8]
    result=dict(job_id=79878,frozen_material_case='population',source_job_id=79151,archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),process_receipts=len(peaks),maximum_worker_peak_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,maps=2,feedback_pairs=0,
        fixed_scale_l2_ratios=l2,fixed_scale_linf_ratios=linf,original_l2_ratios=ol2,original_linf_ratios=olinf,checks=checks,validated=False,worst_full_slabs=ranked,
        original_defect_l2=math.sqrt(sums[0]),original_defect_linf=maxima[0],rows=rows,
        defect_budget=budget,boundary_ledger=ledgers,boundary_reduction_roundoff=roundoff,
        independent_slab_and_block_reduction=True,raw_global_arrays_recomputed_on_mac=False,operator_recomputed_on_mac=False)
    target=Path('handoff/evidence/20260928-population-defect-global-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,4.4),layout='constrained');indices=np.arange(76);ax=axes[0]
    for name,label in [('population','Full'),('half','Half')]:ax.plot(indices,np.array(blockmax[name])/maxima[0],label=label)
    ax.axhline(1.,color='black',ls='--');ax.set(xlabel='Frequency block',ylabel='Block maximum defect / original GLOBAL maximum',title='Maximum defect by block');ax.legend()
    for i,label in ((0,'Current q'),(1,'Full'),(2,'Half')):
        axes[1].plot(indices,[x['squared_l2'][i]/sums[0] for x in budget['blocks']],label=label)
    axes[1].axvspan(19.5,33.5,alpha=.12,color='green');axes[1].set(xlabel='Frequency block',ylabel='Squared defect / original total squared L2',title='Squared L2 budget');axes[1].legend()
    for name,label in (('original','Original x'),('current','Current q'),('population','Full'),('half','Half')):
        ledger=ledgers[name];scale=max(abs(ledger['total_input']),abs(ledger['total_mapped']))
        axes[2].plot(indices,[r['signed_change']/scale for r in ledger['rows']],label=label)
    axes[2].axhline(0,color='black',lw=.6);axes[2].set(xlabel='Frequency block',ylabel='Signed block flux change / global flux scale',title='Boundary cancellation');axes[2].legend()
    fig.savefig(target.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k not in ('worst_full_slabs','rows','defect_budget','boundary_ledger')},indent=2))


if __name__=='__main__':main()
