"""Independent source, thermal-proxy and full-slab reduction for the one-candidate probe."""
import argparse
import json
import math
from pathlib import Path
import tarfile
import numpy as np
from handoff.audit_tools.review_step21_wide_plane import read_archive,digest,totals,six_cut,close


def review(archive,receipt,source,physical_old,received,output):
    claim=json.loads(receipt.read_text());assert digest(archive)==claim['sha256'] and archive.stat().st_size==claim['size_bytes']
    data=read_archive(archive);received.mkdir(exist_ok=False)
    with tarfile.open(archive) as t:
        for n in data:(received/n).write_bytes(t.extractfile(n).read())
    d=data['declaration.json'];pred=data['prediction.json'];status=data['status.json']
    assert status['status']=='complete_requires_review'
    assert status['accepted_outer_steps']==20 and status['new_maps']==status['new_material_steps']==0
    assert not status['candidate_written'] and not d['automatic_promotion']
    assert d['candidate_budget']==d['field_pass_budget']==1
    assert d['candidate_write_budget']==d['map_budget']==d['feedback_budget']==0
    assert d['source']=='outputs/hpc/step21-wide-plane-validation-20260925'
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    audit=json.loads(Path('handoff/evidence/20260925-wide-validation-complete-review.json').read_text())
    assert audit['final_summary_present'] and audit['feedback_rounds']==[3,11]
    prior=archive.parent/Path(audit['archive']['path']).name
    assert digest(prior)==audit['archive']['sha256']
    with tarfile.open(prior) as t:inv={x['path']:x for x in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    def checked(name):
        p=source/name;c=inv[name];assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256'];return p
    def read(name):return json.loads(checked(name).read_text())
    def arrays(name):
        with np.load(checked(name),allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
    st=read('control/state.json');rows=st['history']
    assert st['active_map'] is None and [r['iteration'] for r in rows]==list(range(1,12))
    assert all(a['output_sha256']==b['input_sha256'] for a,b in zip(rows,rows[1:]))
    actual={}
    for n in (3,11):
        ret=read(f'control/endpoints-map{n:02d}/manifest.json');assert ret['history_rows']==rows[n-2:n]
        for key,i,which in [('previous',n-2,'input'),('final',n-1,'input'),('mapped_final',n-1,'output')]:
            c=ret['endpoints'][key];assert c['sha256']==rows[i][which+'_sha256'];actual[i if which=='input' else i+1]=c
    assert d['basis']==[actual[i] for i in (1,9,9,2,10,10)]
    close(d['latest_actual_residual'],rows[-1]['residual'])
    claims={(c['path'],c['size_bytes'],c['sha256']) for c in d['claims']}
    assert all((c['path'],c['size_bytes'],c['sha256']) in claims for c in d['basis'])
    p=read('control/pair11/feedback_protocol.json')
    assert digest(physical_old)==p['sources']['physical_old_time_level']['sha256']
    with np.load(physical_old,allow_pickle=False) as z:mass=z['cell_mass_g_cm2'].copy()
    trial=arrays('control/trial_material.npz');q=[];emitted=[]
    for n in (3,11):
        for e in ('previous','final'):
            b=arrays(f'control/pair{n:02d}/{e}_energy_ledger.npz');f=arrays(f'control/pair{n:02d}/{e}_feedback.npz')
            assert np.array_equal(b['q'],f['half_atomic_rate_heating_erg_s_cm3'])
            q.append(b['q']);emitted.append(f['emitted_power_erg_s_cm3']);u=b['remaining']
    assert all(np.array_equal(emitted[0],x) for x in emitted) and np.all(u>0) and np.all(mass>0)
    scale=float(trial['step_duration_s'])/trial['density_g_cm3']/u
    a=(q[1]-q[0])*scale;b=(q[3]-q[2])*scale;direction=a-b
    dot=lambda x,y:math.fsum(float(m)*float(v)*float(w) for m,v,w in zip(mass,x,y))/math.fsum(mass)
    alpha=-dot(b,direction)/dot(direction,direction)
    ratio=math.sqrt(dot(b+alpha*direction,b+alpha*direction)/dot(b,b))
    close(alpha,d['proxy']['alpha']);close(alpha,pred['proxy']['alpha']);close(ratio,pred['proxy']['proxy_ratio'])
    close(d['uv'],[0.,alpha]);field=pred['field'];close(field['uv'],d['uv'])
    glob,l1,bol,nq,np_=totals(field['slabs'])
    close(glob,field['predicted_global_residual']);close(glob/rows[-1]['residual'],field['predicted_ratio'])
    close(l1,field['predicted_boundary_l1']);close(bol,field['predicted_boundary_bolometric'])
    coefficient=np.array([alpha,0.,1-alpha]);close(field['coefficients'],coefficient)
    gates={'positive':nq==np_==0,'coefficient_l1':sum(abs(coefficient))<192,
        'coefficient_sum':abs(sum(coefficient)-1)<1e-12,'strict_inner':glob<1e-4,
        'maximum_improves':glob/rows[-1]['residual']<.99,'boundary_l1':l1<1e-3,'boundary_bolometric':bol<1e-3}
    assert field['gates']==gates
    for c in field['cuts']:six_cut(c,d['uv'])
    gates['heating_proxy_cost_pass']=0<=ratio<.8
    gates={k:bool(v) for k,v in gates.items()}
    assert gates==pred['gates'] and all(gates.values())==pred['eligible_for_independent_review']
    assert pred['peak_rss_bytes']<6*1024**3
    assert not any(pred[k] for k in ('actual_map_performed','actual_candidate_heating_computed','accepted_material_step','old_l2_cost_gate_reclassified'))
    report={'archive':claim,'verified_files':len(data),'verified_code_claims':len(d['code']),
        'alpha':alpha,'proxy_ratio':ratio,'predicted_radiation_ratio':glob/rows[-1]['residual'],
        'predicted_global_residual':glob,'boundary_l1':l1,'boundary_bolometric':bol,
        'negative_q':nq,'negative_p':np_,'gates':gates,'eligible_for_independent_review':all(gates.values()),
        'peak_rss_bytes':pred['peak_rss_bytes'],'accepted_outer_steps':20,'new_material_steps':0,
        'actual_candidate_heating_computed':False,'full_fields_recomputed_on_mac':False}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    axs[0].bar(['thermal proxy','radiation'],[ratio,glob/rows[-1]['residual']]);axs[0].set(ylabel='Predicted residual ratio')
    s=field['slabs'];axs[1].plot([r['start'] for r in s],[r['negative_q']+r['negative_p'] for r in s]);axs[1].set(xlabel='Frequency slab start',ylabel='Negative intensity entries')
    fig.suptitle('One heating-projected candidate: prediction only');fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','receipt','source','physical-old','received','output'):p.add_argument('--'+n,type=Path,required=True)
    print(json.dumps(review(**vars(p.parse_args())),indent=2))
