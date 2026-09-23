"""Read-only replay of formal-state gates from archived feedback partials.

No material response is solved. A failed state cannot be promoted to acceptance.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from operations.review_outer_step_snapshot import read, digest, arrays


def source_metrics(rate, other, width):
    absolute = max(float(np.sum(width*np.abs(rate))), float(np.sum(width*np.abs(other))))
    r, o = float(np.sum(width*rate)), float(np.sum(width*other))
    net = max(abs(r), abs(o))
    if absolute <= 0 or net <= 0:
        raise ValueError('zero denominator requires separate review')
    return {'volume_l1': float(np.sum(width*np.abs(rate-other)))/absolute,
            'global_fraction': abs(r-o)/net, 'integrated_rate': r,
            'integrated_other': o, 'absolute_integral_difference': abs(r-o),
            'absolute_scale': absolute, 'net_scale': net,
            'absolute_over_net_scale': absolute/net}


def review(root, source):
    inventory=read(root/'ARCHIVE_MANIFEST.json')
    for row in inventory['files']:
        p=root/row['path']
        assert p.stat().st_size==row['size_bytes'] and digest(p)==row['sha256']
    def local(path):
        rel=Path(path)
        return root/rel.relative_to(source) if rel.is_relative_to(source) else root/'inputs'/rel
    def claim(c):
        p=local(c['path']);assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes'];return p
    declaration=read(root/'declaration.json');b=declaration['outer_baseline']
    base=arrays(claim(b['material']));direction=np.load(claim(b['residual']),allow_pickle=False)
    t=arrays(root/'full/trial_material.npz')
    assert float(t['relaxation'])==1/32
    assert np.array_equal(t['base_encoded_state'],base['encoded_state'])
    assert np.array_equal(t['base_residual'],direction) and np.array_equal(t['finite_direction'],direction)
    assert np.array_equal(t['encoded_state'],base['encoded_state']+direction/32)
    for k in ('density_g_cm3','phase_index','step_duration_s'):assert np.array_equal(t[k],base[k])
    for name in ('control','full'):
        identity=read(root/name/'initialized_identity.json');assert identity['passed']
        assert identity['native']['native_mirrored_material_exact'] and identity['native']['physical_phase_and_dt_exact']
    state=read(root/'full/state.json');result={'verified_files':len(inventory['files']),'actual_alpha':1/32,'native_identity':True,'rounds':{}}
    for ri in (1,2):
        rd=root/'full'/f'feedback-round{ri}';proto=read(rd/'feedback_protocol.json');ph=digest(rd/'feedback_protocol.json')
        assert proto['sources']['base_residual']==b['residual'] and proto['sources']['outer_base_material']==b['material']
        assert proto['sources']['physical_old_time_level']==b['physical_old_time_level']
        for c in proto['sources'].values():
            if not c['path'].endswith('.dat'):claim(c)
        assert proto['sources']['trial_material']['sha256']==digest(root/'full/trial_material.npz')
        gates=proto['formal_state_gates'];result['rounds'][str(ri)]={}
        for e in ('previous','final'):
            m=read(rd/'feedback'/f'{e}_manifest.json');c=proto['sources'][e+'_radiation']
            assert m['protocol_sha256']==ph and m['state_path']==c['path'] and m['state_sha256']==c['sha256']
            rows=[x for x in state['history'] if x['input_path']==c['path'] and x['input_sha256']==c['sha256']]
            assert len(rows)==1 and rows[0]['iteration']==4*ri-(1 if e=='previous' else 0)
            records=m['completed_blocks'];assert [r['block_index'] for r in records]==list(range(76))
            combined={};ownership=np.zeros(9632,dtype=int)
            for r in records:
                p=local(r['partial_path']);assert digest(p)==r['partial_sha256']
                partial=arrays(p)
                if not combined:combined={k:np.zeros_like(v) for k,v in partial.items()}
                assert set(partial)==set(combined)
                for k,v in partial.items():combined[k]+=v
                ownership[r['core_group_start']:r['core_group_stop']]+=1
            f=local(m['feedback_artifact_path']);assert digest(f)==m['feedback_artifact_sha256'];fb=arrays(f)
            mirrors=[]
            for k,v in combined.items():
                assert np.array_equal(v,fb[k]);parent=v.reshape(256,16,*v.shape[1:]).mean(axis=1)
                assert np.array_equal(parent,fb['parent_'+k]) and np.array_equal(parent[:128],fb['half_'+k])
                scale=float(np.max(np.abs(parent)));err=float(np.max(np.abs(parent[:128]-parent[128:][::-1])))
                mirrors.append(err/scale if scale>0 else err)
            w=fb['subcell_width_cm'];assert w.shape==(4096,) and np.all(np.isfinite(w)) and np.all(w>0)
            rate=fb['atomic_rate_heating_erg_s_cm3'];direct=source_metrics(rate,fb['source_direct_heating_erg_s_cm3'],w);formal=source_metrics(rate,fb['source_formal_heating_erg_s_cm3'],w)
            for key,value in [('rate_direct_volume_l1',direct['volume_l1']),('rate_formal_volume_l1',formal['volume_l1']),('rate_formal_global_fraction',formal['global_fraction']),('integrated_atomic_rate_heating_erg_s_cm2',formal['integrated_rate']),('integrated_formal_heating_erg_s_cm2',formal['integrated_other'])]:assert np.isclose(value,m[key],rtol=1e-12,atol=0)
            checks={
                'block_count':len(records)==gates['block_count_exactly'],
                'frequency_ownership':int(ownership.sum())==gates['owned_frequency_group_count_exactly'] and bool(np.all(ownership==1)),
                'positive_intensity':min(r['minimum_owned_comoving_mean_intensity'] for r in records)>=gates['minimum_comoving_mean_intensity_at_least'],
                'finite_arrays':all(np.all(np.isfinite(v)) for v in combined.values()),
                'nonnegative_atomic_rates':all(np.all(combined[k]>=0) for k in ('photoionization_s1','spontaneous_recombination_cm3_s','stimulated_recombination_cm3_s','total_recombination_cm3_s')),
                'direct_volume':direct['volume_l1']<gates['atomic_rate_vs_direct_comoving_heating_volume_l1_below'],
                'formal_volume':formal['volume_l1']<gates['atomic_rate_vs_inverse_four_force_volume_l1_below'],
                'formal_global':formal['global_fraction']<gates['atomic_rate_vs_inverse_four_force_global_fraction_below'],
                'mirror':max(mirrors)<gates['maximum_parent_mirror_residual_below'],
                'memory':max(r['peak_process_rss_mib'] for r in records)<gates['each_process_peak_rss_strictly_below_mib'],
                'wall':m['accumulated_wall_runtime_s']<gates['each_state_wall_time_strictly_below_s']}
            checks={k:bool(v) for k,v in checks.items()};assert all(checks.values())==m['state_gate_passed']
            assert m['status']==('complete' if all(checks.values()) else 'gate_failed')
            result['rounds'][str(ri)][e]={'checks':checks,'failed_checks':[k for k,v in checks.items() if not v], 'formal':formal,'direct':direct,'manifest_status':m['status'],'all_76_partials_and_assembled_bytes_verified':True}
    assert not (root/'full/feedback-round2/feedback_summary.json').exists()
    result.update(round2_material_response_evaluated=False,coupled_column_accepted=False)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--received',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=review(a.received,Path('outputs/hpc/step16-amplitude-20260923'))
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':main()
