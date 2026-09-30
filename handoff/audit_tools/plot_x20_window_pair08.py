"""Plot first-pair reproducibility separately from the change from old feedback."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('handoff/evidence');d=json.loads((p/'20260930-x20-82273-accelerated08-review.json').read_text())
r=d['pairs']['accelerated8'];rows=[]
for label,key in [('Adjacent endpoints','within_pair_spread'),('Versus old A16','from_prior_feedback')]:
    z=r[key]
    for norm,values,limit in [('r20',z['frozen_r20']['vector_difference_over_frozen_r20_norms'],.001),('signal',z['vector_difference_over_frozen_80195_signal'],.1)]:
        peaks=np.max(list(values.values()),axis=0)
        for name,value in zip(['L2','Mass','Linf'],peaks):rows.append([label,norm,name,value,limit,value/limit])
with (p/'20260930-x20-82273-accelerated08-review.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['comparison','denominator','norm','maximum_four_endpoint_ratio','tolerance','ratio_to_tolerance']);w.writerows(rows)
fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
x=np.arange(3)
for ax,norm in zip(axes,['r20','signal']):
    for dx,label in [(-.16,'Adjacent endpoints'),(.16,'Versus old A16')]:
        vals=[z[-1] for z in rows if z[0]==label and z[1]==norm]
        bars=ax.bar(x+dx,vals,.32,label=label)
        ax.bar_label(bars,labels=[f'{v:.3g}' for v in vals],padding=3,fontsize=8)
    ax.axhline(1,c='red',ls='--',label='Reference tolerance')
    ax.set(yscale='log',xticks=x,xticklabels=['L2','Mass','Linf'],ylim=(1e-4,20),title='Vector difference / '+norm+' / tolerance')
axes[0].legend(fontsize=8)
fig.suptitle('82273 A08: adjacent feedback stable; longer windows not yet evaluated')
fig.savefig(p/'20260930-x20-82273-accelerated08-review.png',dpi=160)
print(json.dumps({'current_mass_residual':r['endpoints']['final']['norms']['mass_weighted'],'ratio_to_original_r20_mass':r['endpoints']['final']['norms']['mass_weighted']/.2619104204778557}))
