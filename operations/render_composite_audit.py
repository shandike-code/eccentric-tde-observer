"""Render verified full-field audit with a separate acceptance-scale view."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('result',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    data=json.loads(a.result.read_text());rows=data['blocks'];x=np.array([r['block'] for r in rows])
    if list(x)!=list(range(76)):raise ValueError('incomplete block inventory')
    original=max(r['raw_linf'] for r in rows);den=data['sum_original_squared_l2']
    if original<=0 or den<=0:raise ValueError('invalid normalization')
    raw=np.array([r['raw_linf']/original for r in rows]);new=np.array([r['fresh_linf']/original for r in rows])
    delta=np.array([(r['fresh_squared_l2']-r['raw_squared_l2'])/den for r in rows])
    if not np.isclose(delta.sum(),data['full_l2_ratio']**2-1,rtol=1e-12,atol=1e-15):raise ValueError('L2 sum mismatch')
    fig,ax=plt.subplots(3,1,figsize=(11,10),sharex=True)
    for values,name in [(raw,'Original'),(new,'Hybrid full step')]:
        # 零值只在对数图留空；线性图与JSON保留全部76块及真实零值。
        positive=values>0;ax[0].plot(x[positive],values[positive],'.-',label=name)
        ax[1].plot(x,values,'.-',label=name)
    ax[0].set_yscale('log');ax[0].set_ylim(1e-280,10);ax[0].set_yticks([1,1e-60,1e-120,1e-180,1e-240])
    ax[0].set_ylabel('Block Linf / original global Linf');ax[0].set_title('Full dynamic range; zero blocks omitted only on this log axis');ax[0].legend()
    ax[1].axhline(1,color='black',linestyle='--',linewidth=.8);ax[1].set_ylabel('Same ratio, linear scale')
    ax[1].set_ylim(-.05,1.2*max(raw.max(),new.max()))
    ax[1].set_title('Acceptance scale: neighboring blocks exceed the original maximum')
    for i in (13,15,46,48):ax[1].annotate(str(i),(i,new[i]),xytext=(0,8),textcoords='offset points',ha='center')
    ax[2].bar(x,delta,color=np.where(delta>0,'#c04b32','#2171a5'));ax[2].axhline(0,color='black',linewidth=.7)
    ax[2].set_ylabel('Squared L2 change / original total');ax[2].set_xlabel('Frequency block — all 76 retained')
    for axis in ax:
        for i in (14,47):axis.axvline(i,color='gray',alpha=.3)
    fig.suptitle(f"74437 audit: L2 ratio {data['full_l2_ratio']:.6f}; Linf ratio {data['full_linf_ratio']:.6f}")
    fig.tight_layout();a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=150)


if __name__=='__main__':main()
