"""Two long fixed-x20 windows: residual stationarity without rebasing acceptance."""
import argparse,json,os,shutil,signal,time,resource,sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
from operations import validate_step21_positive_plane as v
pipeline,ROOT,fixed,fresh,reused,driver=v.pipeline,v.ROOT,v.fixed,v.fresh,v.reused,v.driver
SOURCE='outputs/hpc/step21-positive-plane-validation-20260925'
LIMIT=16
CADENCE=(8,16)
WINDOW_TOLERANCE=1e-3


def window_comparison(current,previous,r20,mass):
    if set(current)!={'previous','final'} or set(previous)!={'previous','final'}:raise ValueError('endpoint identity')
    def norm(x):
        d=asdict(fresh.bridge.encoded_residual_norms(x,mass))
        values=np.array([d[k] for k in ('l2','mass_weighted','maximum_cell')])
        if not np.isfinite(values).all():raise ValueError('nonfinite residual norm')
        return values
    denominator=norm(r20)
    if np.any(denominator<=0):raise ValueError('zero reference norm')
    # 先作完整向量差再取范数；同范数的不同方向不能被误判为稳定。
    # 原 r20 只提供固定尺度，此诊断不授权替换接受基准。
    ratios={a+'_vs_'+b:(norm(x-y)/denominator).tolist() for a,x in current.items() for b,y in previous.items()}
    if not all(np.isfinite(x).all() for x in ratios.values()):raise ValueError('nonfinite window ratio')
    return {'vector_difference_over_frozen_r20_norms':ratios,'passed':all(max(x)<WINDOW_TOLERANCE for x in ratios.values()),
            'tolerance':WINDOW_TOLERANCE,'strict_error_bound':False,'baseline_replaced':False}


