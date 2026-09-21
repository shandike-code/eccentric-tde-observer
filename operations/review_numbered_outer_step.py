"""Use the frozen snapshot audit with the actual protocol's outer-step index."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from operations.review_outer_step_snapshot import review, read
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--received',type=Path,required=True);p.add_argument('--source-run',type=Path,required=True)
    p.add_argument('--candidate',default='full');p.add_argument('--round',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=review(a.received,a.source_run,a.candidate,a.round)
    proto=read(a.received/a.candidate/f'feedback-round{a.round}'/'feedback_protocol.json')
    d['outer_iteration']=proto['outer_iteration']
    d['formal_denominator']=proto['sources']['base_residual']
    a.output.with_suffix('.json').write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
    c=d['formal_comparison'];fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    fields=['candidate_to_base_residual_l2_ratio','candidate_to_base_mass_weighted_norm_ratio','candidate_to_base_maximum_cell_norm_ratio']
    axes[0].plot(['L2','Mass','Worst cell'],[c[k] for k in fields],'o-',label='Frozen step base')
    axes[0].plot(['L2','Mass','Worst cell'],[d['fresh_control_ratios']['final']['final'][k] for k in ['l2','mass_weighted','maximum_cell']],'s--',label='Fresh control final')
    axes[0].axhline(1,color='black',lw=.8);axes[0].set(title='Residual norm / baseline');axes[0].legend(fontsize=8)
    axes[1].semilogy([r['iteration'] for r in d['history']],[r['residual'] for r in d['history']],'o-')
    axes[1].axhline(1e-4,color='black',lw=.8)
    axes[1].axvspan(d['endpoints']['previous']['iteration'],d['endpoints']['final']['iteration'],alpha=.15)
    axes[1].set(xlabel='Candidate map',ylabel='Original radiation residual',title='Evaluated pair shaded')
    axes[2].barh(['Atomic heat','Direct heat','Formal heat','Noise / signal'],[c[k]/t for k,t in [('atomic_heating_volume_l1',.001),('direct_heating_volume_l1',.001),('formal_heating_volume_l1',.001),('inner_noise_to_trial_signal_l2_ratio',.1)]])
    axes[2].axvline(1,color='black',lw=.8);axes[2].set(xlabel='Metric / original threshold',title='Feedback precision')
    fig.suptitle(f'Outer step {d["outer_iteration"]["index"]}, {a.candidate} pair {a.round}: '+('ACCEPTED finite step' if d['accepted'] else 'NOT ACCEPTED'))
    fig.savefig(a.output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps({k:d[k] for k in ('verified_files','accepted','base_norms','candidate_norms','gas_domain','resources','outer_iteration')}))


if __name__=='__main__':main()
