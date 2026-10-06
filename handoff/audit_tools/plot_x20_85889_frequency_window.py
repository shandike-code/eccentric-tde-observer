"""All signed blocks and all endpoint combinations of the finite stored window."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root=Path('outputs/review-20260925')
target=root/'20261006-x20-85889-frequency-window.png'
if target.exists():raise FileExistsError(target)
d=json.loads((root/'20261006-x20-85889-frequency-window.json').read_text())
edges=[v['left_ev'] for v in d['intervals']]+[d['intervals'][-1]['right_ev']]
fig,ax=plt.subplots(2,2,figsize=(13,8),layout='constrained',sharex=True)
for a,group,title in zip(ax.flat[:2],['accelerated_window','historical_window'],['A16 - A8: 4 combinations','H16 - H8: 4 combinations']):
    for label,r in d['comparisons'][group].items():
        a.stairs(r['signed_projection'],edges,label=label,lw=1.1)
    a.set_title(title);a.set_ylabel('Signed projection of log-heating blocks');a.legend(fontsize=7)
for group,color in [('cross8','tab:blue'),('cross16','tab:orange')]:
    for i,r in enumerate(d['comparisons'][group].values()):
        ax[1,0].stairs(r['signed_projection'],edges,color=color,alpha=.6,label=group+' (4)' if i==0 else None)
ax[1,0].set_title('Cross-history difference: 8 and 16');ax[1,0].legend()
ax[1,0].set_ylabel('Signed projection of log-heating blocks')
for r in d['evolution'].values():
    ax[1,1].stairs(r['signed_projection'],edges,color='tab:purple',alpha=.25,lw=.9)
ax[1,1].set_title('Change in cross-history heating: all 16 quartets')
ax[1,1].set_ylabel('Signed projection of energy-change blocks')
for a in ax.flat:
    a.axhline(0,color='black',lw=.6);a.set_xscale('log');a.set_xlim(edges[0],edges[-1]);a.grid(alpha=.2)
for a in ax[1]:a.set_xlabel('Stored core interval, photon energy (eV)')
fig.suptitle('85889 stored finite changes: all 76 blocks; signed fractions include cancellation\nNot spectral density, luminosity fractions, or a convergence/error bound',fontsize=12)
fig.savefig(target,dpi=170);plt.close(fig)
print(target)
