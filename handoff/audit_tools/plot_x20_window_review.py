"""Plot distinct affine lower bounds and independently checked witness ratios."""
import json,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('handoff/evidence')
a=json.loads((root/'20260930-x20-82166-review.json').read_text())
w=json.loads((root/'20260930-x20-window-candidate-review.json').read_text())
f=json.loads((root/'20260930-x20-window-feasibility-review.json').read_text())
rows=[('One direction: global minimum',.8980763681327247),('Three directions: unrestricted minimum',a['minimum']['minimum_l2_ratio']),('Cap + relaxed boundary: lower bound',float(f['trace'][-1]['verified_dual_squared_lower'])**.5),('Interior full witness (prediction)',float(w['endpoints'][0]['l2_ratio']))]
fig,ax=plt.subplots(1,2,figsize=(13,5),layout='constrained')
ax[0].barh([r[0] for r in rows],[r[1] for r in rows],color=['#a44','#888','#4387a1','#40834d'])
ax[0].axvline(.8,c='red',ls='--',label='Full benefit gate 0.8');ax[0].set_xlim(0,1);ax[0].invert_yaxis();ax[0].legend(loc='lower right');ax[0].set_xlabel('Predicted L2 defect / original A16 defect')
for i,(_,v) in enumerate(rows):ax[0].text(v+.01,i,f'{v:.4f}',va='center')
ax[0].set_title('Different domains: bounds are not candidate acceptances')
for i,key in enumerate(('boundary_l1_ratio','boundary_bolometric_ratio')):
 vals=[float(r[key]) for r in w['endpoints']];ax[1].bar([i-.18,i+.18],vals,width=.32,color=['#40834d','#64a8bc'])
 for x,y in zip([i-.18,i+.18],vals):ax[1].text(x,y+.025,f'{y:.3f}',ha='center')
ax[1].axhline(1,c='red',ls='--');ax[1].set_xticks([0,1],['Boundary L1','Bolometric']);ax[1].set_ylim(0,1.18);ax[1].set_ylabel('Candidate change / original change');ax[1].set_title('Full (green) / half (blue): boundary witness')
fig.suptitle('82166: bounded spectral witness found; full-field and true-map checks remain')
fig.savefig(root/'20260930-x20-window-review.png',dpi=140)
with (root/'20260930-x20-window-review.csv').open('w') as f:
 wr=csv.writer(f);wr.writerow(['quantity','ratio']);wr.writerows(rows)
