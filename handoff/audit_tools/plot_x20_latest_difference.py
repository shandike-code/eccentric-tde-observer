"""Show finite one-map chord actions and all natural-block difference shares."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
root=Path('handoff/evidence');r=json.loads((root/'20260930-x20-window-difference-82396-review.json').read_text());rows=[]
fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for j,n in enumerate(('8','16')):
 total=r['results'][n]['total'];gain=total['mapped_difference_l2_ratio']
 ax[0].plot(j,gain,'o',color=['#408aa2','#cb7748'][j]);ax[0].text(j,gain+.0001,f'{gain:.8f}',ha='center')
 for k in ('relative_change_l2','rayleigh_action','mapped_difference_l2_ratio'):rows.append(dict(checkpoint=n,quantity=k,block='',value=total[k]))
 shares=[r['results'][n]['blocks'][str(i)]['dd']/total['dd'] for i in range(76)]
 ax[1].bar(np.arange(76)+(j-.5)*.4,shares,width=.4,label='map'+n,color=['#408aa2','#cb7748'][j])
 for i,v in enumerate(shares):rows.append(dict(checkpoint=n,quantity='unweighted squared difference share',block=i,value=v))
ax[0].set(xticks=[0,1],xticklabels=['map08','map16'],ylim=(.99,1.0007),xlim=(-.5,1.5),ylabel='Norm of mapped difference / input difference',title='Each point is one actual map, not a fitted rate')
old=json.loads((root/'20260930-x20-82039-review.json').read_text());ax[0].plot([0,1],[old['results'][n]['total']['mapped_difference_l2_ratio'] for n in ('8','16')],'s--',label='Earlier 81769 endpoints',color='gray');ax[0].legend(loc='lower left',fontsize=8);ax[0].axhline(1,color='gray',ls='--');ax[0].grid(axis='y',alpha=.2)
ax[1].set(xlabel='Natural frequency block (all 76 retained)',ylabel='Fraction of unweighted squared difference',title='Field difference is concentrated in the same bands');ax[1].legend()
fig.suptitle('82396: latest endpoints retain a slowly decaying difference')
fig.savefig(root/'20261001-x20-82396-comparison.png',dpi=160)
for row in rows: row['source_job']=82396
for n in ('8','16'): rows.append(dict(checkpoint=n,quantity='mapped_difference_l2_ratio',block='',value=old['results'][n]['total']['mapped_difference_l2_ratio'],source_job=82039))
with (root/'20261001-x20-82396-comparison.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
