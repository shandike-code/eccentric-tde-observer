"""Bounded finite-amplitude surrogate with both frozen and matched baselines."""
import argparse,itertools,json,csv
from pathlib import Path
import numpy as np
from operations.review_common_frequency import read,arrays,digest


def norms(v,mass):
    v=np.asarray(v,float);mass=np.asarray(mass,float)
    if v.ndim!=3 or v.shape[1:]!=(len(mass),4) or not np.isfinite(v).all() or np.any(mass<=0) or not np.isfinite(mass).all():raise ValueError('invalid vectors')
    sq=np.sum(v*v,axis=2)
    return np.stack((np.sqrt(sq.sum(axis=1)),np.sqrt(sq@(mass/mass.sum())),np.sqrt(sq.max(axis=1))),axis=1)


def screen(c,t,p,mass,r20):
    c,t,p=[np.asarray(x,float) for x in (c,t,p)]
    if c.shape!=t.shape or c.shape!=p.shape:raise ValueError('mismatched endpoint sets')
    original=norms(np.asarray(r20).reshape(1,-1,4),mass);matched=norms(c,mass)
    if np.any(original<=0) or np.any(matched<=0):raise ValueError('zero denominator')
    rows=[]
    for ae,ap in itertools.product(np.arange(17)/8,np.arange(49)/4):
        pred=c+ae*(t-c)+ap*(p-c);n=norms(pred,mass)
        o=(n/original).max(axis=0);m=(n/matched).max(axis=0)
        rows.append({'thermal_weight':float(ae),'population_weight':float(ap),'worst_original_ratios':o.tolist(),'worst_matched_ratios':m.tolist(),'score':float(max(o.max(),m.max()))})
    return rows


def analyze(prior,current,old,reference,cone,output):
    proof=read(cone);claims={c['path']:c['sha256'] for c in proof['claims']}
    def checked(path):
        assert digest(path)==claims[str(path)];return arrays(path)['residual'].reshape(128,4)
    mass=arrays(old)['cell_mass_g_cm2'];assert digest(old)==claims[str(old)]
    p=read(current/'control/pair03/feedback_protocol.json');claim=p['sources']['base_residual'];r20=np.load(reference,allow_pickle=False)
    assert reference.stat().st_size==claim['size_bytes'] and digest(reference)==claim['sha256']
    c=[];t=[];pop=[];labels=[]
    for stage,root in [('76957',prior),('77126',current)]:
        v={name:{e:checked(root/f'{name}/pair03/{e}_response.npz') for e in ('previous','final')} for name in ('control','thermal','population')}
        for ec,et,ep in itertools.product(('previous','final'),repeat=3):
            c.append(v['control'][ec]);t.append(v['thermal'][et]);pop.append(v['population'][ep]);labels.append([stage,ec,et,ep])
    rows=screen(c,t,pop,mass,r20);best=min(rows,key=lambda x:x['score']);result={'source_cone_sha256':digest(cone),'original_residual_sha256':digest(reference),'endpoint_combinations':labels,'rows':rows,'best':best,'predicted_pass_count':sum(r['score']<1 for r in rows),'accepted_outer_steps':20,'new_maps':0,'actual_candidate_written':False,'physical_prediction_validated':False}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['thermal_weight','population_weight','worst_score','original_L2','original_mass','original_max','matched_L2','matched_mass','matched_max'])
        for r in rows:w.writerow([r['thermal_weight'],r['population_weight'],r['score'],*r['worst_original_ratios'],*r['worst_matched_ratios']])
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained');im=ax.imshow(np.array([r['score'] for r in rows]).reshape(17,49),origin='lower',aspect='auto',extent=[-.125,12.125,-.0625,2.0625]);fig.colorbar(im,ax=ax,label='Worst predicted norm ratio (both baselines)')
    ax.plot(best['population_weight'],best['thermal_weight'],'rx');ax.set(xlabel='Population finite-response weight',ylabel='Thermal finite-response weight',title='Finite-response grid; not a validated material candidate');fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({k:result[k] for k in ('best','predicted_pass_count','physical_prediction_validated')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('prior','current','old','reference','cone','output'):p.add_argument('--'+k,type=Path,required=True)
    analyze(**vars(p.parse_args()))
