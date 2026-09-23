"""Combine all recorded source components without accepting failed arithmetic checks."""
import argparse
from pathlib import Path
import json
import numpy as np
from operations.review_outer_step_snapshot import read,digest,arrays
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
KINDS=('rate','direct','formal')
COMPONENTS=('absorption','emission','scattering')


def verify_package(root):
    m=read(root/'MANIFEST.json')
    for c in m['files']:
        p=root/c['path'];assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    return len(m['files'])


def review(package,tail,source,output):
    counts=[verify_package(package),verify_package(tail)]
    full=package/'formal-source-split-all-20260923'
    assert read(full/'status.json')['status']=='failed'
    assert read(tail/'summary.json')['measurement_only_not_acceptance']
    original_run=Path('outputs/hpc/step16-backtrack-20260923');rd=source/'full/feedback-round1';manifest=read(rd/'feedback/final_manifest.json');fb=arrays(rd/'final_feedback.npz');width=fb['subcell_width_cm'];total={};rows=[];failed=[];bounds={k:0. for k in KINDS};tail_bounds={k:0. for k in KINDS};tail_reports=[]
    for i,m in enumerate(manifest['completed_blocks']):
        assert m['block_index']==i
        root=full if (full/f'block{i:02d}.json').exists() else tail
        report=read(root/f'block{i:02d}.json');path=root/f'block{i:02d}.npz';assert digest(path)==report['arrays']['sha256'];assert report['original_source_bitwise_replayed']
        receipt=read(root/f'block{i:02d}.process.json');assert receipt['returncode']==0 and receipt['memory_guard_passed'] and report['native_peak_mib']<6144
        a=arrays(path);assert all(np.isfinite(v).all() for v in a.values())
        oldpath=source/Path(m['partial_path']).relative_to(original_run);assert digest(oldpath)==m['partial_sha256'];old=arrays(oldpath)
        for k in KINDS:assert np.array_equal(a['original_'+k],old['source_'+k+'_heating_erg_s_cm3'])
        if not total:total={k:np.zeros_like(v) for k,v in a.items()}
        for k,v in a.items():total[k]+=v
        row={'block':i};bad=[]
        for k in KINDS:
            pieces=[a[c+'_'+k] for c in COMPONENTS];delta=sum(pieces)-a['original_'+k];scale=max(float(np.max(sum(np.abs(v) for v in pieces))),float(np.max(np.abs(a['original_'+k]))));error=float(np.max(np.abs(delta)));relative=error/scale if scale>0 else error
            assert np.isclose(relative,report['linear_closure_error'][k],rtol=1e-10,atol=0)
            if relative>1e-12:bad.append(k)
            # Triangle inequality bounds column error from all block splits.
            bound=float(np.sum(width.astype(np.longdouble)*np.abs(delta.astype(np.longdouble))))
            bounds[k]+=bound
            if root==tail:tail_bounds[k]+=bound
        if bad:failed.append({'block':i,'failed_components':bad})
        if root==tail:tail_reports.append(report)
        for c in ('original',*COMPONENTS,'beta0'):row[c]=float(np.sum(width.astype(np.longdouble)*(a[c+'_rate'].astype(np.longdouble)-a[c+'_formal'].astype(np.longdouble))))
        rows.append(row)
    assert len(rows)==76
    for k in KINDS:assert np.array_equal(total['original_'+k],fb['source_'+k+'_heating_erg_s_cm3'])
    metrics={}
    for c in ('original',*COMPONENTS,'beta0'):
        r=total[c+'_rate'].astype(np.longdouble);f=total[c+'_formal'].astype(np.longdouble);w=width.astype(np.longdouble)
        ri,fi=np.sum(w*r),np.sum(w*f)
        metrics[c]={'rate_integral':float(ri),'formal_integral':float(fi),'signed_difference':float(np.sum(w*(r-f))),'difference_depth_l1':float(np.sum(w*np.abs(r-f))),'net_relative_difference':float(abs(ri-fi)/max(abs(ri),abs(fi))) if max(abs(ri),abs(fi))>0 else None}
    full_closure={k:float(np.sum(width.astype(np.longdouble)*np.abs((sum(total[c+'_'+k] for c in COMPONENTS)-total['original_'+k]).astype(np.longdouble)))) for k in KINDS}
    result={'verified_files':counts,'all_76_block_original_arrays_match':True,'failed_original_linearity_checks_retained':failed,'metrics':metrics,'blockwise_triangle_bound_erg_s_cm2':bounds,'tail_only_triangle_bound_erg_s_cm2':tail_bounds,'assembled_component_closure_l1_erg_s_cm2':full_closure,'tail_measurements':tail_reports,'block_signed_contributions':rows,'longdouble_used_only_for_stored_integral_audit':True,'full_diagnostic_promoted_to_pass':False,'material_step_accepted':False,'scientific_gates_changed':False}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    fig,ax=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    names=['original',*COMPONENTS,'beta0'];ax[0].bar(names,[metrics[n]['signed_difference'] for n in names]);ax[0].set_yscale('symlog',linthresh=10);ax[0].set(ylabel='Signed column discrepancy (erg s$^{-1}$ cm$^{-2}$)',title='All 76 blocks; failed split checks retained');ax[0].tick_params(axis='x',rotation=30)
    for c in ('original',*COMPONENTS):ax[1].plot(range(76),np.cumsum([r[c] for r in rows]),label=c)
    ax[1].set(xlabel='Frequency block',ylabel='Cumulative signed discrepancy',title='Individual bands exchange energy between frames');ax[1].legend()
    fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({k:result[k] for k in ('verified_files','metrics','failed_original_linearity_checks_retained','blockwise_triangle_bound_erg_s_cm2','tail_only_triangle_bound_erg_s_cm2','assembled_component_closure_l1_erg_s_cm2')},indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--tail',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();review(a.package,a.tail,a.source,a.output)

if __name__=='__main__':main()
