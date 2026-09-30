"""Two different feedback comparisons; neither is the pending 16-minus-8 window."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('handoff/evidence');r=json.loads((root/'20260930-x20-81769-accelerated08-review.json').read_text())
labels=['Adjacent endpoints','New pair vs old late16']
cs=[r['within_pair_spread'],r['from_prior_feedback']];names=['L2','Mass weighted','Maximum cell'];rows=[]
fig,axs=plt.subplots(1,2,figsize=(11.8,4.1),layout='constrained')
for ax,key,denom,gate in [(axs[0],'frozen_r20','Frozen r20 norm',.001),(axs[1],'signal','Frozen 80195 signal norm',.1)]:
 for i,name in enumerate(names):
  vals=[max(v[i] for v in (c['frozen_r20']['vector_difference_over_frozen_r20_norms'] if key=='frozen_r20' else c['vector_difference_over_frozen_80195_signal']).values()) for c in cs]
  assert all(np.isfinite(vals)) and min(vals)>0
  ax.plot(range(2),vals,'o',markersize=8,label=name)
  for j,value in enumerate(vals):rows.append(dict(comparison=labels[j].replace('\n',' '),norm=name,denominator=denom,ratio=value,gate=gate))
 ax.axhline(gate,color='#c54b33',ls='--',label='Declared comparison gate')
 ax.set(yscale='log',xticks=[0,1],xticklabels=labels,ylabel=f'Full vector difference / {denom}')
 ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
fig.suptitle('81769 accelerated pair08: original seven gates pass\nTwo comparisons, not time evolution; 16-minus-8 windows still untested',fontsize=12)
fig.savefig(root/'20260930-x20-81769-accelerated08-review.png',dpi=170)
with (root/'20260930-x20-81769-accelerated08-review.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
print(json.dumps(dict(within_pair=r['within_pair_spread'],remaining_min={k:v['minimum_gas_erg_g'] for k,v in r['pair']['endpoints'].items()},external_claims=r['external_claims_bound_to_prior_audits']),indent=2))
