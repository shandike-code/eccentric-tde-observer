"""Plot audited 82518 vector windows; ratios are diagnostic, not luminosities."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    root = Path('handoff/evidence')
    data = json.loads((root/'20261001-x20-82518-final-review.json').read_text())
    assert data['completed_experiment'] and data['map_counts'] == dict(accelerated=16, historical=16)
    comparisons = {
        'A16 - A8': data['pairs']['accelerated16']['eight_map_window'],
        'H16 - H8': data['pairs']['historical16']['eight_map_window'],
        'H16 - A16': data['cross_history']['16']['residual_comparison'],
    }
    rows = []
    for label, item in comparisons.items():
        for denominator, values, limit in [
            ('r20', item['frozen_r20']['vector_difference_over_frozen_r20_norms'], .001),
            ('signal', item['vector_difference_over_frozen_80195_signal'], .1),
        ]:
            vectors = np.asarray(list(values.values()))
            assert vectors.shape == (4, 3) and np.isfinite(vectors).all() and (vectors >= 0).all()
            for norm, value in zip(['L2', 'Mass', 'Max-cell'], vectors.max(axis=0)):
                rows.append([label, denominator, norm, float(value), limit, float(value/limit)])
    with (root/'20261001-x20-82518-final-review.csv').open('w') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['comparison', 'denominator', 'norm', 'maximum_four_endpoint_ratio', 'limit', 'ratio_to_limit'])
        writer.writerows(rows)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), layout='constrained', sharey=True)
    for ax, norm in zip(axes, ['L2', 'Mass', 'Max-cell']):
        for offset, denominator in [(-.18, 'r20'), (.18, 'signal')]:
            values = [r[-1] for r in rows if r[1] == denominator and r[2] == norm]
            assert min(values) > 0, 'zero value needs explicit rendering, not a log floor'
            bars = ax.bar(np.arange(3)+offset, values, .36, label=denominator)
            ax.bar_label(bars, labels=[f'{v:.3g}' for v in values], fontsize=8, padding=3)
        ax.axhline(1, color='red', linestyle='--')
        ax.set(yscale='log', xticks=range(3), xticklabels=list(comparisons), title=norm)
        ax.tick_params(axis='x', labelrotation=15)
    axes[0].set_ylabel('Vector-difference ratio / declared tolerance')
    axes[0].legend(title='Fixed denominator')
    fig.suptitle('82518 complete: finite-window and cross-seed response checks')
    fig.savefig(root/'20261001-x20-82518-final-review.png', dpi=160)
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
