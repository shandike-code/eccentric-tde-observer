"""Independent reductions and six-state lineage audit of the bounded wide scan."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_positive_plane import read_archive,digest,cut_key
from operations.scan_step21_positive_plane import solve_plane


def close(a,b):
    np.testing.assert_allclose(a,b,rtol=2e-11,atol=0)


def ratio(a,b):
    assert b>=0
    if b==0:
        assert a==0;return 0.
    return a/b


def six_cut(c,uv):
    assert c['label'] in ('q','p') and len(c['inputs_hex'])==6
    values=[float.fromhex(v) for v in c['inputs_hex']]
    assert all(math.isfinite(v) and v>=0 for v in values)
    f,m,z=c['index'];assert 0<=f<9632 and 0<=m<32 and 0<=z<4096
    a=values[:3] if c['label']=='q' else values[3:];scale=max(a);assert scale>0
    b=[v/scale for v in a]
    assert c['row']==[b[1]-b[2],b[0]-b[2]] and c['lower']==-b[2]
    u,v=uv;negative=a[2]+u*(a[1]-a[2])+v*(a[0]-a[2])
    assert negative<0,'witness does not reproduce negative output'
    return negative


def totals(slabs):
    assert [(s['start'],s['stop']) for s in slabs]==[(i,i+16) for i in range(0,9632,16)]
    assert all(math.isfinite(v) for s in slabs for v in s.values())
    for s in slabs:
        assert s['change']>=0 and s['scale']>=0
        close(s['local_relative'],ratio(s['change'],s['scale']))
        for key in ('q','p'):
            count=s['negative_'+key]
            assert isinstance(count,int) and 0<=count<=16*32*4096
            assert (count>0)==(s['minimum_'+key]<0)
    total=lambda k:math.fsum(s[k] for s in slabs)
    glob=ratio(max(s['change'] for s in slabs),max(s['scale'] for s in slabs))
    l1=ratio(total('boundary_num'),max(total('q_abs_flux'),total('p_abs_flux')))
    bol=ratio(abs(total('p_bol')-total('q_bol')),max(abs(total('p_bol')),abs(total('q_bol'))))
    return glob,l1,bol,int(total('negative_q')),int(total('negative_p'))


def review(archive,receipt,source,output,received):
    claim=json.loads(receipt.read_text());assert digest(archive)==claim['sha256'] and archive.stat().st_size==claim['size_bytes']
    data=read_archive(archive);received.mkdir(exist_ok=False)
    import tarfile
    with tarfile.open(archive) as t:
        for n in data:(received/n).write_bytes(t.extractfile(n).read())
    # 保留已核验归档中的原始JSON字节，不重序列化来源证据。
    d=data['declaration.json'];pred=data['prediction.json'];status=data['status.json']
    assert status['status']=='complete_requires_review' and status['accepted_outer_steps']==20
    assert status['new_maps']==status['new_material_steps']==0 and not status['candidate_written']
    assert (d['maximum_passes_per_case'],d['maximum_cuts_per_case'],d['coefficient_cap'],d['retreat'],d['cost_ratio_strict_upper_bound'])==(6,4096,191.,.99,.8)
    assert d['candidate_write_budget']==d['map_budget']==d['feedback_budget']==0
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    audit=json.loads(Path('handoff/evidence/20260925-control-recovery-complete-review.json').read_text())
    source_archive=archive.parent/Path(audit['archive']['path']).name
    assert digest(source_archive)==audit['archive']['sha256'] and source_archive.stat().st_size==audit['archive']['size_bytes']
    import tarfile
    with tarfile.open(source_archive) as t:
        inv={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    def source_read(name):
        p=source/name;c=inv[name];assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
        return json.loads(p.read_text())
    state=source_read('control/state.json');assert len(state['history'])==16 and state['active_map'] is None
    history=state['history'];assert [r['iteration'] for r in history]==list(range(1,17))
    assert all(a['output_sha256']==b['input_sha256'] for a,b in zip(history,history[1:]))
    ret={n:source_read(f'control/endpoints-map{n:02d}/manifest.json') for n in (8,16)}
    actual={}
    for n,v in ret.items():
        assert v['history_rows']==history[n-2:n]
        for k,i,which in [('previous',n-2,'input'),('final',n-1,'input'),('mapped_final',n-1,'output')]:
            c=v['endpoints'][k];assert c['sha256']==history[i][which+'_sha256'];actual[i if which=='input' else i+1]=c
    expected={f'x{k}-x14-x15':[actual[i] for i in (k,14,15,k+1,15,16)] for k in (6,7)}
    assert set(pred)==set(d['cases'])==set(expected)
    claims={(c['path'],c['size_bytes'],c['sha256']) for c in d['claims']}
    prior=source_read('declaration.json')
    assert all((c['path'],c['size_bytes'],c['sha256']) in claims for c in prior['claims']+prior['code'])
    for n in (8,16):
        p=source_read(f'control/pair{n:02d}/feedback_protocol.json')
        assert all((c['path'],c['size_bytes'],c['sha256']) in claims for c in p['sources'].values())
    results={};csvrows=[]
    for name,value in pred.items():
        assert d['cases'][name]['basis']==expected[name]
        assert all((c['path'],c['size_bytes'],c['sha256']) in claims for c in expected[name])
        gram=data[name+'-gram.json'];slabs=gram['slabs']
        assert [(s['start'],s['stop']) for s in slabs]==[(i,i+16) for i in range(0,9632,16)]
        g=np.array([[math.fsum(s['gram'][i][j] for s in slabs) for j in range(2)] for i in range(2)])
        b=np.array([math.fsum(s['rhs'][i] for s in slabs) for i in range(2)])
        assert np.isfinite(g).all() and np.isfinite(b).all() and np.array_equal(g,g.T)
        close(g,gram['gram']);close(b,gram['rhs']);close(math.fsum(s['r2_squared'] for s in slabs),gram['r2_squared'])
        latest=ratio(max(s['change'] for s in slabs),max(s['scale'] for s in slabs))
        close(latest,history[-1]['residual']);close(latest,gram['latest_actual_residual'])
        eigen=np.linalg.eigvalsh(g/abs(g).max());resolved=eigen[0]>0 and eigen[-1]/eigen[0]<1e10
        assert bool(resolved)==gram['solve']['resolved']
        if not resolved:
            assert not value['feasible'] and not value['cost_eligible'] and not value['rounds'];results[name]={'feasible':False,'cost_eligible':False,'reason':'unresolved'};continue
        uv=np.linalg.solve(g/abs(g).max(),-b/abs(g).max());close(uv,gram['solve']['uv'])
        normal=np.linalg.norm(g@uv+b)/max(np.linalg.norm(b),np.linalg.norm(g)*np.linalg.norm(uv));assert normal<1e-10
        assert data[name+'-progress.json']=={'rounds':value['rounds'],'cuts':value['cuts']}
        assert 1<=len(value['rounds'])<=6 and value['peak_rss_bytes']<6*1024**3
        assert not any(value[k] for k in ('actual_map_performed','candidate_written','accepted_material_step','full_constrained_optimum_proven'))
        cuts={}
        for j,row in enumerate(value['rounds']):
            assert row['input_cut_count']==len(cuts)<=4096
            replay=solve_plane(g,b,list(cuts.values()))  # 同一小矩阵优化器重放，明确不是独立QP求解器。
            np.testing.assert_allclose(replay['effective_uv'],row['solve']['effective_uv'],rtol=1e-10,atol=1e-12)
            assert row['solve']['retreat']==.99
            np.testing.assert_array_equal(np.array(row['solve']['raw_uv'])*.99,row['solve']['effective_uv'])
            r=row['result'];assert r['uv']==row['solve']['effective_uv'];u,v=r['uv'];coeff=[v,u,1-u-v];assert r['coefficients']==coeff
            glob,l1,bol,nq,np_=totals(r['slabs']);rel=glob/latest
            for x,y in [(glob,r['predicted_global_residual']),(rel,r['predicted_ratio']),(l1,r['predicted_boundary_l1']),(bol,r['predicted_boundary_bolometric'])]:close(x,y)
            gates=dict(positive=nq==np_==0,coefficient_l1=math.fsum(abs(c) for c in coeff)<192,
                coefficient_sum=abs(math.fsum(coeff)-1)<1e-12,strict_inner=glob<1e-4,maximum_improves=rel<.99,boundary_l1=l1<1e-3,boundary_bolometric=bol<1e-3)
            assert gates==r['gates']
            if gates['positive']:assert j==len(value['rounds'])-1
            for c in r['cuts']:
                six_cut(c,r['uv'])
                if cut_key(c) in cuts:assert cuts[cut_key(c)]==c
                cuts[cut_key(c)]=c
            assert len(cuts)<=4096
            csvrows.append(dict(case=name,pass_number=j+1,predicted_ratio=rel,negative_q=nq,negative_p=np_,boundary_l1=l1,boundary_bolometric=bol))
        assert list(cuts.values())==value['cuts']
        feasible=all(gates.values()) and value['reason']=='positive_candidate_review_required'
        cost=feasible and rel<.8
        assert value['feasible']==feasible and value['cost_eligible']==cost
        results[name]=dict(feasible=feasible,cost_eligible=cost,effective_uv=r['uv'],predicted_ratio=rel,predicted_global_residual=glob,
            predicted_boundary_l1=l1,predicted_boundary_bolometric=bol,cuts=len(cuts),passes=len(value['rounds']),
            gram_condition=float(eigen[-1]/eigen[0]),peak_rss_bytes=value['peak_rss_bytes'],gates=gates)
    selected=min((k for k,v in results.items() if v['cost_eligible']),key=lambda k:(results[k]['predicted_ratio'],k),default=None)
    report=dict(archive=claim,verified_files=len(data)-1,verified_code_claims=len(d['code']),cases=results,selected=selected,
        accepted_outer_steps=20,new_maps=0,new_material_steps=0,full_fields_recomputed_on_mac=False,
        optimizer_independently_reimplemented=False,strict_error_bound=False,baseline_replaced=False)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    with output.with_suffix('.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for k in results:
        rows=[r for r in csvrows if r['case']==k]
        ax[0].plot([r['pass_number'] for r in rows],[r['predicted_ratio'] for r in rows],'o-',label=k)
        ax[1].plot([r['pass_number'] for r in rows],[r['negative_q']+r['negative_p'] for r in rows],'o-',label=k)
    ax[0].axhline(.8,color='black',ls='--');ax[0].set(xlabel='Full-field scan pass',ylabel='Predicted / last actual residual');ax[0].legend()
    ax[1].set(xlabel='Full-field scan pass',ylabel='Negative predicted intensity entries')
    fig.suptitle('Wide-history prediction only; no new transfer map');fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','receipt','source','output','received'):p.add_argument('--'+n,type=Path,required=True)
    print(json.dumps(review(**vars(p.parse_args())),indent=2))
