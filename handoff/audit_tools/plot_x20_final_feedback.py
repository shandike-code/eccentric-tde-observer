"""Final finite-window comparisons and signed heat-response localization."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('handoff/evidence');r=json.loads((root/'20260930-x20-81769-final-review.json').read_text())
d=json.loads((root/'20260930-x20-81769-energy-decomposition.json').read_text())
cs=[r['pairs'][n+'16']['eight_map_window'] for n in ('accelerated','historical')]+[r['cross_history']['16']['residual_comparison']]
labels=['Accelerated\n16 minus 8','Historical\n16 minus 8','Cross seeds\nmap16'];names=['L2','Mass weighted','Maximum cell'];rows=[]
fig,axs=plt.subplots(2,2,figsize=(11,7),layout='constrained')
for ax,key,title,gate in [(axs[0,0],'reference','Full residual difference / frozen r20',.001),(axs[0,1],'signal','Full residual difference / frozen signal',.1)]:
 for i,name in enumerate(names):
  values=[max(v[i] for v in (c['frozen_r20']['vector_difference_over_frozen_r20_norms'] if key=='reference' else c['vector_difference_over_frozen_80195_signal']).values()) for c in cs]
  ax.plot(np.arange(3)+(i-1)*.1,values,'o',label=name)
  for j,v in enumerate(values):rows.append(dict(comparison=labels[j].replace('\n',' '),metric=name,scale=key,value=v))
 ax.axhline(gate,color='#bc443b',ls='--');ax.set(yscale='log',xticks=range(3),xticklabels=labels,title=title);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
ax=axs[1,0];fb=d['comparisons']['cross16']['final_vs_final'];weights=[v['signed_projection_fraction'] for v in fb['blocks']]
ax.bar(range(76),weights,color=['#217b95' if w>=0 else '#bc443b' for w in weights]);ax.axhline(0,color='black',lw=.5);ax.set(xlabel='Natural frequency block (all 76 retained)',ylabel='Signed projection fraction',title='Cross16 final/final: log-gas response contribution')
for i,w in enumerate(weights):rows.append(dict(comparison='cross16 final/final',metric=str(i),scale='signed projection',value=w))
ax=axs[1,1];heat=[max(v['atomic_heating_volume_l1'] for v in r['cross_feedback_comparisons'][str(n)].values()) for n in (8,16)]
ax.bar(['Cross08','Cross16'],heat,color=['#83b6bd','#217b95']);ax.axhline(.001,color='#bc443b',ls='--');ax.set(yscale='log',ylim=(.0005,.05),title='Cross-seed atomic heating comparison')
for i,v in enumerate(heat):ax.text(i,v*1.1,f'{v:.6f}',ha='center');rows.append(dict(comparison='cross'+str((8,16)[i]),metric='atomic heating',scale='original',value=v))
fig.suptitle('81769 complete: accelerated window passes; reference calibration fails')
fig.savefig(root/'20260930-x20-81769-final-review.png',dpi=160)
with (root/'20260930-x20-81769-final-review.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
