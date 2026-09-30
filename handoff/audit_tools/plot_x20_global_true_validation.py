"""Plot independently audited predicted and actual defects; no field recomputation."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path('handoff/evidence')


def main():
    rows = []
    for job, prediction_job, prefix in [(82503, 82486, 'boundary'), (82515, 82512, 'global')]:
        actual_prefix = 'boundary' if job == 82503 else 'global-boundary'
        actual = json.loads((ROOT/f'20261001-x20-{actual_prefix}-validation-{job}-review.json').read_text())['actual']
        prediction = json.loads((ROOT/f'20261001-x20-{prefix}-prediction-{prediction_job}-review.json').read_text())
        for i, amplitude in enumerate(('full', 'half'), 1):
            rows.append(dict(job=job, amplitude=amplitude, predicted_l2=prediction['l2_ratios'][i],
                             actual_l2=actual['l2_ratios'][i], prediction_error_l2=actual['prediction_error_l2_ratios'][i]))
    assert all(np.isfinite([r[k] for k in ('predicted_l2','actual_l2','prediction_error_l2')]).all() for r in rows)
    stem = ROOT/'20261001-x20-global-true-validation-comparison'
    with stem.with_suffix('.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
    x = np.arange(4)
    labels = [f"{r['job']}\n{r['amplitude']}" for r in rows]
    axes[0].bar(x-.18, [r['predicted_l2'] for r in rows], .36, label='Predicted defect', color='#6baed6')
    axes[0].bar(x+.18, [r['actual_l2'] for r in rows], .36, label='Actual defect', color='#08519c')
    axes[0].axhline(1, color='gray', linestyle=':', label='Original defect')
    axes[0].set_ylabel('L2 / original A16 defect L2')
    axes[0].set_title('Prediction and true-map result')
    axes[0].legend(fontsize=9)
    values = [r['prediction_error_l2'] for r in rows]
    assert min(values) > 0
    axes[1].scatter(x, values, s=65, color=['#d95f02']*2+['#1b9e77']*2)
    axes[1].set_yscale('log')
    axes[1].axhline(1e-6, color='black', linestyle='--', label='Prediction error gate')
    axes[1].set_ylabel('||true output - predicted output|| / original defect L2')
    axes[1].set_title('Prediction error (log scale)')
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.set_xticks(x, labels)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('82503: block-dependent coefficients; 82515: one global triple\nDifferent candidates, same frozen A16 normalization; no feedback measured', fontsize=11)
    fig.savefig(stem.with_suffix('.png'), dpi=170)
    plt.close(fig)


if __name__ == '__main__': main()
