"""Small-artifact lower bound for a global affine heat proxy, and block ranking."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import read,digest,arrays,verified_inventory


def main():
    root=Path('outputs/review-20260925');new=root/'heating-validation-77577-complete-received';old=root/'step21-wide-validation-77371-complete-received'
    sources=[]
    for folder,name in [(new,'20260926-heating-validation-complete-review'),(old,'20260925-wide-validation-complete-review')]:
        report=read(Path('handoff/evidence')/(name+'.json'));c=report['archive'];p=root/Path(c['path']).name
        assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
        with tarfile.open(p) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(folder/'ARCHIVE_MANIFEST.json')
        verified_inventory(folder);sources.append(c)
    ref=read(new/'inputs/heating_reference.json');mass=np.array(ref['mass']);scale=np.array(ref['scale']);weight=mass/math.fsum(mass)
    q=[]
    for base,n in [(old,11),(new,2),(new,10)]:
        q.append([arrays(base/f'control/pair{n:02d}/{e}_feedback.npz')['half_atomic_rate_heating_erg_s_cm3'] for e in ('previous','final')])
    s=np.array([(b-a)*scale for a,b in q]);A=(s[:2]-s[2]).T*np.sqrt(weight)[:,None];b=s[2]*np.sqrt(weight)
    coefficients,_,rank,sv=np.linalg.lstsq(A,-b,rcond=None)
    assert rank==2 and sv[-1]>0
    c=np.r_[coefficients,1-sum(coefficients)];z=c@s
    norm=lambda x:math.sqrt(math.fsum(float(w)*float(y)**2 for w,y in zip(weight,x)))
    ratio=norm(z)/norm(s[2]);normal=A.T@(A@coefficients+b)
    assert np.linalg.norm(normal)<1e-12*np.linalg.norm(A)*np.linalg.norm(b)
    blocks=[]
    for i in range(76):
        a=arrays(new/f'control/pair02/feedback/previous/block{i:02d}.npz')['atomic_rate_heating_erg_s_cm3']
        b=arrays(new/f'control/pair10/feedback/final/block{i:02d}.npz')['atomic_rate_heating_erg_s_cm3']
        change=(b-a).reshape(256,16).mean(axis=1)[:128]*scale
        blocks.append(dict(block=i,mass_norm=norm(change)))
    ranked=sorted(blocks,key=lambda x:-x['mass_norm']);assert [x['block'] for x in ranked[:2]]==[24,48]
    result=dict(sources=sources,affine_proxy_lower_bound=dict(pair_sources=['77371 pair11','77577 pair02','77577 pair10'],
        coefficients=c.tolist(),singular_values=sv.tolist(),condition=float(sv[0]/sv[-1]),rank=int(rank),
        ratio_to_latest=ratio,coefficient_l1=float(sum(abs(c))),normal_equation_residual_norm=float(np.linalg.norm(normal)),
        old_twenty_percent_cost_pass=ratio<.8,constrained_field_candidate_checked=False,
        scope='unconstrained optimum in exactly these three paired histories; not a bound on all solvers'),
        block_contributions=blocks,ranking=ranked,selected_local_pilot_blocks=[24,48],
        quantity='fixed dt/rho/u_ref times per-block Q change, pair10 final minus pair02 previous; norms do not add without cancellation',
        accepted_outer_steps=20,new_material_steps=0,new_maps=0)
    Path('handoff/evidence/20260926-heating-subspace-and-block-ranking.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['affine_proxy_lower_bound'],indent=2))


if __name__=='__main__':main()
