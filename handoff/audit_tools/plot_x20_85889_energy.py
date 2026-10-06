"""Plot the stored-array audit without running a radiation or population solver."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path('outputs/review-20260925')
source = ROOT / '20261006-x20-85889-energy-diagnostic.json'
target = ROOT / '20261006-x20-85889-energy.png'
if target.exists():
    raise FileExistsError(target)
audit = json.loads(source.read_text())
rows = audit['comparisons']['cross16']
example = rows['final_vs_final']['cells']
x = np.array([np.mean(c['mass_fraction_interval']) for c in example])
fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True, constrained_layout=True)
colors = ['#0072B2', '#E69F00', '#009E73', '#CC79A7']
for (label, row), color in zip(rows.items(), colors):
    cells = row['cells']
    axes[0].plot(x, [c['delta_log_gas'] for c in cells], color=color, lw=1.4,
                 label=label.replace('_vs_', ' H / ') + ' A')
    axes[2].plot(x, [100*c['mass_norm_squared_fraction'] for c in cells],
                 color=color, lw=1.4)
axes[0].set_ylabel(r'$\Delta\ln u$ (H minus A)')
axes[0].set_title('85889: new H16 vs new A16 — all four endpoint combinations')
axes[0].legend(fontsize=8, ncol=2, loc='lower left')
# These are actual-endpoint algebraic terms, not counterfactual responses.
axes[1].plot(x, [c['ionization_log_contribution'] for c in example],
             color='#882255', label=r'$-g\,\Delta I$, final / final')
axes[1].set_ylabel('Ionization term in log u')
axes[1].ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
axes[1].legend(fontsize=9)
axes[1].set_title(r'$\Delta\ln u = g\Delta h-g\Delta I$; heating/log-u mass-norm ratio $\simeq 1$', fontsize=11)
axes[2].set_ylabel('Cell share of full 512-vector\nmass norm squared (%)')
axes[2].set_xlabel('Mass fraction from surface (not geometric depth)')
axes[2].axvspan(.9052051159149267, 1, color='gray', alpha=.15)
axes[2].text(.035, .85, 'Cells 123–127: 26.05% combined\nRemaining cells: about 74%',
             transform=axes[2].transAxes, fontsize=10)
for ax in axes:
    ax.grid(alpha=.2)
    ax.set_xlim(0, 1)
fig.savefig(target, dpi=170)
plt.close(fig)
print(target)
