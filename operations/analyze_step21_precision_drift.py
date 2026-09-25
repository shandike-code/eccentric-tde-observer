"""Separate original-denominator noise from matched-control directional variability."""
import argparse
from dataclasses import asdict
import csv,json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from operations.review_common_frequency import read,arrays,digest
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms


def analyze(root,prior,reference,old,output):
    claims=[]
    def load(where,relative):
        inv={c['path']:c for c in read(where/'ARCHIVE_MANIFEST.json')['files']};p=where/relative;c=inv[relative]
        assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256'];claims.append(dict(path=str(p),sha256=c['sha256']))
        return arrays(p)
    mass=arrays(old)['cell_mass_g_cm2'];norm=lambda v:asdict(encoded_residual_norms(v.ravel(),mass))
    fixed=np.load(reference/'base_residual.npy',allow_pickle=False)
    vectors={};trials={}
    for case in ('control','thermal','population'):
        trials[case]=load(root,case+'/trial_material.npz')
        vectors[case]={}
        for stage,where,n in (('prior',prior,4 if case=='control' else 8),('new04',root,4),('new08',root,8)):
            vectors[case][stage]={e:load(where,f'{case}/pair{n:02d}/{e}_response.npz')['residual'] for e in ('previous','final')}
    stages=('prior','new04','new08');record={'claims':claims,'accepted_outer_steps':20,'new_material_steps':0,'strict_error_bound':False,'jacobian_established':False,'stages':{},'drifts':{}}
    rows=[];fig,axs=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    for stage in stages:
        control=vectors['control'][stage];entry={'control_norms':norm(control['final']),'control_minus_r20':norm(control['final']-fixed),'cases':{}}
        for case in ('thermal','population'):
            v=vectors[case][stage];signal=v['final']-control['final'];original_signal=v['final']-fixed
            noise=v['final']-v['previous'];base_noise=control['final']-control['previous']
            sl2=norm(signal)['l2'];ol2=norm(original_signal)['l2'];assert sl2>0 and ol2>0
            # 实测端点跨度，不是随机噪声估计或严格误差界；三角和保留两端都在移动的事实。
            x={'candidate_norms':norm(v['final']),'matched_signal':norm(signal),'original_signal':norm(original_signal),'candidate_adjacent':norm(noise),'control_adjacent':norm(base_noise),'matched_adjacent':norm(noise-base_noise),
               'matched_adjacent_over_signal':norm(noise-base_noise)['l2']/sl2,
               'adjacent_cosine':float(np.dot(noise,base_noise)/(np.linalg.norm(noise)*np.linalg.norm(base_noise))),
               'original_noise_ratio':norm(noise)['l2']/ol2,'candidate_adjacent_over_matched_signal':norm(noise)['l2']/sl2,
               'sum_adjacent_over_matched_signal':(norm(noise)['l2']+norm(base_noise)['l2'])/sl2,
               'four_endpoint_signal_norms':{a+'_vs_'+b:norm(va-vb) for a,va in v.items() for b,vb in control.items()}}
            entry['cases'][case]=x
            rows.append([stage,case,sl2,ol2,norm(noise)['l2'],norm(base_noise)['l2'],x['original_noise_ratio'],x['sum_adjacent_over_matched_signal'],x['matched_adjacent_over_signal'],x['adjacent_cosine']])
        record['stages'][stage]=entry
    for case in ('control','thermal','population'):
        v=vectors[case];record['drifts'][case]={a+'_to_'+b:norm(v[b]['final']-v[a]['final']) for a,b in zip(stages,stages[1:])}
    record['matched_direction_drift']={case:{a+'_to_'+b:norm((vectors[case][b]['final']-vectors['control'][b]['final'])-(vectors[case][a]['final']-vectors['control'][a]['final'])) for a,b in zip(stages,stages[1:])} for case in ('thermal','population')}
    # 只筛查有限线性预测，不据此写物质候选；小预测裕量不能替代真实反馈。
    den=np.array(list(norm(fixed).values()));screen=[]
    for ae in np.arange(.25,2.01,.25):
        for ap in np.arange(.5,12.01,.5):
            ratios=[]
            for stage in ('new04','new08'):
                for e in ('previous','final'):
                    c=vectors['control'][stage][e]
                    predicted=c+ae*(vectors['thermal'][stage][e]-c)+ap*(vectors['population'][stage][e]-c)
                    ratios.append(np.array(list(norm(predicted).values()))/den)
            worst=np.max(ratios,axis=0)
            screen.append({'thermal_weight':float(ae),'population_weight':float(ap),'worst_original_ratios':worst.tolist(),'score':float(worst.max())})
    record['finite_linear_screen']={'definition':'C + aE*(thermal-C) + aP*(population-C), both endpoints of new04/new08; original r20 denominator',
        'thermal_grid':[.25,2.,.25],'population_grid':[.5,12.,.5],'cases':len(screen),'best':min(screen,key=lambda x:x['score']),
        'actual_candidate_written':False,'physical_prediction_validated':False,'selection_is_a_science_acceptance':False}
    for case in ('thermal','population'):
        axs[0].plot(stages,[record['stages'][s]['cases'][case]['matched_signal']['l2'] for s in stages],'o-',label=case+' matched signal')
        axs[1].plot(stages,[record['stages'][s]['cases'][case]['original_noise_ratio'] for s in stages],'o-',label=case+' original')
        axs[1].plot(stages,[record['stages'][s]['cases'][case]['sum_adjacent_over_matched_signal'] for s in stages],'s--',label=case+' sum of norms / matched')
        axs[1].plot(stages,[record['stages'][s]['cases'][case]['matched_adjacent_over_signal'] for s in stages],'^:',label=case+' difference of drifts / matched')
        for i in (1,2):
            axs[2].plot(stages,[np.linalg.norm(vectors[case][s]['final'].reshape(128,4)[i]) for s in stages],'o-',label=case+f' cell{i}')
    axs[0].plot(stages,[norm(vectors['control'][s]['final']-fixed)['l2'] for s in stages],'o:',label='control drift from r20')
    axs[1].axhline(.1,color='black',lw=1,label='0.1 reference (not new gate)')
    axs[0].set(title='Finite signal versus baseline drift',ylabel='Encoded vector L2')
    axs[1].set(title='Two distinct denominators',ylabel='Observed ratio')
    axs[2].set(title='Fixed material cells',ylabel='Four-component residual norm')
    for ax in axs:ax.legend(fontsize=7)
    fig.suptitle('Fixed-trial precision; observed changes are not error bounds')
    fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    output.with_suffix('.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['stage','case','matched_signal_l2','original_signal_l2','candidate_adjacent_l2','control_adjacent_l2','original_noise_ratio','both_adjacent_over_matched','matched_adjacent_over_signal','adjacent_cosine']);w.writerows(rows)
    print(json.dumps({'rows':rows,'matched_direction_drift':record['matched_direction_drift'],'drifts':record['drifts']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('root','prior','reference','old','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();analyze(a.root,a.prior,a.reference,a.old,a.output)
