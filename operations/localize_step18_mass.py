"""Reproduce the signed mass-norm decomposition from independently audited NPZs."""
import argparse
import json
from pathlib import Path
import numpy as np
from operations.audit_outer_contraction import decomposition


def main():
    p=argparse.ArgumentParser()
    for k in ('received','baseline','physical-old','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();m=np.load(a.physical_old,allow_pickle=False)['cell_mass_g_cm2'];records={}
    b=np.load(a.baseline/'final_response.npz',allow_pickle=False)['residual']
    for case in ('pair04','pair08'):
        for e in ('previous','final'):
            v=np.load(a.received/case/(e+'_response.npz'),allow_pickle=False)['residual'];d=decomposition(b,v,m)
            order=np.argsort(d['cell_mass_excess'])[::-1]
            d['top_positive_cells']=[dict(half_cell_index=int(i),mass_norm_squared_excess=d['cell_mass_excess'][i],cell_mass_fraction=float(m[i]/m.sum())) for i in order[:12]]
            records[case+'_'+e]=d
    result=dict(definition='sum_i (mass_i/sum_mass) * (sum_k rcandidate_ik^2 - sum_k rbase_ik^2)',component_order=['log_thermal_energy','log_HII_HI','log_HeII_HeI','log_HeIII_HeI'],baseline='76260 confirm2 final',records=records,note='Signed squared encoded residual contributions, not physical energy fractions; cells use half material grid indexing.')
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
