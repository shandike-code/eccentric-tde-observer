"""Verify current two-block pilot and saved actual local fields, without re-solving."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,verified_inventory,read,digest
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close


def main():
    root=Path('outputs/review-20260925');archive=root/'complete-1790461087073776500.tar.gz';receipt=root/'complete-1790461087073776500-receipt.json'
    out=root/'five-blocks-78037-received';manifest=receive(archive,receipt,out)
    prior=root/'heating-validation-77577-complete-received';c=read(Path('handoff/evidence/20260926-heating-validation-complete-review.json'))['archive']
    original=root/Path(c['path']).name;assert digest(original)==c['sha256']
    with tarfile.open(original) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(prior/'ARCHIVE_MANIFEST.json')
    verified_inventory(prior)
    terminal=read(Path('handoff/evidence/20260927-five-block-78037-terminal.json'));assert terminal['job_id']==78037 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    d=read(out/'declaration.json');s=read(out/'summary.json');status=read(out/'status.json')
    assert status['status']=='complete_requires_review' and d['blocks']==[24,48] and d['workers']==2
    assert d['core_intervals']==[[2816,3456],[5888,6528]] and d['per_worker_limit_mib']==24576
    assert (d['gmres_restart'],d['gmres_cycles'],d['gmres_tolerance'],d['maximum_source_maps_per_case'])==(8,2,1e-5,4)
    assert d['maximum_global_maps']==d['maximum_feedback_pairs']==0 and not d['global_candidate_authorized'] and not d['automatic_promotion']
    assert all(s[k]==0 for k in ('new_material_steps','new_full_maps','new_feedback_pairs')) and s['accepted_outer_steps']==20
    assert not s['global_candidate_written'] and not s['full_frequency_run_authorized'] and s['source_bytes_unchanged']
    state=read(prior/'control/state.json');ret=read(prior/'control/endpoints-map10/manifest.json');case=d['cases']['control']
    assert case['input']==ret['endpoints']['final'] and case['output']==ret['endpoints']['mapped_final']
    assert case['input']['sha256']==state['history'][-1]['input_sha256'] and case['output']['sha256']==state['history'][-1]['output_sha256']
    for k in ('config','trial','state'):
        p=prior/'control'/dict(config='config.json',trial='trial_material.npz',state='state.json')[k]
        assert digest(p)==case[k]['sha256'] and p.stat().st_size==case[k]['size_bytes']
    for c in d['code']:
        p=Path(c['path']);assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    rows=[]
    for i in (24,48):
        r=read(out/f'control-block{i:02d}.json');proc=read(out/f'control-block{i:02d}.process.json')
        assert r==s['rows'][(i==48)] and r['block_index']==i and r['label']=='control'
        assert r['replay']==dict(field_relative_error=0.,defect_relative_error=0.,array_equal=True)
        assert proc['returncode']==0 and proc['memory_guard_passed'] and proc['native_observed_peak_kib']<24*1024**2
        assert not (out/f'control-block{i:02d}.err').read_text()
        claim=r['local_arrays']
        # Metadata review only: raw arrays remain on school; independent scan follows.
        l2=r['fresh_defect_l2'];maximum=r['fresh_defect_linf']
        assert r['minimum_candidate']>=0 and r['minimum_mapped']>=0
        assert proc['wall_s']<3600 and d['worker_timeout_s']==3600
        old=[read(prior/f'control/map0010/block{j:02d}.json') for j in range(i-2,i+3)]
        assert_close(r['raw_defect_linf'],max(x['maximum_absolute_radiation_change'] for x in old))
        assert read(out/f'control-block{i:02d}-replay.json')['replay']==r['replay']
        l2ratio=l2/r['raw_defect_l2'];maxratio=maximum/r['raw_defect_linf']
        assert_close(l2ratio,r['fixed_scale_l2_ratio']);assert_close(maxratio,r['fixed_scale_linf_ratio'])
        checks=dict(l2_halved=l2ratio<=.5,linf_halved=maxratio<=.5,
            useful_step=r['exact_nonnegative_step']>0 and r['line_fraction']>0,affine_prediction=r['prediction_error_over_raw_l2']<=1e-6,
            boundary_not_worse=r['fresh_boundary_absolute']<=r['raw_boundary_absolute'],finite_budget=r['gmres_iterations']<=16,
            memory_below_24gib=r['peak_rss_mib']<24576,time_below_24_maps=r['wall_s']<=24*r['raw_map_s'],independent_half_affinity=r['half_affinity_over_raw_l2']<=1e-6)
        assert checks==r['checks'] and r['eligible_for_further_block_review']==all(checks.values())
        assert r['core_groups']==[(i-2)*128,(i+3)*128] and not r['global_candidate_written'] and not r['formal_acceptance_changed']
        rows.append(dict(block=i,local_arrays=claim,l2_ratio=l2ratio,linf_ratio=maxratio,checks=checks,
            local_candidate_min=r['minimum_candidate'],local_mapped_min=r['minimum_mapped'],raw_map_s=r['raw_map_s'],wall_s=r['wall_s'],half_affinity_over_raw_l2=r['half_affinity_over_raw_l2'],
            observed_peak_kib=proc['native_observed_peak_kib'],gmres_info=r['gmres_info'],gmres_iterations=r['gmres_iterations'],
            linear_audit_passed=r['linear_audit_passed'],full_step=r['exact_nonnegative_step']==r['line_fraction']==1.,
            zero_prediction_error_is_not_independent_half_probe=r['line_fraction']==1.))
    assert s['all_local_cases_passed']==all(all(r['checks'].values()) for r in rows)
    result=dict(archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),rows=rows,
        all_local_cases_passed=s['all_local_cases_passed'],accepted_outer_steps=20,new_material_steps=0,
        raw_input_output_blocks_present_on_mac=False,raw_l2_independently_recomputed=False,
        fresh_l2_and_linf_independently_recomputed=False,local_boundary_flux_independently_recomputed=False,
        operator_recomputed_on_mac=False,half_operator_recomputed_on_mac=False,global_validation_required=True)
    target=Path('handoff/evidence/20260927-five-block-pilot-metadata-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained');x=np.arange(2)
    ax.bar(x-.17,[r['l2_ratio'] for r in rows],.34,label='L2');ax.bar(x+.17,[r['linf_ratio'] for r in rows],.34,label='Maximum')
    ax.axhline(.5,ls='--',color='black');ax.set(xticks=x,xticklabels=['Blocks 22–26','Blocks 46–50'],ylabel='Actual local defect / original defect',title='Metadata checked; raw-array scan pending');ax.legend()
    fig.savefig(target.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
