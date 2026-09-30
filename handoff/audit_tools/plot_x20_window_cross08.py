"""Separate original feedback quality from vector sensitivity in 82273 cross08."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('handoff/evidence');d=json.loads((p/'20260930-x20-82273-cross08-review.json').read_text())
rows=[];comparisons={n:d['pairs'][name]['within_pair_spread'] for n,name in [('A adjacent','accelerated8'),('H adjacent','historical8')]}
comparisons['Cross seeds']=d['cross_history']['8']['residual_comparison']
for label,c in comparisons.items():
 for den,v,lim in [('r20',c['frozen_r20']['vector_difference_over_frozen_r20_norms'],.001),('signal',c['vector_difference_over_frozen_80195_signal'],.1)]:
  for name,value in zip(['L2','Mass','Max-cell'],np.max(list(v.values()),axis=0)):rows.append([label,den,name,value,lim,value/lim])
with (p/'20260930-x20-82273-cross08-review.csv').open('w') as f:
 w=csv.writer(f,lineterminator="\n");w.writerow(['comparison','denominator','norm','maximum_ratio','reference_tolerance','ratio_to_tolerance']);w.writerows(rows)
fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout='constrained');x=np.arange(3)
for dx,den in [(-.17,'r20'),(.17,'signal')]:
 vals=[r[-1] for r in rows if r[1]==den and r[2]=='Mass'];bars=axs[0].bar(x+dx,vals,.34,label='Difference / '+den+' / tolerance');axs[0].bar_label(bars,labels=[f'{v:.3g}' for v in vals],fontsize=8,padding=3)
axs[0].set(yscale='log',xticks=x,xticklabels=list(comparisons),ylim=(1e-3,2000),title='Mass-weighted full-vector differences')
axs[0].legend(fontsize=8,loc='upper left')
keys=['photoionization_volume_l1','total_recombination_volume_l1','atomic_heating_volume_l1','direct_heating_volume_l1','formal_heating_volume_l1']
vals=[float(np.max([c[k] for c in d['cross_feedback_comparisons']['8'].values()]))/.001 for k in keys]
bars=axs[1].bar(range(5),vals,color=['#487b99' if v<1 else '#b34e42' for v in vals]);axs[1].bar_label(bars,labels=[f'{v:.3g}' for v in vals],fontsize=8,padding=3)
axs[1].set(yscale='log',xticks=range(5),xticklabels=['Photoion','Recomb','Atomic Q','Direct Q','Formal Q'],ylim=(1e-5,100),title='Cross-seed rate/heating difference / 0.001')
for ax in axs:ax.axhline(1,c='red',ls='--')
fig.suptitle('82273 at 8 new maps: original pairs pass; cross-seed agreement fails')
fig.savefig(p/'20260930-x20-82273-cross08-review.png',dpi=160)
print(json.dumps({'rows':rows,'cross_rates_over_tolerance':vals},indent=2))
