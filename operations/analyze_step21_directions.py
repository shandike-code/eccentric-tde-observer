"""Compare audited split responses, retaining inner drift and physical variables."""
import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from operations.review_common_frequency import read,arrays,digest
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms


def analyze(root,probe,old,output):
    claims=[]
    def load(where,relative):
        inv={c['path']:c for c in read(where/'ARCHIVE_MANIFEST.json')['files']}
        c=inv[relative];p=where/relative
        assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
        claims.append(dict(path=str(p),sha256=c['sha256']))
        return arrays(p)
    mass=arrays(old)['cell_mass_g_cm2'];norm=lambda v:asdict(encoded_residual_norms(v.ravel(),mass))
    trials={};responses={};vectors={};books={}
    cases={'control':('control',4),'thermal04':('thermal',4),'thermal08':('thermal',8),'population04':('population',4),'population08':('population',8)}
    for name,(child,n) in cases.items():
        trials[name]=load(root,child+'/trial_material.npz')
        responses[name]=load(root,f'{child}/pair{n:02d}/final_response.npz')
        vectors[name]=responses[name]['residual'].reshape(128,4)
        books[name]=load(root,f'{child}/pair{n:02d}/final_energy_ledger.npz')
    for name,path in [('prior_control','control/pair04/final_response.npz'),('full_half','half/pair08/final_response.npz')]:
        vectors[name]=load(probe,path)['residual'].reshape(128,4)
    # 有限方向变化只作诊断；旧完整半幅使用它自身control，显式保留control间漂移。
    baseline=vectors['control'];changes={k:v-baseline for k,v in vectors.items() if k in cases and k!='control'}
    full_change=vectors['full_half']-vectors['prior_control']
    additive=changes['thermal08']+changes['population08']
    result={'claims':claims,'accepted_outer_steps':20,'new_material_steps':0,'strict_jacobian_established':False,'drift_is_error_bound':False,
      'norms':{k:norm(v) for k,v in vectors.items()},'direction_signals':{k:norm(v) for k,v in changes.items()},
      'map4_to_map8_drift':{k:norm(vectors[k+'08']-vectors[k+'04']) for k in ('thermal','population')},
      'between_control_drift':norm(baseline-vectors['prior_control']),
      'additive_minus_full_with_own_controls':norm(additive-full_change),'cells':{}}
    rows=[]
    for i in (1,2):
        cell={}
        for name in cases:
            t=trials[name];v=vectors[name];a=responses[name];b=books[name]
            cell[name]={'residual':v[i].tolist(),'norm':float(np.linalg.norm(v[i])),
                'delta_from_control':(v[i]-baseline[i]).tolist(),
                'trial_temperature_k':float(t['temperature_k'][i]),'response_temperature_k':float(a['temperature_k'][i]),
                'trial_hydrogen_fraction':t['hydrogen_fraction'][i].tolist(),'response_hydrogen_fraction':a['hydrogen_fraction'][i].tolist(),
                'trial_helium_fraction':t['helium_fraction'][i].tolist(),'response_helium_fraction':a['helium_fraction'][i].tolist(),
                'trial_gas_erg_g':float(np.exp(t['encoded_state'].reshape(128,4)[i,0])),
                'response_gas_erg_g':float(b['remaining'][i]),'response_ionization_erg_g':float(b['ion_new'][i])}
            rows.append([i,name,*v[i],cell[name]['norm'],cell[name]['trial_temperature_k'],cell[name]['response_temperature_k']])
        result['cells'][str(i)]=cell
    fig,axs=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    labels=['thermal','HII/HI','HeII/HeI','HeIII/HeI']
    for name in ('thermal08','population08'):
        axs[0].plot(labels,changes[name][1],'o-',label=name)
        axs[1].plot(np.linalg.norm(changes[name],axis=1),label=name)
        axs[2].plot(np.linalg.norm(vectors[name],axis=1)[:8],label=name)
    axs[0].plot(labels,full_change[1],'o--',label='full half (own control)')
    axs[0].plot(labels,additive[1],'s:',label='sum of split changes')
    axs[2].plot(np.linalg.norm(baseline,axis=1)[:8],label='control')
    axs[0].set(title='Cell 1: four-component changes',ylabel='Encoded residual change')
    axs[1].set(title='All 128 cells: direction signal',xlabel='Material cell index',ylabel='Change vector norm')
    axs[2].set(title='Fixed cells, no component omitted',xlabel='Material cell index',ylabel='Residual cell norm')
    for ax in axs:ax.legend(fontsize=7)
    fig.suptitle('Finite differences with unresolved population inner noise')
    fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['cell','case',*labels,'norm','trial_T_K','response_T_K']);w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cells','claims')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('root','probe','old','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();analyze(a.root,a.probe,a.old,a.output)
