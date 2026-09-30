"""Plot only measured maps and audited small-data predictions, not accepted physics."""
import csv,json
from pathlib import Path
import matplotlib.pyplot as plt


def main():
    root=Path('handoff/evidence')
    maps=json.loads((root/'20260930-x20-long-chord-review.json').read_text())['maps']
    candidate=json.loads((root/'20260930-x20-expanded-candidate-review.json').read_text())['endpoints']
    rows=[]
    for name,row in zip(('Full','Half'),candidate):
        for key,limit in [('l2_ratio',.8 if name=='Full' else 1.),('boundary_l1_ratio',1.),('boundary_bolometric_ratio',1.)]:
            rows.append(dict(case=name,metric=key,value=float(row[key]),gate=limit,ratio_to_gate=float(row[key])/limit))
    with (root/'20260930-x20-expanded-review.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    fig,ax=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    original=5.475932014387697e-7
    ax[0].plot([16]+[16+r['iteration'] for r in maps],[1.]+[r['residual']/original for r in maps],marker='o')
    ax[0].set(xlabel='Late radiation iteration (fixed matter)',ylabel='Original-operator residual / late16',title='Four measured original maps')
    ax[0].set_xticks(range(16,21));ax[0].grid(alpha=.25)
    labels=['Full L2','Full spectral L1','Full bolometric','Half L2','Half spectral L1','Half bolometric']
    ax[1].bar(range(6),[r['ratio_to_gate'] for r in rows],color=['#376BB3']*3+['#4D9A80']*3)
    ax[1].set_xticks(range(6),labels,rotation=27,ha='right');ax[1].axhline(1,color='#AF3939',ls='--',label='Original gate')
    ax[1].set(ylabel='Predicted quantity / its original gate',ylim=(0,1.12),title='Small-data candidate; full fields pending');ax[1].legend(loc='lower right')
    fig.suptitle('Fixed x20: new direction measured, candidate still requires actual maps')
    fig.savefig(root/'20260930-x20-expanded-review.png',dpi=150);plt.close(fig)


if __name__=='__main__':main()
