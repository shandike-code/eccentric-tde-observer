"""Audit transferred fixed-state common-frequency results, retaining old verdicts."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(p):return json.loads(p.read_text())


def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def arrays(p):
    with np.load(p,allow_pickle=False) as a:return {k:np.array(a[k]) for k in a.files}


def metrics(a,b,w):
    ai=float(np.sum(w*a));bi=float(np.sum(w*b))
    return {'volume_l1':float(np.sum(w*abs(a-b))/max(np.sum(w*abs(a)),np.sum(w*abs(b)))),
            'net_fraction':abs(ai-bi)/max(abs(ai),abs(bi)),
            'reference_integral':ai,'compared_integral':bi,'difference_depth_l1':float(np.sum(w*abs(a-b)))}


def review(archive,receipt,received,original,output):
    claim=read(receipt);assert digest(archive)==claim['sha256'] and archive.stat().st_size==claim['size_bytes']
    received.mkdir(exist_ok=False)
    with tarfile.open(archive) as t:
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers())
        t.extractall(received,filter='data')
    files=read(received/'MANIFEST.json')['files']
    for c in files:
        f=received/c['path'];assert digest(f)==c['sha256'] and f.stat().st_size==c['size_bytes']
    assert read(received/'status.json')['status']=='common_source_consistent'
    labels=[label for label in ('previous','final') if (received/label/'summary.json').exists()]
    fig,axes=plt.subplots(len(labels),2,figsize=(11,4*len(labels)),layout='constrained',squeeze=False)
    results=[]
    for ax,label in zip(axes,labels):
        folder=received/label;s=read(folder/'summary.json');plan=read(folder/'common_declaration.json');a=arrays(folder/'comparison.npz')
        assert digest(folder/'comparison.npz')==s['arrays']['sha256']
        assert all(np.isfinite(v).all() for v in a.values())
        assert s['original_formal_verdict_retained']=='gate_failed' and not s['material_response_evaluated']
        selected=plan['selected_blocks'];assert selected==([24] if plan['pilot'] else list(range(76)))
        oldroot=original/'full/feedback-round1';oldmanifest=read(oldroot/f'feedback/{label}_manifest.json')
        byindex={r['block_index']:r for r in oldmanifest['completed_blocks']};total={};ownership=np.zeros(9632,int)
        peaks=[]
        for i in selected:
            report=read(folder/f'block{i:02d}.json');proc=read(folder/f'block{i:02d}.process.json');block=arrays(folder/f'block{i:02d}.npz')
            assert digest(folder/f'block{i:02d}.npz')==report['arrays']['sha256']
            assert proc['returncode']==0 and proc['memory_guard_passed'] and report['native_peak_mib']<6144
            row=byindex[i];p=original/Path(row['partial_path']).relative_to('outputs/hpc/step16-backtrack-20260923')
            assert digest(p)==row['partial_sha256'];old=arrays(p)
            for k in ('rate','direct','formal'):assert np.array_equal(block['original_'+k],old['source_'+k+'_heating_erg_s_cm3'])
            assert report['core_group_start']==row['core_group_start'] and report['core_group_stop']==row['core_group_stop']
            ownership[report['core_group_start']:report['core_group_stop']]+=1
            if not total:total={k:np.zeros_like(v) for k,v in block.items()}
            for k,v in block.items():total[k]+=v
            peaks.append((report['native_peak_mib'],proc['native_observed_peak_kib']))
        for k,v in total.items():assert np.array_equal(v,a[k])
        if not plan['pilot']:
            assert np.all(ownership==1)
            oldfb=arrays(oldroot/f'{label}_feedback.npz')
            assert np.array_equal(a['atomic_rate_heating_erg_s_cm3'],oldfb['atomic_rate_heating_erg_s_cm3'])
        w=a['subcell_width_cm'];assert (w>0).all()
        assert np.array_equal(w,arrays(oldroot/f'{label}_feedback.npz')['subcell_width_cm'])
        rate=a['atomic_rate_heating_erg_s_cm3'];common=a['common_formal_erg_s_cm3']
        checks={name:metrics(x,y,w) for name,x,y in (
            ('atomic_vs_common',rate,common),('direct_vs_common',a['original_direct'],common),
            ('atomic_vs_old_formal',rate,a['original_formal']),('atomic_vs_direct',rate,a['original_direct']))}
        # 净积分差受两次大数相减影响，保存本机复算值和差，不把相对末位一致当物理门。
        differences={name:{key:checks[name][key]-value for key,value in values.items()} for name,values in s['metrics'].items()}
        gates=s['formal_state_gate_thresholds']
        assert checks['atomic_vs_common']['volume_l1']<gates['atomic_rate_vs_inverse_four_force_volume_l1_below']
        assert checks['atomic_vs_common']['net_fraction']<gates['atomic_rate_vs_inverse_four_force_global_fraction_below']
        assert checks['atomic_vs_direct']['volume_l1']<gates['atomic_rate_vs_direct_comoving_heating_volume_l1_below']
        for key in ('original_rate','original_formal','common_formal_erg_s_cm3'):ax[0].plot(a[key],label=key)
        ax[0].set(title=label+(' pilot block24' if plan['pilot'] else ' all 76 blocks'),xlabel='Radiation depth index',ylabel='Heating (erg s-1 cm-3)',yscale='symlog');ax[0].legend()
        ax[1].plot(np.cumsum(w*(rate-a['original_formal'])),label='old same-number bands')
        ax[1].plot(np.cumsum(w*(rate-common)),label='common physical band')
        ax[1].set(xlabel='Radiation depth index',ylabel='Cumulative source difference (erg s-1 cm-2)',yscale='symlog');ax[1].legend()
        results.append({'endpoint':label,'all_76_blocks':not plan['pilot'],'verified_blocks':len(selected),'metrics':checks,
                        'local_minus_linux_metrics':differences,'native_peak_mib':max(v[0] for v in peaks),'proc_peak_kib':max(v[1] for v in peaks),
                        'pilot_rate_label_is_source_rate_not_recomputed_atomic_rate':plan['pilot']})
    result={'archive':claim,'verified_files':len(files),'results':results,'old_verdicts_unchanged':True,'material_step_accepted':False,'frequency_truncation_established':False}
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');fig.savefig(output.with_suffix('.png'),dpi=160);plt.close(fig)
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','original','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();review(a.archive,a.receipt,a.received,a.original,a.output)


if __name__=='__main__':main()
