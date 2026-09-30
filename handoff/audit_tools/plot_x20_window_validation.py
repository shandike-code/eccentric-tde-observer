"""Plot independently reduced 82214 diagnostics, not a physical spectrum."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
p=Path('handoff/evidence');d=json.loads((p/'20260930-x20-window-validation-review.json').read_text())['actual']
fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
x=np.arange(2);labels=['Full','Half']
ax[0].bar(x-.16,d['l2_ratios'][1:3],.32,label='L2 defect / original')
ax[0].bar(x+.16,d['linf_ratios'][1:3],.32,label='Linf defect / original')
ax[0].axhline(1,c='grey',ls=':');ax[0].set(xticks=x,xticklabels=labels,ylim=(0,1.1),title='True maps: defect reduced')
ax[0].legend(fontsize=8)
for k,label in [('prediction_error_l2_ratios','L2 prediction error'),('prediction_error_linf_ratios','Linf prediction error')]:ax[1].plot(x,d[k][1:3],'o-',label=label)
ax[1].axhline(1e-6,c='red',ls='--',label='Acceptance limit')
ax[1].set(yscale='log',xticks=x,xticklabels=labels,ylim=(1e-9,3e-6),title='Prediction error / original defect')
ax[1].legend(fontsize=8)
fig.suptitle('82214: fixed-matter radiation validation; no feedback acceptance')
fig.savefig(p/'20260930-x20-window-validation-review.png',dpi=160)
with (p/'20260930-x20-window-validation-review.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['case','defect_l2_ratio','defect_linf_ratio','prediction_l2_ratio','prediction_linf_ratio'])
    for i,n in enumerate(labels,1):w.writerow([n,*[d[k][i] for k in ['l2_ratios','linf_ratios','prediction_error_l2_ratios','prediction_error_linf_ratios']]])
