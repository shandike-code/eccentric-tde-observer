"""Resume the audited eight-map prefix; settle its feedback before any new map."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json,os,resource,shutil,signal,sys,tarfile,time
from pathlib import Path
import numpy as np
from operations import diagnose_step21_control_windows as original
v=original.v
pipeline,ROOT,fixed,fresh,reused,driver=original.pipeline,original.ROOT,original.fixed,original.fresh,original.reused,original.driver
FAILED='outputs/hpc/step21-control-windows-20260925'
RECOVERY_ERROR="RuntimeError('trial-residual acceptance authorization changed')"


def control_protocol(finite_template,zero_template,out,endpoints,history,trial,retained,declaration):
    """Use the finite-template factory contract, then freeze a zero-only protocol."""
    # 构造器有有限试步的模板契约；绝不修改旧零控制授权来绕过检查。
    # 采用已审有限模板只做构造，写盘/执行之前必须替换为零位移trial并禁止接受。
    for key in ('acceptance_gates','formal_state_gates'):
        if finite_template[key]!=zero_template[key]:raise RuntimeError('control/template gates differ')
    for key in ('outer_base_material','base_residual','physical_old_time_level'):
        if finite_template['sources'][key]!=zero_template['sources'][key]:raise RuntimeError('control/template physical identity differs')
    p=fresh.new_protocol(finite_template,out,endpoints,history,16)
    for key in ('positive_plane_validation','affine_validation'):p['sources'].pop(key,None)
    p['sources'].update(control_window_declaration=declaration,trial_material=trial,retained_manifest=retained)
    p['numerical_backtracking']={'alpha':0.,'fixed_base_accepted_index':20,'direction_family':'control','diagnostic_only':True,'physical_time_advanced':False}
    p['outer_iteration'].update(direction_is_latest_confirmed_response=True,diagnostic_only=True)
    fixed.set_authorization(p,'control')
    if any(p['authorization'][key] is not False for key in ('accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass','accept_finite_trial_only_if_all_acceptance_gates_pass','accept_material_step')):
        raise RuntimeError('control acceptance authorized')
    return p


def inherit_history(state,history,resume_seed):
    if state['history'] or state['active_map'] is not None:raise RuntimeError('destination already has work')
    if len(history)!=8 or [x['iteration'] for x in history]!=list(range(1,9)):raise RuntimeError('not an eight-map prefix')
    if any(a['output_sha256']!=b['input_sha256'] for a,b in zip(history,history[1:])):raise RuntimeError('broken inherited lineage')
    if history[-1]['output_sha256']!=resume_seed['sha256'] or state['current_sha256']!=resume_seed['sha256']:raise RuntimeError('wrong resumed state')
    state['history']=deepcopy(history);state['inherited_map_count']=8
    return state


def continuation_schedule(feedback,map_one):
    """The owed pair is a prerequisite; the remaining budget is exactly eight."""
    feedback(8)
    for n in range(9,17):map_one(n)
    feedback(16)


def prepare(out):
    ev=ROOT/'handoff/evidence';source=ROOT/FAILED
    audit=pipeline.read(ev/'20260925-control-windows-77264-failure-review.json');terminal=pipeline.read(ev/'20260925-control-windows-77264-terminal.json')
    if terminal['job_id']!=77264 or terminal['state']!='FAILED' or audit['error']!=RECOVERY_ERROR or audit['feedback_pairs_executed']!=0 or audit['remaining_new_map_budget']!=8:raise RuntimeError('unaudited recovery premise')
    reused.verify([audit['archive']])
    with tarfile.open(ROOT/audit['archive']['path']) as t:manifest=json.load(t.extractfile('ARCHIVE_MANIFEST.json'))
    inventory={c['path']:c for c in manifest['files']};claims=[pipeline.claim(ev/'20260925-control-windows-77264-failure-review.json'),pipeline.claim(ev/'20260925-control-windows-77264-terminal.json'),audit['archive']]
    def source_claim(name):
        c=pipeline.claim(source/name);expected=inventory[name]
        if any(c[k]!=expected[k] for k in ('size_bytes','sha256')):raise RuntimeError('audited source changed: '+name)
        claims.append(c);return c
    for name in ('status.json','declaration.json','control/state.json','control/config.json','control/trial_material.npz','control/endpoints-map08/manifest.json'):source_claim(name)
    status=pipeline.read(source/'status.json');state=pipeline.read(source/'control/state.json');prior=pipeline.read(source/'declaration.json');ret=pipeline.read(source/'control/endpoints-map08/manifest.json')
    if status['status']!='failed' or status['error']!=RECOVERY_ERROR or state['active_map'] is not None or len(state['history'])!=8:raise RuntimeError('source no longer recoverable')
    if ret['history_rows']!=state['history'][-2:] or list((source/'control/pair08').glob('*')):raise RuntimeError('feedback started or retained rows changed')
    for e,row,kind in (('previous',state['history'][-2],'input'),('final',state['history'][-1],'input'),('mapped_final',state['history'][-1],'output')):
        if ret['endpoints'][e]['sha256']!=row[kind+'_sha256']:raise RuntimeError('retained endpoint identity')
    root=ROOT/original.SOURCE
    names=['control/pair03/feedback_protocol.json','thermal/pair03/feedback_protocol.json','control/pair03/previous_response.npz','control/pair03/final_response.npz']
    claims+=v.audited_inputs(root,ev/'20260925-positive-validation-complete-review.json',ev/'20260925-positive-validation-77126-terminal.json',77126,names)
    zero=pipeline.read(root/names[0]);finite=pipeline.read(root/names[1]);s=zero['sources']
    base=v.load_arrays(ROOT/s['outer_base_material']['path']);r=np.load(ROOT/s['base_residual']['path'],allow_pickle=False);old=v.load_arrays(ROOT/s['physical_old_time_level']['path'])
    trial=v.load_arrays(source/'control/trial_material.npz');fixed.exact_trial(trial,base,r,old,'control');fixed.same_trial(trial,base)
    fixed.validate_base_against_accepted(base,v.load_arrays(ROOT/fixed.BASE/'trial_material.npz'))
    if not np.array_equal(r,v.load_arrays(ROOT/fixed.BASE/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(source/'control/trial_material.npz',inputs/'trial_material.npz')
    cfg=pipeline.read(source/'control/config.json')
    if pipeline.sha256(source/'control/config.json')!=state['config_sha256']:raise RuntimeError('source configuration changed')
    pipeline.write_json(inputs/'config.json',cfg)
    inherited=[]
    for name in sorted(inventory):
        if name.startswith('control/map') or name=='control/endpoints-map08/manifest.json':
            if not name.endswith('.json'):raise RuntimeError('unexpected inherited metadata type')
            inherited.append({'relative_path':name,'source':source_claim(name)})
    claims+=prior['claims']+prior['code']+list(s.values())+list(ret['endpoints'].values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/recover_step21_control_windows.sbatch','tests/test_recover_step21_control_windows.py','handoff/protocols/step21-control-windows-recovery-v1.md')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    # 在初始化或新map之前真实构造控制协议，提前发现本次曾漏测的模板契约。
    preview=control_protocol(finite,zero,out/'control/pair08',ret['endpoints'],ret['history_rows'],pipeline.claim(inputs/'trial_material.npz'),pipeline.claim(source/'control/endpoints-map08/manifest.json'),pipeline.claim(source/'declaration.json'))
    fixed.native_identity(preview)
    reused.verify(claims+code)
    plan={'cases':{'control':{'trial':pipeline.claim(inputs/'trial_material.npz'),'config':pipeline.claim(inputs/'config.json')}},
          'seed':prior['seed'],'resume_seed':ret['endpoints']['mapped_final'],'claims':claims,'code':code,'maximum_maps':16,'cadence':[8,16],'maximum_feedback_pairs':2,'window_tolerance':.001,
          'accepted_outer_steps':20,'automatic_promotion':False,'baseline_replacement_authorized':False,'environment':pipeline.environment(),
          'recovery':{'source':FAILED,'source_job':77264,'failure_review':pipeline.claim(ev/'20260925-control-windows-77264-failure-review.json'),'source_state':pipeline.claim(source/'control/state.json'),'inherited_map_count':8,'maximum_new_maps':8,'feedback_due_before_new_map':True,'inherited_files':inherited}}
    reused.immutable(out/'declaration.json',plan)
    previous={e:v.load_arrays(root/f'control/pair03/{e}_response.npz')['residual'] for e in ('previous','final')}
    return plan,finite,zero,base,r,old,previous,state['history']


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing_recovery')
    try:
        if shutil.disk_usage(out).free<8*pipeline.STATE_BYTES:raise RuntimeError('insufficient recovery space')
        plan,finite,zero,base,r,old,previous,history=prepare(out);origin={k:x.copy() for k,x in previous.items()};reports={};reused.LIMITS={'control':16}
        with fixed.relay_dispatch():
            folder,cfg,state=reused.child(out,'control','control',plan['resume_seed'],plan)
            for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),base)
            for item in plan['recovery']['inherited_files']:
                dest=out/item['relative_path'];dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists():raise FileExistsError(dest)
                shutil.copyfile(ROOT/item['source']['path'],dest)
                if pipeline.sha256(dest)!=item['source']['sha256']:raise RuntimeError('copied history differs')
            inherit_history(state,history,plan['resume_seed']);pipeline.write_json(folder/'state.json',state)
            def new_map(n):
                if len(state['history'])!=n-1:raise RuntimeError('continuation map counter')
                mark('mapping',completed_maps=n-1,inherited_maps=8);original.map_once(folder,cfg,state)
            def feedback(n):
                nonlocal previous
                reused.checkpoint()
                if len(state['history'])!=n or not pipeline.pair_ready(state['history'],1e-4):raise RuntimeError('feedback endpoint not ready')
                if n!=8:fixed.retain_pair(folder,state)
                ret_path=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(ret_path);rd=folder/f'pair{n:02d}';rd.mkdir()
                p=control_protocol(finite,zero,rd,ret['endpoints'],ret['history_rows'],pipeline.claim(folder/'trial_material.npz'),pipeline.claim(ret_path),pipeline.claim(out/'declaration.json'))
                fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r,old,'control');fixed.native_identity(p)
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];path=rd/'feedback_protocol.json';reused.immutable(path,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',after_maps=n,inherited_maps=8)
                with reused.feedback_stop_guard():stable=fixed.zero_feedback(rd,p,path,state['history'][-2:])
                summary=pipeline.read(rd/'baseline_summary.json')
                if summary.get('material_response_failures'):raise RuntimeError('physical response rejected')
                vectors={e:v.load_arrays(rd/f'{e}_response.npz')['residual'] for e in ('previous','final')}
                report={'zero_control_stable':stable,'window_comparison':original.window_comparison(vectors,previous,r,old['cell_mass_g_cm2']),
                        'from_77126_comparison':original.window_comparison(vectors,origin,r,old['cell_mass_g_cm2']),
                        'fresh_control_minus_r20_norms':asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2'])),
                        'original_gates':summary['gate_checks'],'baseline_replaced':False,'promoted':False}
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                report['parent_peak_rss_bytes']=peak;reused.immutable(rd/'decision.json',report);reports[str(n)]=report;previous=vectors
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'control-map{n:02d}-feedback')
                if not stable:raise RuntimeError('zero control feedback unstable')
            continuation_schedule(feedback,new_map)
        reused.verify(plan['claims']+plan['code'])
        result={'status':'control_window_diagnostic_complete','windows':reports,'both_windows_stable':all(x['window_comparison']['passed'] for x in reports.values()),'accepted_outer_steps':20,'new_material_steps':0,'baseline_replaced':False,'strict_error_bound':False,'inherited_maps':8,'new_maps':8}
        reused.immutable(out/'summary.json',result);mark(result['status']);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,args.run))
