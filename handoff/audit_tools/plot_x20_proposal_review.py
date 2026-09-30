"""Analytic one-dimensional prediction minimum and boundary nonincrease failures."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('handoff/evidence');r=json.loads((root/'20260930-x20-82083-review.json').read_text());g=np.asarray(r['gram']);xs=np.linspace(-.035,.015,301)
ys=np.sqrt((g[0,0]+2*xs*g[0,1]+xs*xs*g[1,1])/g[0,0]);fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
ax[0].plot(xs,ys,label='Affine-predicted defect');ax[0].axhline(.8,color='#c4543b',ls='--',label='Required <= 0.8');ax[0].axhline(1,color='gray',ls=':')
z=r['line_minimum'];ax[0].plot(z['unconstrained_alpha'],z['unconstrained_minimum_l2_ratio'],'o',color='black',label='Analytic minimum (all real alpha)')
ax[0].plot(r['alpha'],r['l2_ratio'],'x',ms=8,color='#c4543b',label='Selected coefficient')
ax[0].set(xlabel='Coefficient alpha (view near minimum)',ylabel='Predicted L2 defect / original A16 defect',ylim=(.65,1.6),title='The full affine line cannot reach the 20% gain gate');ax[0].legend(fontsize=8)
ratios=[r['predicted_boundary'][k]/r['original_boundary'][k] for k in ('boundary_l1','boundary_bolometric')]
ax[1].bar(['Boundary L1','Bolometric'],ratios,color=['#408aa2','#cb7748']);ax[1].axhline(1,color='#c4543b',ls='--');ax[1].set(yscale='log',ylim=(.7,45),ylabel='Predicted change / original change',title='Both remain below 0.001, but fail nonincrease')
for i,v in enumerate(ratios):ax[1].text(i,v*1.1,f'{v:.3f}x',ha='center')
fig.suptitle('82083: reject this affine direction; no true map or material step')
fig.savefig(root/'20260930-x20-82083-review.png',dpi=160)
with (root/'20260930-x20-82083-review.csv').open('w') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['alpha','affine_predicted_l2_ratio']);w.writerows(zip(xs,ys))
