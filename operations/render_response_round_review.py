"""Render frozen first-pair evidence without changing its scientific verdict."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();d=json.loads(args.input.read_text());c=d['formal_comparison']
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    keys=['candidate_to_base_residual_l2_ratio','candidate_to_base_mass_weighted_norm_ratio','candidate_to_base_maximum_cell_norm_ratio']
    labels=['L2','Mass-weighted','Worst cell']
    axes[0].plot(range(3),[c[k] for k in keys],'o-',label='Frozen formal base')
    fresh=d['fresh_control_ratios']['final']['final']
    axes[0].plot(range(3),[fresh[k] for k in ['l2','mass_weighted','maximum_cell']],'s--',label='Fresh control final')
    axes[0].axhline(1,color='black',lw=.8);axes[0].set_xticks(range(3),labels)
    axes[0].set(ylabel='Candidate / baseline norm',title='Three contraction gates pass');axes[0].legend(fontsize=8)
    rows=d['history']['full'];axes[1].semilogy([v['iteration'] for v in rows],[v['residual'] for v in rows],'o-')
    axes[1].axhline(1e-4,color='black',lw=.8,label='Original threshold')
    axes[1].axvspan(3,4,alpha=.12,color='orange',label='Evaluated pair')
    axes[1].set(xlabel='Candidate map',ylabel='Original radiation residual',title='Both endpoints required');axes[1].legend(fontsize=8)
    values=[c['atomic_heating_volume_l1']/1e-3,c['direct_heating_volume_l1']/1e-3,c['formal_heating_volume_l1']/1e-3,c['inner_noise_to_trial_signal_l2_ratio']/.1]
    axes[2].barh(['Atomic heat','Direct heat','Formal heat','Noise / signal'],values)
    axes[2].axvline(1,color='black',lw=.8);axes[2].set(xlabel='Metric / original threshold',title='Remaining precision gates fail')
    fig.suptitle('74671: fresh direction, alpha = 1/256, pair at maps 3/4 — NOT ACCEPTED',fontsize=12)
    fig.savefig(args.output,dpi=160);plt.close(fig)


if __name__=='__main__':main()
