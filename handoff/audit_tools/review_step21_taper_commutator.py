"""Independent reduction of one-pass defect decomposition; no global arrays on Mac."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,read,digest,verified_inventory


def main():
    root=Path('outputs/review-20260925');out=root/'taper-commutator-77954-received'
    receipt=root/'complete-1790438922135455540-receipt.json'
    manifest=receive(root/'complete-1790438922135455540.tar.gz',receipt,out)
    d=read(out/'declaration.json');p=read(out/'decomposition.json');s=read(out/'status.json')
    terminal=read(Path('handoff/evidence/20260927-taper-commutator-77954-terminal.json'))
    assert terminal['job_id']==77954 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert s['status']=='complete_requires_review' and s['accepted_outer_steps']==d['accepted_outer_steps']==20 and s['new_material_steps']==0
    assert d['maximum_maps']==d['maximum_feedback_pairs']==d['maximum_candidate_writes']==0 and d['maximum_passes']==p['passes']==1
    assert p['actual_map_performed']==p['candidate_written']==p['accepted_material_step']==False
    assert p['columns']==['original','uniform','actual_tapered','weighted_defect','commutator']
    assert d['taper']=={'kind':'sin_squared_midpoint','groups_per_core':384,'formula':'sin(pi*(j+0.5)/384)^2','free_parameters':0}
    for c in d['code']:
        f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    evidence=[];vals=[]
    for folder,ev in [('joint-block-global-77843-received','20260926-joint-global-review'),('tapered-joint-77927-received','20260926-tapered-joint-review')]:
        old=root/folder;a=read(Path('handoff/evidence')/(ev+'.json'));claim=a['archive'];archive=root/Path(claim['path']).name
        assert digest(archive)==claim['sha256']
        with tarfile.open(archive) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(old/'ARCHIVE_MANIFEST.json')
        verified_inventory(old);evidence.append(a);vals.append(read(old/'control/validation.json'))
    assert vals[0]['source_pair']==vals[1]['source_pair']
    expected=list(vals[0]['source_pair'])
    for val in vals:
        r=val['actual_map'];expected += [val['candidate'],dict(path=r['output_path'],sha256=r['output_sha256'],size_bytes=10099884032)]
    assert d['paths']==expected
    rows=p['slabs'];assert len(rows)==301 and [r['first_group'] for r in rows]==list(range(0,9632,32))
    for r in rows:
        assert r['group_count']==32 and r['selected']==(r['first_group']//128 in (23,24,25,47,48,49))
        assert len(r['squared_l2'])==len(r['linf'])==5 and np.isfinite(r['squared_l2']+r['linf']+[r['cross'],r['closure_linf']]).all()
        assert min(r['squared_l2']+r['linf']+[r['closure_linf']])>=0
        ss=r['squared_l2'];scale=max(ss[2],ss[3],ss[4],abs(2*r['cross']))
        assert abs(ss[2]-(ss[3]+ss[4]+2*r['cross']))<=1e-12*scale if scale else ss[2]==0
        w=r['witness'];idx=w['index'];assert all(type(i) is int for i in idx) and r['first_group']<=idx[0]<r['first_group']+32 and 0<=idx[1]<32 and 0<=idx[2]<4096
        assert np.isfinite([w['actual'],w['weighted_defect'],w['commutator']]).all()
        assert abs(w['actual'])==r['linf'][2]
        assert abs(w['actual']-w['weighted_defect']-w['commutator'])<=max(r['closure_linf'],1e-15*r['linf'][2])
    domains={}
    for name,part in [('all',rows),('selected',[r for r in rows if r['selected']]),('outside',[r for r in rows if not r['selected']])]:
        ss=[math.fsum(r['squared_l2'][i] for r in part) for i in range(5)];mx=[max(r['linf'][i] for r in part) for i in range(5)];cross=math.fsum(r['cross'] for r in part)
        np.testing.assert_allclose(ss,p['domains'][name]['squared_l2'],rtol=2e-15);np.testing.assert_array_equal(mx,p['domains'][name]['linf']);assert cross==p['domains'][name]['cross']
        norm=p['domains']['all']['squared_l2'][0];maximum=p['domains']['all']['linf'][0]
        domains[name]=dict(squared_l2=ss,linf=mx,cross=cross,l2_over_original=[math.sqrt(v/norm) for v in ss],linf_over_original=[v/maximum for v in mx],squared_budget_over_original=[ss[3]/norm,ss[4]/norm,2*cross/norm],closure_over_original=(ss[2]-ss[3]-ss[4]-2*cross)/norm)
    for a,col in zip(evidence,(1,2)):
        np.testing.assert_allclose(domains['all']['l2_over_original'][col],a['fixed_scale_l2_ratios'][1],rtol=1e-12)
        np.testing.assert_allclose(domains['all']['linf_over_original'][col],a['fixed_scale_linf_ratios'][1],rtol=1e-12)
        np.testing.assert_allclose(math.sqrt(domains['all']['squared_l2'][0]),a['original_defect_l2'],rtol=1e-12)
    assert p['peak_rss_bytes']<6*1024**3
    worst=max(rows,key=lambda r:r['linf'][2]);worstc=max(rows,key=lambda r:r['linf'][4])
    result=dict(archive=read(receipt),accepted_outer_steps=20,new_material_steps=0,maps=0,feedback_pairs=0,passes=1,verified_files=len(manifest['files']),verified_code_claims=len(d['code']),domains=domains,worst_actual=worst,worst_commutator_slab=worstc,peak_rss_bytes=p['peak_rss_bytes'],maximum_closure_linf=max(r['closure_linf'] for r in rows),independent_slab_reduction=True,raw_fields_recomputed_on_mac=False,operator_recomputed_on_mac=False)
    target=Path('handoff/evidence/20260927-taper-commutator-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained');blocks=range(76);M=domains['all']['linf'][0]
    for i,label in [(2,'Actual tapered'),(3,'Weighted defect'),(4,'Noncommutation difference')]:ax.plot(list(blocks),[max(r['linf'][i] for r in rows if r['first_group']//128==b)/M for b in blocks],label=label)
    ax.axhline(1,color='black',ls='--');ax.set(xlabel='Frequency block',ylabel='Maximum absolute component / original global maximum',title='Magnitude comparison; signed components may reinforce or cancel');ax.legend();fig.savefig(target.with_suffix('.png'),dpi=150)
    print(json.dumps({k:v for k,v in result.items() if k not in ('worst_actual','worst_commutator_slab')},indent=2));print('WORST',worst['witness'])


if __name__=='__main__':main()
