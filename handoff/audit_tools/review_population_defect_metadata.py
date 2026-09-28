"""Verify current two-block pilot and saved actual local fields, without re-solving."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,verified_inventory,read,digest
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close


def main():
    root=Path('outputs/review-20260925');archive=root/'complete-1790603129264916005.tar.gz';receipt=root/'complete-1790603129264916005-receipt.json'
    out=root/'population-defect-79747-received';manifest=receive(archive,receipt,out)
    prior=root/'late-population-global-79631-received';source_archive=read(Path('handoff/evidence/20260928-late-population-global-review.json'))['archive']
    original=root/Path(source_archive['path']).name
    assert digest(original)==source_archive['sha256'] and original.stat().st_size==source_archive['size_bytes']
    with tarfile.open(original) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(prior/'ARCHIVE_MANIFEST.json')
    verified_inventory(prior)
    terminal=read(Path('handoff/evidence/20260928-population-defect-79747-terminal.json'));assert terminal['job_id']==79747 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    d=read(out/'declaration.json');s=read(out/'summary.json');status=read(out/'status.json')
    assert status['status']=='complete_requires_review' and d['blocks']==[23,30] and d['workers']==2
    assert d['core_intervals']==[[2560,3456],[3456,4352]] and d['per_worker_limit_mib']==32768
    assert (d['gmres_restart'],d['gmres_cycles'],d['gmres_tolerance'],d['maximum_source_maps_per_case'])==(8,2,1e-5,4)
    assert d['maximum_global_maps']==d['maximum_feedback_pairs']==0 and not d['global_candidate_authorized'] and not d['automatic_promotion']
    assert all(s[k]==0 for k in ('new_material_steps','new_full_maps','new_feedback_pairs')) and s['accepted_outer_steps']==20
    assert not s['global_candidate_written'] and not s['full_frequency_run_authorized'] and s['source_bytes_unchanged']
    state=read(prior/'population/state.json');val=read(prior/'population/validation.json');case=d['cases']['population']
    assert case['input']==val['candidate']
    assert case['output']==dict(path=state['history'][0]['output_path'],sha256=state['history'][0]['output_sha256'],size_bytes=10099884032)
    assert state['history']==[val['actual_map']] and state['current_sha256']==case['output']['sha256']
    assert state['slots'][state['current_slot']]==case['output']['path']
    assert case['input']['sha256']==state['history'][-1]['input_sha256'] and case['output']['sha256']==state['history'][-1]['output_sha256']
    for k in ('config','trial','state'):
        p=prior/'population'/dict(config='config.json',trial='trial_material.npz',state='state.json')[k]
        assert digest(p)==case[k]['sha256'] and p.stat().st_size==case[k]['size_bytes']
    for c in d['code']:
        p=Path(c['path']);assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    assert d['source_job_id']==79631 and d['refreshed_halo'] and d['source_run']=='outputs/hpc/step21-late-population-global-20260928'
    assert d['frozen_material_case']=='population' and d['material_relaxation']==1/256
    assert d['original_r20_unchanged'] and d['physical_dt_unchanged']
    assert d['source_pair']==[case['input'],case['output']]
    assert set(d['cases'])=={'population'} and d['worker_timeout_s']==3600
    assert d['source_rejected'] and d['source_full_map_is_not_accepted'] and d['eventual_global_validation_requires_both_source_and_original_reference']
    assert d['original_pre_correction_pair']==read(prior/'declaration.json')['source_pair']
    failed={'full_l2_benefit','full_boundary_bolometric','half_boundary_bolometric'}
    assert not val['validated'] and set(d['source_failed_gate_names'])==failed
    assert d['source_gate_checks']==val['checks'] and {k for k,v in val['checks'].items() if not v}==failed
    assert read(prior/'summary.json')['status']=='stopped_at_full_half_validation'
    slabs=val['field_comparison']['slabs']
    assert [r['first_group'] for r in slabs]==list(range(0,9632,32))
    # 独立从完整实际映射统计归约平方缺陷，不复用运行时选区函数。
    scores={i:math.fsum(r['squared_l2'][1] for r in slabs if r['block']==i) for i in range(76)}
    options=[(math.fsum(scores[j] for j in list(range(a-3,a+4))+list(range(b-3,b+4))),-a,-b)
             for a in range(3,72) for b in range(a+7,72)]
    best=max(options);assert (-best[1],-best[2])==(23,30)
    coverage=best[0]/math.fsum(scores.values())
    assert coverage==d['selected_squared_defect_fraction'] and coverage>=.36
    assert state['active_map'] is None and [r['iteration'] for r in state['history']]==[1]
    rows=[]
    for i in (23,30):
        r=read(out/f'population-block{i:02d}.json');proc=read(out/f'population-block{i:02d}.process.json')
        assert r==s['rows'][(i==30)] and r['block_index']==i and r['label']=='population'
        assert r['replay']==dict(field_relative_error=0.,defect_relative_error=0.,array_equal=True)
        assert proc['returncode']==0 and proc['memory_guard_passed'] and proc['native_observed_peak_kib']<32*1024**2
        warning=(out/f'population-block{i:02d}.err').read_text()
        assert not warning, 'unexpected worker stderr needs explicit review'
        assert all(np.isfinite(x) for x in r.values() if isinstance(x,(int,float)))
        assert 0<r['exact_nonnegative_step']<=1

        claim=r['local_arrays'];assert claim['size_bytes']==1879048728
        # Metadata review only: raw arrays remain on school; independent scan follows.
        l2=r['fresh_defect_l2'];maximum=r['fresh_defect_linf']
        assert r['minimum_candidate']>=0 and r['minimum_mapped']>=0
        assert proc['wall_s']<3600 and d['worker_timeout_s']==3600
        old=[read(prior/f'population/map0001/block{j:02d}.json') for j in range(i-3,i+4)]
        assert_close(r['raw_defect_linf'],max(x['maximum_absolute_radiation_change'] for x in old))
        assert read(out/f'population-block{i:02d}-replay.json')['replay']==r['replay']
        l2ratio=l2/r['raw_defect_l2'];maxratio=maximum/r['raw_defect_linf']
        assert_close(l2ratio,r['fixed_scale_l2_ratio']);assert_close(maxratio,r['fixed_scale_linf_ratio'])
        checks=dict(l2_halved=l2ratio<=.5,linf_halved=maxratio<=.5,
            useful_step=r['exact_nonnegative_step']>0 and r['line_fraction']>0,affine_prediction=r['prediction_error_over_raw_l2']<=1e-6,
            boundary_not_worse=r['fresh_boundary_absolute']<=r['raw_boundary_absolute'],finite_budget=r['gmres_iterations']<=16,
            memory_below_32gib=r['peak_rss_mib']<32768,time_below_24_maps=r['wall_s']<=24*r['raw_map_s'],independent_half_affinity=r['half_affinity_over_raw_l2']<=1e-6)
        assert checks==r['checks'] and r['eligible_for_further_block_review']==all(checks.values())
        assert r['core_groups']==[(i-3)*128,(i+4)*128] and not r['global_candidate_written'] and not r['formal_acceptance_changed']
        rows.append(dict(warning=warning,block=i,local_arrays=claim,l2_ratio=l2ratio,linf_ratio=maxratio,checks=checks,
            local_candidate_min=r['minimum_candidate'],local_mapped_min=r['minimum_mapped'],raw_map_s=r['raw_map_s'],wall_s=r['wall_s'],half_affinity_over_raw_l2=r['half_affinity_over_raw_l2'],
            observed_peak_kib=proc['native_observed_peak_kib'],gmres_info=r['gmres_info'],gmres_iterations=r['gmres_iterations'],
            linear_audit_passed=r['linear_audit_passed'],full_step=r['exact_nonnegative_step']==r['line_fraction']==1.,
            zero_prediction_error_is_not_independent_half_probe=r['line_fraction']==1.))
    assert s['all_local_cases_passed']==all(all(r['checks'].values()) for r in rows)
    result=dict(archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),rows=rows,
        source_job_id=79631,job_id=79747,frozen_material_case="population",refreshed_halo=True,source_pair=[case['input'],case['output']],
        all_local_cases_passed=s['all_local_cases_passed'],selected_squared_defect_fraction=coverage,source_rejected=True,accepted_outer_steps=20,new_material_steps=0,
        raw_input_output_blocks_present_on_mac=False,raw_l2_independently_recomputed=False,
        fresh_l2_and_linf_independently_recomputed=False,local_boundary_flux_independently_recomputed=False,
        operator_recomputed_on_mac=False,half_operator_recomputed_on_mac=False,global_validation_required=True)
    target=Path('handoff/evidence/20260928-population-defect-metadata-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained');x=np.arange(2)
    ax.bar(x-.17,[r['l2_ratio'] for r in rows],.34,label='L2');ax.bar(x+.17,[r['linf_ratio'] for r in rows],.34,label='Maximum')
    ax.axhline(.5,ls='--',color='black');ax.set(xticks=x,xticklabels=['Blocks 20–26','Blocks 27–33'],ylabel='Actual local defect / original defect',title='Metadata checked; raw-array scan pending');ax.legend()
    fig.savefig(target.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':main()
