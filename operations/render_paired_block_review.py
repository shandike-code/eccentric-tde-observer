"""Validate and render the four-case 74235 report without a new physics solve."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_bytes()
    summary = json.loads(source)
    rows = summary['rows']
    if [(r['label'], r['block_index']) for r in rows] != [('base',14),('base',47),('trial',14),('trial',47)]:
        raise ValueError('four-case ownership differs')
    if not summary['source_bytes_unchanged'] or summary['new_full_maps'] or summary['new_feedback_pairs']:
        raise ValueError('experiment scope differs')
    table = []
    for r in rows:
        for name in ('l2','linf'):
            observed = r['fresh_defect_'+name]/r['raw_defect_'+name]
            if not np.isfinite(observed) or not np.isclose(observed,r['fixed_scale_'+name+'_ratio'],rtol=1e-13,atol=0):
                raise ValueError('stored defect ratio is inconsistent')
        if not r['replay']['array_equal'] or r['replay']['field_relative_error'] or r['replay']['defect_relative_error']:
            raise ValueError('native map was not reproduced exactly')
        if bool(r['eligible_for_further_block_review']) != all(r['checks'].values()):
            raise ValueError('case decision differs from its gates')
        # 中文：端点被完整采用时，两次相同端点的复算并非独立的内部仿射检验。
        interior_tested = 0 < r['line_fraction'] < 1
        table.append(dict(case=f"{r['label']}/{r['block_index']}",
            l2_ratio=r['fixed_scale_l2_ratio'],linf_ratio=r['fixed_scale_linf_ratio'],
            positive_step=r['exact_nonnegative_step'],line_fraction=r['line_fraction'],
            interior_affinity_tested=interior_tested,linear_audit_passed=r['linear_audit_passed'],
            gmres_info=r['gmres_info'],wall_s=r['wall_s'],peak_rss_mib=r['peak_rss_mib'],
            time_over_one_map=r['wall_s']/r['raw_map_s'],
            boundary_ratio=(r['fresh_boundary_absolute']/r['raw_boundary_absolute']
                            if r['raw_boundary_absolute'] else None)))
    if summary['all_four_local_cases_passed'] != all(r['eligible_for_further_block_review'] for r in rows):
        raise ValueError('summary decision differs from four cases')
    args.output.mkdir(parents=True,exist_ok=False)
    with (args.output/'cases.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    (args.output/'review.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source).hexdigest(),
        'cases':table,'interpretation':'Local fixed-halo gains only; no converged linear or global atmosphere solution.'},indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    x=np.arange(4)
    axes[0].bar(x-.17,[r['l2_ratio'] for r in table],width=.34,label='L2')
    axes[0].bar(x+.17,[r['linf_ratio'] for r in table],width=.34,label='L-infinity')
    axes[0].axhline(.5,color='black',ls='--',label='Local gate')
    axes[0].set(yscale='log',ylabel='Fresh defect / original defect',title='Original operator: fixed-halo gains')
    axes[0].legend()
    axes[1].bar(x,[r['time_over_one_map'] for r in table],color='tab:gray')
    axes[1].axhline(20,color='black',ls='--',label='Cost gate')
    axes[1].set(ylabel='Wall time / one local map',ylim=(0,23),title='All four GMRES linear audits remain false')
    axes[1].legend()
    for ax in axes:ax.set_xticks(x,[r['case'] for r in table])
    fig.suptitle('74235: four local cases pass; full-frequency solution not tested')
    fig.savefig(args.output/'comparison.png',dpi=160)
    plt.close(fig)
    print(json.dumps(table,indent=2))


if __name__=='__main__':main()
