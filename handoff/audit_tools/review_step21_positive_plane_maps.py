"""Small-artifact true-map audit for the frozen positive-plane coefficients."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_close(actual,expected):
    np.testing.assert_allclose(actual,expected,rtol=2e-13,atol=0)


def guarded_ratio(a,b):
    if b==0:
        if a==0:return 0.
        raise ArithmeticError('zero normalization with nonzero numerator')
    return a/b


def review(archive,receipt,received,prior,scan,output):
    claim=read(receipt);assert archive.stat().st_size==claim['size_bytes'] and sha(archive)==claim['sha256']
    with tarfile.open(archive) as t:
        manifest=json.load(t.extractfile('ARCHIVE_MANIFEST.json'))
        assert len(t.getmembers())==len(manifest['files'])+1
        for c in manifest['files']:
            assert not Path(c['path']).is_absolute() and '..' not in Path(c['path']).parts
            m=t.getmember(c['path']);assert m.isfile()
            data=t.extractfile(m).read();q=received/c['path']
            assert len(data)==c['size_bytes'] and hashlib.sha256(data).hexdigest()==c['sha256']
            assert q.stat().st_size==c['size_bytes'] and sha(q)==c['sha256']
    for root in (prior,scan):
        for c in read(root/'ARCHIVE_MANIFEST.json')['files']:
            f=root/c['path'];assert f.stat().st_size==c['size_bytes'] and sha(f)==c['sha256']
    plan=read(received/'declaration.json');scan_plan=read(scan/'declaration.json')
    assert plan['maximum_maps']==9 and plan['maximum_feedback_pairs']==3 and plan['accepted_outer_steps']==20
    assert plan['automatic_promotion'] is False and plan['physical_dt_changed'] is False
    for c in plan['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and sha(p)==c['sha256']
    rows={};total_receipts=0
    for case in ('control','thermal','population'):
        folder=received/case;v=read(folder/'validation.json');s=read(folder/'state.json');cfg=read(folder/'config.json')
        assert s['active_map'] is None and 1<=len(s['history'])<=3 and s['history'][0]==v['actual_map']
        assert sha(folder/'config.json')==s['config_sha256'] and sha(folder/'trial_material.npz')==s['trial_sha256']
        assert (folder/'trial_material.npz').read_bytes()==(prior/case/'trial_material.npz').read_bytes()
        assert read(folder/'initialized_identity.json')['passed'] is True
        assert plan['basis'][case]==scan_plan['cases'][case]
        assert cfg['warm_seed']==v['candidate'] and v['candidate']['sha256']==v['actual_map']['input_sha256']
        assert v['candidate']['size_bytes']==10099884032
        predicted=plan['prediction'][case];assert predicted==read(scan/'prediction.json')[case]
        assert predicted['feasible'] and all(predicted['rounds'][-1]['result']['gates'].values())
        assert v['effective_uv']==predicted['rounds'][-1]['result']['uv']
        old_validation=read(prior/case/'validation.json');ret=read(prior/case/'endpoints-map03/manifest.json')
        assert plan['basis'][case]['basis']==[old_validation['candidate']]+[ret['endpoints'][k] for k in ('previous','final','mapped_final')]
        assert v['parent_peak_rss_bytes']<6*1024**3 and v['minimum_candidate']>=0 and v['accepted_material_step'] is False
        blocks=[read(folder/'map0001'/f'block{i:02d}.json') for i in range(76)]
        ownership=np.zeros(9632,int);peaks=[]
        for i,b in enumerate(blocks):
            assert b['block_index']==i and b['input_state_sha256']==v['candidate']['sha256']
            assert 0<=b['core_group_start']<b['core_group_stop']<=9632
            ownership[b['core_group_start']:b['core_group_stop']]+=1
            assert all(np.isfinite(x) for x in b.values() if isinstance(x,(float,int)))
            assert b['minimum_input_intensity']>=0 and b['minimum_mapped_intensity']>=0
            p=list((folder/'map0001').glob(f'block{i:02d}.process-*.json'));assert len(p)==1
            q=read(p[0]);assert q['returncode']==0 and q['memory_guard_passed'] and q['native_observed_peak_kib']<6*1024**2
            peaks.append(q['native_observed_peak_kib']);total_receipts+=1
        assert np.all(ownership==1)
        scale=max(b['maximum_radiation_scale'] for b in blocks)
        # 独立按原最大范数和边界积分定义聚合；不调用运行驱动的判门函数。
        aggregate={'residual':max(b['maximum_absolute_radiation_change'] for b in blocks)/scale,
                   'boundary_l1':sum(b['boundary_spectrum_l1_numerator'] for b in blocks)/max(sum(b['current_boundary_absolute_scale'] for b in blocks),sum(b['mapped_boundary_absolute_scale'] for b in blocks)),
                   'boundary_bolometric':abs(sum(b['mapped_boundary_bolometric'] for b in blocks)-sum(b['current_boundary_bolometric'] for b in blocks))/max(abs(sum(b['mapped_boundary_bolometric'] for b in blocks)),abs(sum(b['current_boundary_bolometric'] for b in blocks))),
                   'maximum_worker_rss_mib':max(b['peak_process_rss_mib'] for b in blocks)}
        for k,value in aggregate.items():assert_close(value,v['actual_map'][k])
        f=v['field_comparison'];slabs=f['slabs']
        assert [(q['start'],q['stop']) for q in slabs]==[(i,min(i+16,9632)) for i in range(0,9632,16)]
        for q in slabs:
            assert all(np.isfinite(x) and x>=0 for x in q.values())
            assert_close(q['error_relative_to_local_field'],guarded_ratio(q['error_max'],q['field_scale']))
        e=max(q['error_max'] for q in slabs);z=max(q['field_scale'] for q in slabs);delta=max(q['actual_change_max'] for q in slabs)
        assert_close(e/z,f['max_error_over_field']);assert_close(e/delta,f['max_error_over_actual_change'])
        assert_close(f['actual_global_residual'],aggregate['residual']);assert f['full_intensity_prediction_error_evaluated']
        prior_res=plan['basis'][case]['latest_actual_residual']
        checks={'actual_maximum_norm_improves':aggregate['residual']/prior_res<.99,
                'actual_boundary_spectrum_pass':aggregate['boundary_l1']<1e-3,
                'actual_boundary_bolometric_pass':aggregate['boundary_bolometric']<1e-3,
                'worker_memory_pass':aggregate['maximum_worker_rss_mib']<6144,
                'strict_inner_pass':0<=aggregate['residual']<1e-4,
                'full_field_prediction_error_small':0<=e/z<1e-7,
                'prediction_error_below_tenth_actual_change':0<=e/delta<.1}
        assert checks==v['checks'] and v['validated']==all(checks.values())
        worst=max(blocks,key=lambda b:b['block_relative_radiation_change'])
        worst_slab=max(slabs,key=lambda q:q['error_relative_to_local_field'])
        rows[case]={'actual_residual':aggregate['residual'],'actual_over_prior':aggregate['residual']/prior_res,
                    'boundary_l1':aggregate['boundary_l1'],'boundary_bolometric':aggregate['boundary_bolometric'],
                    'prediction_error_over_field':e/z,'prediction_error_over_actual_change':e/delta,
                    'worst_slab_prediction_relative':max(q['error_relative_to_local_field'] for q in slabs),
                    'worst_slab':worst_slab,'maximum_field_scale':z,
                    'worst_slab_scale_subnormal':bool(0<worst_slab['field_scale']<np.finfo(float).tiny),
                    'worst_block_index':worst['block_index'],'worst_block_relative':worst['block_relative_radiation_change'],
                    'map_wall_s':v['actual_map']['wall_s'],'max_proc_kib':max(peaks),'checks':checks}
    result={'archive':claim,'verified_files':len(manifest['files']),'verified_code_claims':len(plan['code']),
            'map_process_receipts':total_receipts,'cases':rows,'accepted_outer_steps':20,'new_material_steps':0,
            'feedback_reviewed':False,'raw_large_states_recomputed_on_mac':False,
            'field_extrema_reaggregated_from_602_slabs_per_case':True,
            'full_field_l2_recomputed_on_mac':False}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    axes[0].bar(list(rows),[r['actual_over_prior'] for r in rows.values()]);axes[0].set(title='Measured map improvement',ylabel='Actual residual / prior residual')
    axes[1].bar(list(rows),[r['prediction_error_over_actual_change'] for r in rows.values()]);axes[1].axhline(.1,color='r',linestyle='--',label='Continuation gate')
    axes[1].set(yscale='log',title='Full-field prediction discrepancy',ylabel='Max error / max actual change');axes[1].legend()
    axes[2].bar(list(rows),[r['worst_slab_prediction_relative'] for r in rows.values()]);axes[2].set(title='Weakest-tail discrepancy retained',ylabel='Worst slab error / its field scale')
    fig.tight_layout();fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','prior','scan','output'):p.add_argument('--'+k,type=Path,required=True)
    print(json.dumps(review(**vars(p.parse_args())),indent=2))
