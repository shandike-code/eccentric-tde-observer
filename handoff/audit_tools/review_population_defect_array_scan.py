"""Mac reduction of the school raw-array scan, not a Mac transfer-operator replay."""
import json,math
from pathlib import Path
from handoff.audit_tools.review_step21_control_windows import read,digest
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close
ROOT=Path('outputs/review-20260925')

def main():
    out=ROOT/'population-defect-array-79850-received';claims=read(out/'download-receipt.json')
    for c in claims:
        p=out/c['name'];assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    d=read(out/'declaration.json');s=read(out/'summary.json');terminal=read(out/'scheduler-terminal.json')
    assert d['source_job_id']==79747 and d['frozen_material_case']=='population'
    assert d['maximum_frequency_rows']==1792 and d['source_data_passes']==1 and d['maximum_wall_s']==1800
    assert d['job_id']=='79850' and terminal['job_id']==79850 and 'JobState=COMPLETED' in terminal['scontrol'] and 'ExitCode=0:0' in terminal['scontrol']
    assert s['status']=='complete_requires_mac_reduction' and s['source_unchanged'] and not s['operator_recomputed']
    assert s['peak_rss_bytes']<8*1024**3 and s['wall_s']<1800
    assert s['new_maps']==s['new_feedback']==s['new_material_steps']==0
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    prior=ROOT/'population-defect-79747-received';p=read(prior/'declaration.json');summary=read(prior/'summary.json')
    assert p['source_job_id']==79631 and p['refreshed_halo'] and p['blocks']==[23,30] and p['frozen_material_case']=='population'
    expected=p['cases']['population'];lookup={c['path']:c for c in d['claims']}
    for c in expected.values():assert lookup[c['path']]==c
    for name in ('declaration.json','summary.json'):
        key='outputs/hpc/step21-population-defect-pilot-20260928/'+name;c=lookup[key]
        assert digest(prior/name)==c['sha256'] and (prior/name).stat().st_size==c['size_bytes']
    results=[]
    for r in summary['rows']:
        i=r['block_index'];z=read(out/f'block{i}.json');lo,hi=r['core_groups'];rows=z['rows']
        assert z['block']==i and z['core']==[lo,hi] and [x['group'] for x in rows]==list(range(lo,hi)) and hi-lo==896
        assert z['local_arrays']==r['local_arrays']==lookup[r['local_arrays']['path']]
        norms={}
        for k in ('raw','fresh'):
            assert all(all(math.isfinite(v) and v>=0 for v in a[k].values()) for a in rows)
            norms[k]=dict(l2=math.sqrt(math.fsum(a[k]['square'] for a in rows)),linf=max(a[k]['maximum'] for a in rows))
            for n,v in norms[k].items():
                # Same small statistics: strict original tolerance; old whole-array norm uses
                # a different reduction. Keep the scan's predeclared 2e-11 for that comparison.
                assert_close(v,z['norms'][k][n])
                if n=='linf':assert v==r[k+'_defect_'+n]
                else:assert math.isclose(v,r[k+'_defect_'+n],rel_tol=2e-11,abs_tol=0.)
        for block in range(i-3,i+4):
            raw=read(ROOT/f'late-population-global-79631-received/population/map0001/block{block:02d}.json')
            assert_close(max(x['raw']['maximum'] for x in rows if x['group']//128==block),raw['maximum_absolute_radiation_change'])
        assert_close(min(a['fresh']['minimum_input'] for a in rows),r['minimum_candidate'])
        assert_close(min(a['fresh']['minimum_output'] for a in rows),r['minimum_mapped'])
        results.append(dict(block=i,legacy_l2_relative_differences={k:abs(norms[k]['l2']/r[k+'_defect_l2']-1) for k in ('raw','fresh')},norms=norms,l2_ratio=norms['fresh']['l2']/norms['raw']['l2'],linf_ratio=norms['fresh']['linf']/norms['raw']['linf']))
    result=dict(job_id=79850,source_job_id=79747,frozen_material_case='population',download_receipt=claims,claims=d['claims'],code=d['code'],rows=results,verified_frequency_rows=1792,peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],school_raw_arrays_scanned=True,mac_full_arrays_read=False,mac_independent_fsum=True,legacy_l2_rtol=2e-11,mac_to_scan_rtol=2e-13,linf_exact=True,operator_recomputed=False,global_validation_required=True,new_material_steps=0)
    Path('handoff/evidence/20260928-population-defect-array-independent-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':main()
