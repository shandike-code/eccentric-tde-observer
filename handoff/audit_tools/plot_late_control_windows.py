"""Plot audited local versus historical control drift without recomputing physics."""
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt


def main():
    source=Path('handoff/evidence/20260928-refreshed-directions-complete-review.json')
    current=Path('handoff/evidence/20260928-late-direction-control08-review.json')
    before=json.loads(source.read_text())['pairs'];after=json.loads(current.read_text())['pairs']['control08']
    rows=[]
    for n,r,hkey in [(8,before['control08'],'cumulative'),(16,before['control16'],'cumulative'),(24,after,'historical')]:
        row=dict(maps_since_78594=n)
        for key,item in [('local',r['window']),('historical',r[hkey])]:
            values=np.asarray(list(item['vector_difference_over_frozen_r20_norms'].values()),float)
            assert values.shape==(4,3) and np.isfinite(values).all() and np.all(values>=0)
            # 每个范数分别取4端点组合的最大值；不挑单一有利端点。
            row[key]=values.max(axis=0).tolist()
        rows.append(row)
    evidence=dict(rows=rows,norm_order=['L2','mass weighted','maximum cell'],tolerance=.001,
        sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (source,current)],
        physical_time_advanced=False,strict_error_bound=False)
    out=Path('handoff/evidence/20260928-late-control-window-comparison')
    out.with_suffix('.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained',sharey=True)
    for ax,key,title in zip(axes,['local','historical'],['Each eight-map window','Cumulative from the 78594 endpoint']):
        for i,label in enumerate(evidence['norm_order']):
            ax.plot([r['maps_since_78594'] for r in rows],[r[key][i] for r in rows],'o-',label=label)
        ax.axhline(.001,color='black',ls='--',label='declared threshold')
        ax.set(title=title,xlabel='Numerical maps since 78594 (not physical steps)',xticks=[8,16,24])
        ax.ticklabel_format(axis='y',style='sci',scilimits=(0,0));ax.legend(fontsize=8)
    axes[0].set_ylabel('Worst vector change / frozen r20 norm')
    fig.suptitle('Local checks pass while historical mass-weighted drift crosses the threshold')
    fig.savefig(out.with_suffix('.png'),dpi=160);plt.close(fig)


if __name__=='__main__':main()
