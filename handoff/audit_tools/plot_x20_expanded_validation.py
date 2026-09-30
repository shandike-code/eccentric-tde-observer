"""Plot audited 81679 finite-map results; no material-convergence claim."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
root=Path('handoff/evidence');a=json.loads((root/'20260930-x20-expanded-validation-review.json').read_text())
rows=[]
for i,name in enumerate(('original','full','half')):
 rows.append(dict(endpoint=name,prediction_l2_ratio=a['prediction']['l2_ratios'][i],actual_l2_ratio=a['actual']['l2_ratios'][i],actual_linf_ratio=a['actual']['linf_ratios'][i]))
with (root/'20260930-x20-expanded-validation-review.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
fig,axes=plt.subplots(1,3,figsize=(12.4,3.7),layout='constrained')
x=np.arange(3);ax=axes[0]
ax.bar(x, [r['actual_l2_ratio'] for r in rows],color=['#999999','#197d9a','#83b6bd'],label='Actual map')
ax.scatter(x,[r['prediction_l2_ratio'] for r in rows],color='#202020',marker='_',s=220,label='Prediction',zorder=3)
ax.set(xticks=x,xticklabels=['Original','Full','Half'],ylim=(0,1.16),ylabel='Defect L2 / original defect L2',title='Full step passes its 0.8 gate')
ax.hlines(.8,.65,1.35,colors='#c54b33',linestyles='--');ax.legend(fontsize=8,loc='upper right')
for i,r in enumerate(rows):ax.text(i,r['actual_l2_ratio']+(-.065 if i==1 else .025),f"{r['actual_l2_ratio']:.6f}",ha='center',fontsize=9,color='white' if i==1 else 'black')
ax=axes[1];vals=[a['actual']['l2_ratios'][3],a['actual']['linf_ratios'][3]]
ax.bar([0,1],vals,color=['#197d9a','#83b6bd']);ax.axhline(1e-6,color='#c54b33',ls='--',label='Declared gate')
ax.set(xticks=[0,1],xticklabels=['L2','Linf'],yscale='log',ylim=(1e-10,4e-6),title='Half-step affine mismatch',ylabel='Mismatch / original defect norm');ax.legend(fontsize=8)
for i,y in enumerate(vals):ax.text(i,y*1.4,f'{y:.3e}',ha='center',fontsize=9)
ax=axes[2]
for j,(key,label) in enumerate([('boundary_l1','Spectrum L1'),('boundary_bolometric','Bolometric')]):
 vals=a['actual']['boundary_ratios'][key];ax.bar(np.arange(2)+(j-.5)*.34,vals,width=.34,label=label)
ax.axhline(1,color='#c54b33',ls='--');ax.set(xticks=[0,1],xticklabels=['Full','Half'],ylim=(0,1.17),ylabel='Boundary change / original change',title='Both boundary changes decrease');ax.legend(fontsize=8)
fig.suptitle('Slurm 81679: fixed-matter radiation only; no new feedback or accepted material step',fontsize=12)
fig.savefig(root/'20260930-x20-expanded-validation-review.png',dpi=170)
