"""Compare adjacent-pair and cross-seed feedback at map08, never a convergence curve."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('handoff/evidence');r=json.loads((root/'20260930-x20-81769-cross08-review.json').read_text())
cs=[r['pairs']['accelerated8']['within_pair_spread'],r['pairs']['historical8']['within_pair_spread'],r['cross_history']['8']['residual_comparison']]
labels=['Accelerated\nadjacent','Historical\nadjacent','Cross seeds\nmap08'];names=['L2','Mass weighted','Maximum cell'];rows=[]
fig,axs=plt.subplots(1,3,figsize=(13.6,4.3),layout='constrained')
for ax,key,title,gate in [(axs[0],'reference','Difference / frozen r20',.001),(axs[1],'signal','Difference / frozen 80195 signal',.1)]:
 for i,name in enumerate(names):
  values=[max(v[i] for v in (c['frozen_r20']['vector_difference_over_frozen_r20_norms'] if key=='reference' else c['vector_difference_over_frozen_80195_signal']).values()) for c in cs]
  ax.plot(np.arange(3)+(i-1)*.09,values,'o',label=name)
  for j,v in enumerate(values):rows.append(dict(comparison=labels[j].replace('\n',' '),norm=name,scale=key,ratio=v,threshold=gate))
 ax.axhline(gate,color='#c54b33',ls='--');ax.set(yscale='log',xticks=range(3),xticklabels=labels,title=title);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
ax=axs[2];heat=[r['pairs']['accelerated8']['comparison']['atomic_heating_volume_l1'],r['pairs']['historical8']['comparison']['atomic_heating_volume_l1'],max(c['atomic_heating_volume_l1'] for c in r['cross_feedback_comparisons']['8'].values())]
ax.bar(range(3),heat,color=['#197d9a','#83b6bd','#cd8646']);ax.axhline(.001,color='#c54b33',ls='--');ax.set(yscale='log',xticks=range(3),xticklabels=labels,title='Atomic heating comparison')
for i,y in enumerate(heat):ax.text(i,y*1.2,f'{y:.3e}',ha='center',fontsize=8)
ax.set_ylim(5e-7,.09)
fig.suptitle('81769 map08: each original pair passes; cross-seed response is not yet reproducible',fontsize=12)
fig.savefig(root/'20260930-x20-81769-cross08-review.png',dpi=160)
with (root/'20260930-x20-81769-cross08-review.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
