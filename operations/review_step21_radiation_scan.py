"""Independently audit the small scan archive; never claim a new map was measured."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(archive, receipt, prior, output):
    claim=json.loads(receipt.read_text())
    assert archive.stat().st_size==claim['size_bytes'] and digest(archive)==claim['sha256']
    with tarfile.open(archive) as t:
        members=t.getmembers()
        assert all(m.isfile() and '/' not in m.name for m in members)
        contents={m.name:t.extractfile(m).read() for m in members}
    manifest=json.loads(contents['ARCHIVE_MANIFEST.json'])
    assert set(contents)=={'ARCHIVE_MANIFEST.json',*[c['path'] for c in manifest['files']]}
    for c in manifest['files']:
        assert len(contents[c['path']])==c['size_bytes'] and hashlib.sha256(contents[c['path']]).hexdigest()==c['sha256']
    d=json.loads(contents['declaration.json']);p=json.loads(contents['prediction.json']);status=json.loads(contents['status.json'])
    assert status['status']=='complete_requires_review' and status['accepted_outer_steps']==20
    assert status['new_maps']==status['new_material_steps']==0 and status['candidate_written'] is False
    for c in d['code']:
        q=Path(c['path']);assert q.stat().st_size==c['size_bytes'] and digest(q)==c['sha256']
    prefix='outputs/hpc/common-step21-direction-precision-20260925/'
    source_claims={c['path']:c for c in d['claims']}
    rows={}
    for case,h in p['histories'].items():
        for suffix in ('state.json','config.json','trial_material.npz','endpoints-map08/manifest.json'):
            c=source_claims[prefix+case+'/'+suffix];q=prior/case/suffix
            assert q.stat().st_size==c['size_bytes'] and digest(q)==c['sha256']
        s=json.loads((prior/case/'state.json').read_text());retained=json.loads((prior/case/'endpoints-map08/manifest.json').read_text())
        assert s['active_map'] is None and len(s['history'])==8 and retained['history_rows']==s['history'][-2:]
        basis=d['cases'][case]['basis']
        assert basis==[retained['endpoints'][k] for k in ('previous','final','mapped_final')]
        assert [c['sha256'] for c in basis]==[s['history'][-2]['input_sha256'],s['history'][-1]['input_sha256'],s['history'][-1]['output_sha256']]
        assert h['latest_actual_residual']==s['history'][-1]['residual']
        g=np.asarray(h['direction']['gram']);v=h['direction'];m=h['metrics']
        assert np.isfinite(g).all() and np.array_equal(g,g.T) and np.linalg.eigvalsh(g).min()>0
        np.testing.assert_allclose(v['difference_squared'],g[0,0]+g[1,1]-2*g[0,1],rtol=1e-10,atol=0)
        np.testing.assert_allclose(v['selected_forward_fraction'],(g[0,0]-g[0,1])/v['difference_squared'],rtol=1e-13,atol=0)
        assert 1<v['selected_forward_fraction']<min(96,v['exact_positive_upper'])
        assert h['algebraic_feasibility'] and all(h['algebraic_gates'].values())
        assert h['actual_candidate_residual'] is None and h['actual_map_performed'] is False
        assert h['peak_rss_bytes']<6*1024**3 and m['candidate_negative_count']==m['predicted_map_negative_count']==0
        blocks=m['reports'];assert len(blocks)==76
        assert [(r['core_group_start'],r['core_group_stop']) for r in blocks]==[(i,min(i+128,9632)) for i in range(0,9632,128)]
        rows[case]={'fraction':v['selected_forward_fraction'],'old_residual':h['latest_actual_residual'],
                    'predicted_residual':m['predicted_global_original_operator_residual'],
                    'predicted_ratio':m['predicted_global_original_operator_residual']/h['latest_actual_residual'],
                    'boundary_l1':m['predicted_boundary_spectrum_l1'],
                    'worst_block_relative':max(r['block_relative_predicted_residual'] for r in blocks),
                    'peak_rss_bytes':h['peak_rss_bytes']}
    result={'archive':claim,'files_verified':len(manifest['files']),'code_claims_verified':len(d['code']),
            'cases':rows,'accepted_outer_steps':20,'new_material_steps':0,'new_maps':0,
            'full_large_arrays_recomputed_on_mac':False,'fresh_map_required':True,
            'source_metadata_matches_independently_audited_76931':True}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for name,h in p['histories'].items():
        axes[0].plot([r['block_index'] for r in h['metrics']['reports']],[r['block_relative_predicted_residual'] for r in h['metrics']['reports']],label=name)
    axes[0].set(yscale='log',xlabel='Frequency block',ylabel='Predicted block-relative residual',title='Weak-tail errors retained');axes[0].legend()
    axes[1].bar(list(rows),[r['predicted_ratio'] for r in rows.values()]);axes[1].set(ylabel='Predicted / latest global residual',title='Algebraic prediction only')
    fig.tight_layout();fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--prior',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(review(**vars(p.parse_args())),indent=2))
