"""Necessary descent cones of finite material-response secants, not a Jacobian."""
import argparse,json,itertools,csv
from pathlib import Path
import numpy as np
from operations.review_common_frequency import read,arrays,digest


def positive_interval(gradients):
    """Find theta in [0,1] satisfying every g dot (theta,1-theta) < 0."""
    g=np.asarray(gradients,float)
    if g.ndim!=2 or g.shape[1]!=2 or not np.isfinite(g).all():raise ValueError('invalid gradients')
    lo,hi=0.,1.;bounds=[]
    for row in g:
        a,b=row[0]-row[1],row[1]
        if a==0:
            if b>=0:return {'feasible':False,'reason':'constant_nonnegative','bounds':bounds}
        else:
            x=-b/a;bounds.append({'side':'lower' if a<0 else 'upper','value':float(x)})
            if a<0:lo=max(lo,float(x))
            else:hi=min(hi,float(x))
    if lo>=hi:return {'feasible':False,'reason':'incompatible_bounds','lower':lo,'upper':hi,'bounds':bounds}
    mid=(lo+hi)/2
    if not np.all(g@np.array([mid,1-mid])<0):raise ArithmeticError('interval witness verification failed')
    return {'feasible':True,'lower':lo,'upper':hi,'witness':[mid,1-mid],'bounds':bounds}


def norm_gradients(control,thermal,population,mass):
    c,t,p=[np.asarray(x,float).reshape(-1,4) for x in (control,thermal,population)];mass=np.asarray(mass,float)
    if c.shape!=t.shape or c.shape!=p.shape or mass.shape!=(len(c),) or not all(np.isfinite(x).all() for x in (c,t,p,mass)) or np.any(mass<=0):raise ValueError('invalid residual/mass')
    d=np.stack((t-c,p-c));weights=mass/mass.sum();sq=np.sum(c*c,axis=1);active=np.flatnonzero(sq==sq.max())
    # 使用平方范数，正范数处的下降符号相同；不删除任何残差分量。
    rows=[2*np.sum(d*c,axis=(1,2)),2*np.sum(d*c*weights[:,None],axis=(1,2))]
    labels=['l2_squared','mass_squared']
    for i in active:rows.append(2*np.sum(d[:,i,:]*c[i],axis=1));labels.append('max_cell_'+str(i)+'_squared')
    return np.array(rows),labels,active.tolist()


def analyze(stages,old,output):
    mass=arrays(old)['cell_mass_g_cm2'];claims=[{'path':str(old),'sha256':digest(old)}];results={};table=[]
    expected=read(stages['77126']/'control/pair03/feedback_protocol.json')['sources']['physical_old_time_level']
    assert old.stat().st_size==expected['size_bytes'] and digest(old)==expected['sha256']
    for label,root in stages.items():
        inv={c['path']:c for c in read(root/'ARCHIVE_MANIFEST.json')['files']};v={}
        for name in ('control','thermal','population'):
            v[name]={}
            for end in ('previous','final'):
                rel=f'{name}/pair03/{end}_response.npz';p=root/rel;c=inv[rel]
                assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256'];claims.append({'path':str(p),'sha256':c['sha256']})
                v[name][end]=arrays(p)['residual']
        entries={};pooled=[]
        for ec,et,ep in itertools.product(('previous','final'),repeat=3):
            gradients,labels,active=norm_gradients(v['control'][ec],v['thermal'][et],v['population'][ep],mass)
            # 四象限分别诊断；权重是物质有限差商，不是辐射uv。
            quadrants={}
            for signs in itertools.product((1.,-1.),repeat=2):
                q=positive_interval(gradients*np.array(signs));quadrants[str(signs)]=q
            key=f'{ec}/{et}/{ep}';entries[key]={'labels':labels,'gradients':gradients.tolist(),'active_cells':active,'quadrants':quadrants}
            pooled.extend(gradients)
            for l,g in zip(labels,gradients):table.append([label,key,l,*g])
        results[label]={'endpoints':entries,'all_endpoint_positive_cone':positive_interval(pooled),
                        'all_endpoint_signed_cones':{str(s):positive_interval(np.array(pooled)*s) for s in itertools.product((1.,-1.),repeat=2)}}
    record={'claims':claims,'stages':results,'definition':'C+a*(thermal-C)+b*(population-C), gradient of squared norms at a=b=0',
            'finite_secant_amplitude':1/256,'strict_jacobian_established':False,'actual_candidate_written':False,'new_maps':0,
            'conclusion_scope':'finite affine-response surrogate only; no physical no-solution or true derivative claim',
            'accepted_outer_steps':20}
    output.with_suffix('.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['stage','control/thermal/pop endpoint','squared_norm','thermal_gradient','population_gradient']);w.writerows(table)
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,len(stages),figsize=(6*len(stages),4),layout='constrained');axs=np.atleast_1d(axs)
    theta=np.linspace(0,1,401)
    for ax,(label,r) in zip(axs,results.items()):
        row=r['endpoints']['final/final/final']
        for name,g in zip(row['labels'],row['gradients']):
            scale=max(abs(x) for x in g)
            ax.plot(theta,np.array(g)@np.array([theta,1-theta])/scale if scale else np.zeros_like(theta),label=name)
        ax.axhline(0,color='black');ax.set(title=label,xlabel='Thermal share theta (population=1-theta)',ylabel='Scaled squared-norm directional slope');ax.legend()
    fig.suptitle('Finite-response surrogate: necessary descent, not a physical derivative')
    fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',type=Path,required=True);p.add_argument('--current',type=Path,required=True)
    p.add_argument('--old',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=analyze({'76957':a.prior,'77126':a.current},a.old,a.output)
    print(json.dumps({k:{j:v for j,v in x.items() if j!='endpoints'} for k,x in r['stages'].items()},indent=2))
