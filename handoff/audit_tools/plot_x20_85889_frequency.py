"""Visualize all stored frequency contributions; no physical recomputation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root=Path('outputs/review-20260925')
target=root/'20261006-x20-85889-frequency.png'
if target.exists():raise FileExistsError(target)
d=json.loads((root/'20261006-x20-85889-frequency-diagnostic.json').read_text())
energy=json.loads((root/'20261006-x20-85889-energy-diagnostic.json').read_text())
rows=d['comparisons']; blocks=rows['final_vs_final']['blocks']
edges=np.array([b['energy_left_ev'] for b in blocks]+[blocks[-1]['energy_right_ev']])
cells=energy['comparisons']['cross16']['final_vs_final']['cells']
mass_edges=np.array([c['mass_fraction_interval'][0] for c in cells]+[cells[-1]['mass_fraction_interval'][1]])
fig,axes=plt.subplots(2,1,figsize=(10,8),layout='constrained',sharex=True)
for label,row in rows.items():
    axes[0].stairs([b['signed_projection'] for b in row['blocks']],edges,
                   label=label.replace('_vs_',' H / ')+' A',lw=1.5)
axes[0].axhline(0,color='black',lw=.7)
axes[0].set_ylabel('Signed mass-inner-product fraction\n(sum = 1; not luminosity fraction)')
axes[0].set_title('85889 new H16 minus A16: all 76 stored frequency blocks')
axes[0].legend(fontsize=8,ncol=2)
axes[0].grid(alpha=.2)
z=np.array([b['log_contribution'] for b in blocks]).T
maximum=np.max(np.abs(z))
# 色标对称以保留正负项；展示的是已积分块贡献，不是每eV谱密度。
mesh=axes[1].pcolormesh(edges,mass_edges,z,cmap='RdBu_r',vmin=-maximum,vmax=maximum,shading='flat')
fig.colorbar(mesh,ax=axes[1],label=r'Block contribution to $g\Delta h$ (dimensionless)')
axes[1].set_title('Final / final example: all 128 cells, original mass coordinate',fontsize=11)
axes[1].set_ylabel('Mass fraction from surface')
axes[1].set_xlabel('Core frequency interval expressed as photon energy (eV)')
axes[1].set_xscale('log');axes[1].set_xlim(edges[0],edges[-1]);axes[1].set_ylim(0,1)
fig.savefig(target,dpi=170);plt.close(fig)
print(target)
