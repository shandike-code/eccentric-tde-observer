import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('handoff/evidence');x=json.loads((p/'20261001-x20-82441-bounded-gram-analysis.json').read_text())
fig,ax=plt.subplots(1,2,figsize=(12,4),layout='constrained')
values=[1,x['global_minimum_l2_ratio'],x['blockwise_feasible_anchor_retained_l2_ratio'],x['blockwise_selected_l2_ratio']]
labels=['Original','Uniform optimum','Blockwise feasible','Blockwise x 0.9']
b=ax[0].bar(labels,values,color=['gray','#44849c','#99bdc8','#c78347']);ax[0].bar_label(b,labels=[f'{v:.6f}' for v in values],padding=3);ax[0].set(ylim=(0,1.15),ylabel='Predicted radiation-defect L2 / original',title='Stored Gram prediction only; field gates pending');ax[0].tick_params(axis='x',labelrotation=15)
weights=[]
for r in x['blocks']:
 c=r['selected_coefficients_float'];weights.append(abs(1-sum(c))+sum(map(abs,c)))
ax[1].plot(range(76),weights,'.-',label='Selected weight L1');ax[1].axhline(17,color='red',ls='--',label='Cap');u=x['unresolved_blocks'];ax[1].scatter(u,[weights[i] for i in u],marker='x',s=65,color='red',label='Unresolved: anchor retained');ax[1].set(xlabel='Natural frequency block',ylabel='Sum of absolute affine weights',ylim=(0,19));ax[1].legend(fontsize=8)
fig.savefig(p/'20261001-x20-82441-block-gram.png',dpi=160)
with (p/'20261001-x20-82441-block-gram.csv').open('w') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['block','status','c1','c2','c3','weight_l1','anchor_squared','selected_squared'])
 for r,v in zip(x['blocks'],weights):w.writerow([r['block'],r['status'],*r['selected_coefficients_float'],v,r['anchor_squared']['decimal'],r['selected_squared']['decimal']])
