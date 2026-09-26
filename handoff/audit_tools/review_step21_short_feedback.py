"""Audit short-step formal feedback and its frozen-reference eight-map window."""
import argparse,json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_step21_control_windows as cw
from handoff.audit_tools.review_step21_wide_validation import audit_maps
from handoff.audit_tools.review_step21_positive_plane_maps import assert_close
read,digest,arrays=cw.read,cw.digest,cw.arrays


def review(archive,receipt,received,first,prior,reference,physical_old,output):
    manifest=cw.receive(archive,receipt,received)
    for root,name in [(first,'20260926-short-validation-first-review'),(prior,'20260926-heating-validation-complete-review')]:
        c=read(Path('handoff/evidence')/(name+'.json'))['archive'];p=archive.parent/Path(c['path']).name
        assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
        with tarfile.open(p) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(root/'ARCHIVE_MANIFEST.json')
        cw.verified_inventory(root)
    out=received;d=read(out/'declaration.json');status=read(out/'status.json')
    assert status['accepted_outer_steps']==20 and status['new_material_steps']==0
    assert (d['maximum_maps'],d['maximum_feedback_pairs'],d['cadence'])==(11,2,[2,10])
    # 首map包已经审过物理身份、basis与初始候选；相同文件必须逐位保留。
    for name in ('declaration.json','inputs/trial_material.npz','inputs/config.json',
                 'control/validation.json','control/config.json','control/trial_material.npz','control/initialized_identity.json'):
        assert (out/name).read_bytes()==(first/name).read_bytes(),name
    for c in d['code']:
        p=Path(c['path']);assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
    maps,peaks=audit_maps(out);assert len(maps)<=10
    assert read(out/'control/state.json')['history'][0]==read(first/'control/state.json')['history'][0]
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r=np.load(reference/'base_residual.npy',allow_pickle=False)
    source=read(prior/'control/pair10/feedback_protocol.json')
    for k in ('outer_base_material','physical_old_time_level','base_residual'):
        c=source['sources'][k];p=physical_old if k=='physical_old_time_level' else reference/(k+Path(c['path']).suffix)
        assert digest(p)==c['sha256'] and p.stat().st_size==c['size_bytes']
    selected=[n for n in (2,10) if (out/f'control/pair{n:02d}/decision.json').exists()];assert selected in ([2],[2,10])
    origin={e:arrays(prior/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')};previous=origin
    reports={};count=0
    for n in selected:
        folder=out/f'control/pair{n:02d}';p=read(folder/'feedback_protocol.json');decision=read(folder/'decision.json')
        for key in ('acceptance_gates','formal_state_gates','outer_iteration'):assert p[key]==source[key]
        for key,path in [('control_window_declaration',out/'declaration.json'),('constrained_short_step_validation',out/'control/validation.json'),
                         ('retained_manifest',out/f'control/endpoints-map{n:02d}/manifest.json')]:assert p['sources'][key]['sha256']==digest(path)
        for c in p['common_code_claims']:
            f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
        report,vectors,resources=cw.audit_pair(out,n,reference,physical_old,out/'inputs/trial_material.npz')
        peaks.extend(resources);count+=len(resources)
        window=cw.recompute_window(vectors,previous,r,mass);total=cw.recompute_window(vectors,origin,r,mass)
        cw.verify_window(window,decision['window_comparison']);cw.verify_window(total,decision['from_77577_comparison'])
        kind='post_extrapolation_shift' if n==2 else 'eight_map_drift';assert decision['comparison_kind']==kind
        drift=dict(zip(cw.NAMES,cw.independent_norms(vectors['final']-r,mass)))
        for k,x in drift.items():assert_close(x,decision['fresh_control_minus_r20_norms'][k])
        assert decision['feedback_evaluated'] and decision['zero_control_stable'] and decision['original_gates']==report['gate_checks']
        assert not decision['baseline_replaced'] and not decision['promoted'] and decision['parent_peak_rss_bytes']<6*1024**3
        if n==2:
            assert decision['conditional_continuation_pass']==decision['zero_control_stable']
            rows=read(out/'control/state.json')['history'];ret=read(out/'control/endpoints-map02/manifest.json')
            assert ret['endpoints']['previous']['sha256']==read(out/'control/validation.json')['candidate']['sha256']
            assert ret['endpoints']['final']['sha256']==rows[0]['output_sha256']
        else:assert decision['conditional_continuation_pass']==(decision['zero_control_stable'] and window['passed'])
        reports[str(n)]={**report,'comparison_kind':kind,'window':window,'from_77577':total,'final_minus_r20':drift}
        previous=vectors
    assert read(out/'half/state.json')==read(first/'half/state.json')
    if len(maps)>2:assert read(out/'control/pair02/decision.json')['conditional_continuation_pass']
    first_audit=read(Path('handoff/evidence/20260926-short-validation-first-review.json'));peaks.append(first_audit['maximum_worker_peak_kib'])
    complete=(out/'summary.json').exists()
    if complete:
        s=read(out/'summary.json');assert s['accepted_outer_steps']==20 and s['new_material_steps']==0 and not s['baseline_replaced'] and not s['strict_error_bound']
        assert s['maps']==len(maps)+1 and s['control_maps']==len(maps) and s['half_maps']==1
        if s['status']=='constrained_short_step_validation_complete_requires_review':assert len(maps)==10 and selected==[2,10] and thermal['validated']
        elif s['status']=='first_control_or_heating_not_validated':assert len(maps)==2 and selected==[2] and not thermal['validated']
        else:raise AssertionError('unexpected terminal requires dedicated failure audit')
        for n in selected:assert s['cases'][str(n)]==read(out/f'control/pair{n:02d}/decision.json')
    else:assert manifest['stage'] in ('control-map02-feedback','control-map10-feedback')
    result=dict(archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),maps=maps,
        half_maps=1,feedback_rounds=selected,windows=reports,final_summary_present=complete,
        maximum_proc_kib=max(peaks),map_process_receipts=76*(len(maps)+1),feedback_process_receipts=count,
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
        production_window_reducer_reused=False,
        original_seven_gate_reducer_reused=True,material_ode_recomputed_on_mac=False,full_large_fields_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    for i,label in enumerate(cw.NAMES):ax.plot(selected,[max(x[i] for x in reports[str(n)]['window']['vector_difference_over_frozen_r20_norms'].values()) for n in selected],'o-',label=label)
    ax.axhline(.001,ls='--',color='black');ax.set(xlabel='2: initialization shift; 10: eight-map drift',ylabel='Vector difference / original r20 norm');ax.legend()
    fig.suptitle('Short-step feedback audit; no new material acceptance');fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('archive','receipt','received','first','prior','reference','physical-old','output'):p.add_argument('--'+n,type=Path,required=True)
    r=review(**vars(p.parse_args()));print(json.dumps({k:r[k] for k in ('verified_files','verified_code_claims','feedback_rounds','windows')},indent=2))
