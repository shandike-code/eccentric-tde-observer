"""Independent small-statistic reduction of the two-pass, zero-map proposal."""
import argparse,json,math
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,read,digest


def quadratic(g,c):
    return math.fsum(c[i]*g[i][j]*c[j] for i in range(3) for j in range(3))


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    root=Path('outputs/review-20260925');out=root/'boundary-proposal-80005-received'
    manifest=receive(a.archive,a.receipt,out)
    d=read(out/'declaration.json');s=read(out/'summary.json');g=read(out/'gram.json');pred=read(out/'prediction.json')
    terminal=read(Path('handoff/evidence/20260928-boundary-proposal-80005-terminal.json'))
    assert terminal['job_id']==80005 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['job_id']=='80005' and d['source_job_id']==79878 and d['maximum_field_scans']==2 and d['maximum_coefficients']==1
    assert d['maximum_maps']==d['maximum_feedback_pairs']==d['new_material_steps']==0
    assert not d['production_candidate_written'] and not d['operator_recomputed'] and d['half_anchor']=='original 79151 x'
    assert s['status']=='complete_requires_review' and s['source_unchanged'] and s['field_scans']==2 and s['accepted_outer_steps']==20
    assert s['new_maps']==s['new_feedback_pairs']==s['new_material_steps']==0 and not s['production_candidate_written'] and not s['operator_recomputed']
    assert s['peak_rss_bytes']<8*1024**3 and s['wall_s']<1800
    for c in d['code']:
        path=Path(c['path']);assert digest(path)==c['sha256'] and path.stat().st_size==c['size_bytes']
    prior=root/'population-defect-global-79878-received';pd=read(prior/'declaration.json');pv=read(prior/'population/validation.json')
    row=pv['actual_map'];last=[pv['candidate'],dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=10099884032)]
    assert d['field_pairs']==pd['original_pair']+pd['source_pair']+last
    for rows in (g['rows'],g['boundary'],pred['rows']):assert [r['first_group'] for r in rows]==list(range(0,9632,32))
    assert all(r['group_count']==32 for r in g['rows']+pred['rows'])
    matrix=[[math.fsum(r['gram'][i][j] for r in g['rows']) for j in range(3)] for i in range(3)]
    np.testing.assert_allclose(matrix,g['gram'],rtol=2e-13,atol=0)
    for i in range(3):
        for j in range(3):assert matrix[i][j]==matrix[j][i]
    assert np.isfinite(matrix).all() and np.linalg.eigvalsh(matrix).min()>=-1e-13*np.max(abs(np.array(matrix)))
    delta=[math.fsum(r['signed'][i] for r in g['boundary']) for i in range(3)]
    np.testing.assert_allclose(delta,g['signed'],rtol=2e-13,atol=0)
    ds=[delta[0],delta[1]-delta[0],delta[2]-delta[1]]
    # 独立用标量求和展开约束线上的二次式，不调用生产系数求解函数。
    intercept=-ds[0]/ds[2];slope=-ds[1]/ds[2]
    roots=sorted((-intercept/slope,(1-intercept)/slope));lo,hi=max(0.,roots[0]),min(1.,roots[1]);assert lo<=hi
    c0=[1.,0.,intercept];c1=[0.,1.,slope]
    curvature=quadratic(matrix,c1);linear=math.fsum(c1[i]*matrix[i][j]*c0[j] for i in range(3) for j in range(3))
    assert curvature>0
    optimum=-linear/curvature
    aa=lo if optimum<lo else hi if optimum>hi else optimum;bb=intercept+slope*aa
    coef=g['coefficients'];assert coef==s['coefficients']
    np.testing.assert_allclose([aa,bb], [coef['a'],coef['b']],rtol=2e-12,atol=1e-15)
    assert 0<=aa<=1 and 0<=bb<=1
    assert abs(math.fsum(c*t for c,t in zip((1,aa,bb),ds)))<=1e-12*max(abs(t) for t in ds)
    squares=[math.fsum(r['squared_l2'][i] for r in pred['rows']) for i in range(5)]
    maxima=[max(r['linf'][i] for r in pred['rows']) for i in range(5)]
    expected=[quadratic(matrix,c) for c in ([1,0,0],[1,aa,bb],[1,aa/2,bb/2],[1,1,0],[1,1,1])]
    # 用源场幅度界估计先组合强度再相减的舍入误差，不事后调相对容差。
    origins=[root/'late-direction-79151-complete-received/population/map0008',
             root/'late-population-global-79631-received/population/map0001',prior/'population/map0001']
    scale=max(read(folder/f'block{i:02d}.json')['maximum_radiation_scale'] for folder in origins for i in range(76))
    entry_error=64*np.finfo(float).eps*scale
    norm_error=math.sqrt(9632*32*4096)*entry_error
    coeffs=([1,0,0],[1,aa,bb],[1,aa/2,bb/2],[1,1,0],[1,1,1])
    bounds=[2*math.sqrt(t)*norm_error+norm_error**2+2e-11*math.fsum(abs(c[i]*matrix[i][j]*c[j]) for i in range(3) for j in range(3))
            for t,c in zip(expected,coeffs)]
    assert all(abs(x-y)<=bound for x,y,bound in zip(squares,expected,bounds))
    differences=[abs(x/y-1) for x,y in zip(squares,expected)]
    np.testing.assert_allclose(squares,pred['squared_l2'],rtol=2e-13,atol=0)
    assert maxima==pred['linf'] and all(all(math.isfinite(v) and v>=0 for v in r['minima']) for r in pred['rows'])
    l2=[math.sqrt(t/squares[0]) for t in squares];linf=[t/maxima[0] for t in maxima]
    np.testing.assert_allclose(l2,pred['l2_ratios'],rtol=2e-13,atol=0)
    assert linf==pred['linf_ratios']
    for col,slabs in ((0,pv['original_comparison']['slabs']),(3,pv['field_comparison']['slabs']),(4,pv['field_comparison']['slabs'])):
        sourcecol=1 if col==4 else 0
        actual=math.fsum(r['squared_l2'][sourcecol] for r in slabs)
        assert math.isclose(squares[col],actual,rel_tol=2e-11)
        assert maxima[col]==max(r['linf'][sourcecol] for r in slabs)
    flux=[math.fsum(r['flux_totals'][i] for r in pred['rows']) for i in range(4)]
    signed=[math.fsum(r['signed_flux'][i] for r in pred['rows']) for i in range(2)]
    l1=[math.fsum(r['spectrum_change_l1'][i] for r in pred['rows'])/max(flux[2*i:2*i+2]) for i in range(2)]
    bol=[abs(signed[i])/max(flux[2*i:2*i+2]) for i in range(2)]
    np.testing.assert_allclose(flux,pred['flux'],rtol=2e-13,atol=0)
    assert signed==pred['signed_flux'] and l1==pred['boundary_l1'] and bol==pred['boundary_bolometric']
    original=pd['original_row'];checks=dict(full_l2_benefit=l2[1]<=.8,full_linf_nonincrease=linf[1]<=1.0000000001,
        half_l2_nonincrease=l2[2]<=1.0000000001,half_linf_nonincrease=linf[2]<=1.0000000001)
    for i,name in enumerate(('full','half')):
        for key,values in [('boundary_l1',l1),('boundary_bolometric',bol)]:
            checks[name+'_'+key]=values[i]<1e-3 and values[i]<=original[key]*1.0000000001
    assert checks==pred['checks'] and all(checks.values())==s['all_predicted_checks_passed']==pred['all_predicted_checks_passed']
    assert not pred['genuine_transfer_map'] and pred['half_anchor']=='original 79151 x'
    result=dict(job_id=80005,source_job_id=79878,archive=read(a.receipt),verified_files=len(manifest['files']),
        verified_code_claims=len(d['code']),coefficients=dict(a=aa,b=bb),gram=matrix,signed_basis=ds,
        l2_ratios=l2,linf_ratios=linf,boundary_l1=l1,boundary_bolometric=bol,checks=checks,
        all_predicted_checks_passed=all(checks.values()),gram_to_field_squared_relative_differences=differences,gram_to_field_absolute_roundoff_bounds=bounds,
        original_nonincrease_bolometric=original['boundary_bolometric'],peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],
        raw_arrays_read_on_mac=False,independent_small_statistic_reduction=True,actual_map_required=True,accepted_outer_steps=20,new_material_steps=0)
    target=Path('handoff/evidence/20260928-boundary-proposal-independent-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib.pyplot as plt
    grid=np.linspace(lo,hi,121);bg=intercept+slope*grid
    norm=[math.sqrt(quadratic(matrix,[1,a,b])/matrix[0][0]) for a,b in zip(grid,bg)]
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    axes[0].plot(grid,norm);axes[0].scatter([aa],[math.sqrt(quadratic(matrix,[1,aa,bb])/matrix[0][0])]);axes[0].axhline(.8,ls='--',color='black')
    axes[0].set(xlabel='Coefficient a on boundary-neutral line',ylabel='Predicted L2 / original L2',title='Affine predictor only; actual map pending')
    axes[1].bar(['Original','Full prediction','Half prediction'],[original['boundary_bolometric'],*bol]);axes[1].axhline(original['boundary_bolometric'],ls='--',color='black')
    axes[1].set(ylabel='Boundary map change / flux scale',title='Half anchored at original x')
    fig.savefig(target.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':main()