def prepare(out):
    ev=ROOT/'handoff/evidence';root=ROOT/SOURCE
    names=['summary.json','control/state.json','control/config.json','control/trial_material.npz','control/endpoints-map03/manifest.json',
           'control/pair03/feedback_protocol.json','control/pair03/previous_response.npz','control/pair03/final_response.npz']
    claims=v.audited_inputs(root,ev/'20260925-positive-validation-complete-review.json',ev/'20260925-positive-validation-77126-terminal.json',77126,names)
    summary=pipeline.read(root/'summary.json')
    if not summary['cases']['control']['baseline_stable'] or any(summary['cases'][n]['pair_supported'] for n in ('thermal','population')):
        raise RuntimeError('diagnostic premise changed')
    reference=pipeline.read(root/'control/pair03/feedback_protocol.json');sources=reference['sources']
    base=v.load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path']);old=v.load_arrays(ROOT/sources['physical_old_time_level']['path'])
    trial=v.load_arrays(root/'control/trial_material.npz');fixed.exact_trial(trial,base,r,old,'control')
    fixed.validate_base_against_accepted(base,v.load_arrays(ROOT/fixed.BASE/'trial_material.npz'))
    if not np.array_equal(r,v.load_arrays(ROOT/fixed.BASE/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    state=pipeline.read(root/'control/state.json');ret=pipeline.read(root/'control/endpoints-map03/manifest.json')
    if state['active_map'] is not None or len(state['history'])!=3 or ret['history_rows']!=state['history'][-2:]:raise RuntimeError('source incomplete')
    seed=ret['endpoints']['mapped_final']
    if seed['sha256']!=state['history'][-1]['output_sha256']:raise RuntimeError('seed not latest mapped endpoint')
    # 初始化前先固定 trial，防止通用流水线迁移为历史 0.0625 候选。
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(root/'control/trial_material.npz',inputs/'trial_material.npz')
    cfg=pipeline.read(root/'control/config.json')
    if pipeline.sha256(root/'control/config.json')!=state['config_sha256']:raise RuntimeError('source config changed')
    pipeline.write_json(inputs/'config.json',cfg);fixed.same_trial(v.load_arrays(inputs/'trial_material.npz'),trial)
    claims+=cfg['sources']+list(sources.values())+[seed]
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/diagnose_step21_control_windows.sbatch','tests/test_diagnose_step21_control_windows.py','handoff/protocols/step21-control-windows-v1.md')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan={'cases':{'control':{'trial':pipeline.claim(inputs/'trial_material.npz'),'config':pipeline.claim(inputs/'config.json')}},
          'seed':seed,'claims':claims,'code':code,'maximum_maps':LIMIT,'cadence':list(CADENCE),'maximum_feedback_pairs':2,
          'window_tolerance':WINDOW_TOLERANCE,'accepted_outer_steps':20,'automatic_promotion':False,'baseline_replacement_authorized':False,'environment':pipeline.environment()}
    reused.immutable(out/'declaration.json',plan)
    previous={e:v.load_arrays(root/f'control/pair03/{e}_response.npz')['residual'] for e in ('previous','final')}
    return plan,reference,base,r,old,previous


def map_once(folder,cfg,state):
    reused.checkpoint()
    if len(state['history'])>=LIMIT:raise RuntimeError('sixteen-map hard limit')
    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
    if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('mapping fault')
    paths=list((folder/f"map{len(state['history']):04d}").glob('block*.process-*.json'))
    if len(paths)!=76:raise RuntimeError('process receipt count')
    for path in paths:
        p=pipeline.read(path)
        if p['returncode'] or not p['memory_guard_passed'] or p['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',{'status':status,'accepted_outer_steps':20,'new_material_steps':0,'updated_unix':time.time(),**kw})
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained space')
        plan,reference,base,r,old,previous=prepare(out);origin={k:x.copy() for k,x in previous.items()};reports={};reused.LIMITS={'control':LIMIT}
        with fixed.relay_dispatch():
            folder,cfg,state=reused.child(out,'control','control',plan['seed'],plan)
            for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),base)
            for _ in range(LIMIT):
                mark('mapping',completed_maps=len(state['history']));map_once(folder,cfg,state);n=len(state['history'])
                if n not in CADENCE:continue
                if not pipeline.pair_ready(state['history'],1e-4):raise RuntimeError('long-window inner pair not ready')
                fixed.retain_pair(folder,state);ret=pipeline.read(folder/f'endpoints-map{n:02d}/manifest.json');rd=folder/f'pair{n:02d}';rd.mkdir()
                p=fresh.new_protocol(reference,rd,ret['endpoints'],ret['history_rows'],16)
                for key in ('positive_plane_validation','affine_validation'):p['sources'].pop(key,None)
                p['sources']['control_window_declaration']=pipeline.claim(out/'declaration.json')
                p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz');p['sources']['retained_manifest']=pipeline.claim(folder/f'endpoints-map{n:02d}/manifest.json')
                p['numerical_backtracking']={'alpha':0.,'fixed_base_accepted_index':20,'direction_family':'control','diagnostic_only':True,'physical_time_advanced':False}
                p['outer_iteration'].update(direction_is_latest_confirmed_response=True,diagnostic_only=True)
                fixed.set_authorization(p,'control');fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r,old,'control');fixed.native_identity(p)
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];path=rd/'feedback_protocol.json';reused.immutable(path,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',after_maps=n)
                with reused.feedback_stop_guard():stable=fixed.zero_feedback(rd,p,path,state['history'][-2:])
                summary=pipeline.read(rd/'baseline_summary.json')
                if summary.get('material_response_failures'):raise RuntimeError('physical response rejected')
                vectors={e:v.load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                report={'zero_control_stable':stable,'window_comparison':window_comparison(vectors,previous,r,old['cell_mass_g_cm2']),
                        'from_77126_comparison':window_comparison(vectors,origin,r,old['cell_mass_g_cm2']),
                        'fresh_control_minus_r20_norms':asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2'])),
                        'original_gates':summary['gate_checks'],'baseline_replaced':False,'promoted':False}
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                report['parent_peak_rss_bytes']=peak
                reused.immutable(rd/'decision.json',report);reports[str(n)]=report;previous=vectors
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'control-map{n:02d}-feedback')
                if not stable:raise RuntimeError('zero control feedback unstable')
        reused.verify(plan['claims']+plan['code'])
        report={'status':'control_window_diagnostic_complete','windows':reports,'both_windows_stable':all(x['window_comparison']['passed'] for x in reports.values()),
                'accepted_outer_steps':20,'new_material_steps':0,'baseline_replaced':False,'strict_error_bound':False}
        reused.immutable(out/'summary.json',report);mark(report['status']);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
