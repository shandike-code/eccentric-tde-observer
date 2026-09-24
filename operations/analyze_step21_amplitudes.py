"""Compare two audited finite amplitudes without claiming derivative convergence."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from operations.review_common_frequency import read, arrays, digest


def analyze(full, probe, output):
    claims = []
    vectors = {}
    for label, root, relative in (
        ('control', probe, 'control/pair04/final_response.npz'),
        ('half', probe, 'half/pair08/final_response.npz'),
        ('full', full, 'pair08/final_response.npz'),
    ):
        inventory = {c['path']: c for c in read(root/'ARCHIVE_MANIFEST.json')['files']}
        p = root/relative
        c = inventory[relative]
        assert p.stat().st_size == c['size_bytes'] and digest(p) == c['sha256']
        claims.append(dict(path=str(p), sha256=c['sha256']))
        v = arrays(p)['residual'].reshape(128, 4)
        assert np.isfinite(v).all()
        vectors[label] = v
    # 两种幅度共用本批的新control作比较；这仍是有限差商，不是严格Jacobian。
    alphas = {'control': 0., 'half': 1/256, 'full': 1/128}
    labels = ('ln thermal energy', 'ln HII/HI', 'ln HeII/HeI', 'ln HeIII/HeI')
    record = dict(claims=claims, component_order=labels, cells={},
                  strict_derivative_convergence_established=False,
                  inner_drift_is_error_bound=False, accepted_outer_steps=20)
    rows = []
    for i in (1, 2):
        cell = {}
        for name, v in vectors.items():
            delta = v[i]-vectors['control'][i]
            cell[name] = dict(alpha=alphas[name], residual=v[i].tolist(),
                norm=float(np.linalg.norm(v[i])), delta_from_control=delta.tolist(),
                squared_norm_change_components=(v[i]**2-vectors['control'][i]**2).tolist())
            if alphas[name]:
                cell[name]['finite_quotient'] = (delta/alphas[name]).tolist()
            rows.append([i, name, alphas[name], *v[i], np.linalg.norm(v[i])])
        record['cells'][str(i)] = cell
    record['global_maximum'] = {k:dict(index=int(np.linalg.norm(v, axis=1).argmax()),
        norm=float(np.linalg.norm(v, axis=1).max())) for k,v in vectors.items()}
    fig, axs = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for j, name in enumerate(labels):
        axs[0].plot(list(alphas.values()), [vectors[k][1,j]-vectors['control'][1,j] for k in alphas], 'o-', label=name)
    axs[0].set(xlabel='Finite amplitude', ylabel='Cell 1 residual change', title='Same cell, same fresh control')
    axs[0].legend(fontsize=8)
    for i in (1, 2):
        axs[1].plot(list(alphas.values()), [np.linalg.norm(vectors[k][i]) for k in alphas], 'o-', label=f'Cell {i}')
    axs[1].axhline(record['global_maximum']['control']['norm'], color='black', ls='--', label='Control maximum')
    axs[1].set(xlabel='Finite amplitude', ylabel='Four-component residual norm')
    axs[1].legend(fontsize=8)
    fig.suptitle('Finite-amplitude evidence; no derivative-convergence claim')
    fig.savefig(output.with_suffix('.png'), dpi=160)
    plt.close(fig)
    output.with_suffix('.json').write_text(json.dumps(record, indent=2, allow_nan=False)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.writer(f, lineterminator='\n');w.writerow(['cell', 'case', 'alpha', *labels, 'cell_norm']);w.writerows(rows)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for k in ('full','probe','output'):p.add_argument('--'+k, type=Path, required=True)
    a=p.parse_args();analyze(a.full,a.probe,a.output)
