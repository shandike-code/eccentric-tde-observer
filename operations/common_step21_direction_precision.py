"""Fixed-trial radiation precision for the audited x20 split-direction experiment."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
import os
import shutil
import signal
import tarfile
import time
import numpy as np
from operations import common_native_feedback as fresh
from operations.common_outer_step21 import verify_step21_pair,validate_acceptance
from operations.common_confirmation_batch import validate_zero,native_identity,cross_comparisons,all_pair_gates
from operations.common_confirmation_step17 import latest_seed,validate_base_against_accepted
from operations.common_precision_maps import retain_pair
from operations.constrained_hybrid_batch import relay_dispatch
from diagnostics import interval_diagnostic as driver
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec,ground_state_material_trial_within_trust_region
pipeline=fresh.pipeline;pair=fresh.pair;reused=fresh.reused;ROOT=fresh.ROOT;load_arrays=fresh.load_arrays
PRIOR='outputs/hpc/common-step21-directions-20260925'
BASE='outputs/hpc/common-confirmation20-20260924/confirm2'
SOURCE='outputs/hpc/common-step21-20260924'
ALPHAS={'control':0.,'thermal':1/256,'population':1/256}
LIMITS={'control':8,'thermal':8,'population':8}
CONTRACTION={'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass','candidate_maximum_cell_contraction_pass'}


from operations.common_step21_directions import exact_trial,zero_feedback,direction_sequence


def validate_source_audit(audit,terminal):
    if terminal['job_id']!=76905 or terminal['state']!='COMPLETED':raise RuntimeError('source job not complete')
    if audit['accepted_outer_steps']!=20 or set(audit['pairs'])!={'control','thermal04','thermal08','population04','population08'}:raise RuntimeError('source audit incomplete')
    gates=audit['pairs']['population08']['gate_checks']
    if gates.get('inner_noise_resolved_pass') is not False:raise RuntimeError('population noise no longer justifies precision experiment')
    if any(audit['pairs'][k]['all_16_pair_gates'] for k in ('thermal08','population08')):raise RuntimeError('source verdict changed')


def same_trial(actual,frozen):
    if set(actual)!=set(frozen) or any(not np.array_equal(actual[k],frozen[k]) for k in frozen):raise RuntimeError('fixed trial changed')


def set_authorization(p,name):
    if name not in ALPHAS:raise ValueError('undeclared direction')
    if name=='control':
        p['classification']='zero displacement baseline; finite-step acceptance forbidden'
        p['authorization'].update(accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass=False,accept_finite_trial_only_if_all_acceptance_gates_pass=False,accept_material_step=False,zero_displacement_control=True)
    elif not p['authorization'].get('accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass') or p['authorization'].get('zero_displacement_control'):
        raise RuntimeError('nonzero diagnostic inherited zero-control authorization')


def prepare(out):
    audit_path=ROOT/'handoff/evidence/20260925-common-step21-directions-review.json'
    terminal_path=ROOT/'handoff/evidence/20260925-step21-directions-76905-terminal.json'
    audit=pipeline.read(audit_path);validate_source_audit(audit,pipeline.read(terminal_path))
    reused.verify([audit['archive']])
    with tarfile.open(ROOT/audit['archive']['path']) as archive:
        inventory={c['path']:c for c in json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    claims=[pipeline.claim(audit_path),pipeline.claim(terminal_path)]
    def claim_source(name):
        c=pipeline.claim(ROOT/PRIOR/name);expected=inventory[name]
        if any(c[k]!=expected[k] for k in ('size_bytes','sha256')):raise RuntimeError('source differs from audited archive: '+name)
        claims.append(c);return c
    claim_source('summary.json')
    summary=pipeline.read(ROOT/PRIOR/'summary.json')
    if summary['status']!='direction_budget_complete_requires_review' or summary['accepted_outer_steps']!=20 or summary['new_material_steps']!=0:raise RuntimeError('source status changed')
    claim_source('population/pair08/feedback_protocol.json')
    reference=pipeline.read(ROOT/PRIOR/'population/pair08/feedback_protocol.json');s=reference['sources']
    base=load_arrays(ROOT/s['outer_base_material']['path']);r=np.load(ROOT/s['base_residual']['path'],allow_pickle=False);old=load_arrays(ROOT/s['physical_old_time_level']['path'])
    validate_zero(base,base,r,old);validate_base_against_accepted(base,load_arrays(ROOT/BASE/'trial_material.npz'))
    acceptance_path=ROOT/'handoff/evidence/20260924-accepted-step20.json';acceptance=pipeline.read(acceptance_path)
    validate_acceptance(acceptance,pipeline.read(ROOT/'handoff/evidence/20260924-confirmation20-76727-terminal.json'))
    reused.verify(acceptance['claims']);claims.append(pipeline.claim(acceptance_path))
    if not np.array_equal(r,load_arrays(ROOT/BASE/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    claims+=[s[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]
    inputs=out/'inputs';inputs.mkdir();cases={};seeds={}
    for name in ALPHAS:
        for f in ('trial_material.npz','config.json','state.json'):claim_source(name+'/'+f)
        st=pipeline.read(ROOT/PRIOR/name/'state.json');cfg=pipeline.read(ROOT/PRIOR/name/'config.json')
        if st['active_map'] is not None or len(st['history'])!=(4 if name=='control' else 8):raise RuntimeError('source state incomplete')
        if pipeline.sha256(ROOT/PRIOR/name/'config.json')!=st['config_sha256']:raise RuntimeError('source config differs')
        trial=load_arrays(ROOT/PRIOR/name/'trial_material.npz');exact_trial(trial,base,r,old,name)
        # 每个固定物质候选继续自身最新场；不得交叉换种子引入新的松弛瞬态。
        seeds[name]=latest_seed(st);claims.append(seeds[name])
        folder=inputs/name;folder.mkdir();shutil.copyfile(ROOT/PRIOR/name/'trial_material.npz',folder/'trial_material.npz')
        same_trial(load_arrays(folder/'trial_material.npz'),trial)
        pipeline.write_json(folder/'config.json',cfg)
        cases[name]={'trial':pipeline.claim(folder/'trial_material.npz'),'config':pipeline.claim(folder/'config.json')}
        check=deepcopy(reference);check['sources']['trial_material']=cases[name]['trial'];native_identity(check)
        claims+=list(cases[name].values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/common_step21_direction_precision.sbatch','tests/test_common_step21_direction_precision.py','handoff/protocols/common-step21-direction-precision-v1.md')]
    plan={'cases':cases,'seeds':seeds,'claims':claims,'code':code,'alphas':ALPHAS,'limits':LIMITS,'maximum_maps':24,'maximum_feedback_pairs':6,'diagnostic_only':True,'accepted_outer_steps':20,'automatic_promotion':False,'physical_dt_changed':False,'environment':pipeline.environment()}
    reused.verify(claims+code);reused.immutable(out/'declaration.json',plan)
    return plan,reference,base,r,old


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage must be disabled')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<32*pipeline.STATE_BYTES:raise RuntimeError('checkpoint disk budget insufficient')
        plan,reference,base,r,old=prepare(out);reused.LIMITS=LIMITS.copy();reports={};baseline={};seeds=plan['seeds']
        def evaluate(name):
            mark('mapping',case=name,budget=LIMITS[name]);folder,cfg,state=reused.child(out,name,name,seeds[name],plan);case_reports={}
            for _ in range(LIMITS[name]):
                reused.checkpoint()
                if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
                if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('mapping resource/fault state')
                n=len(state['history']);mark('mapping',case=name,completed_maps=n,budget=LIMITS[name])
                if n not in (4,8):continue
                if not pipeline.pair_ready(state['history'],1e-4):
                    case_reports[str(n)]={'feedback_evaluated':False,'inner_pair_ready':False};reused.archive(out,name+f'-map{n:02d}-inner-not-ready')
                    if name=='control':
                        reports[name]=case_reports;return 'baseline_unstable'
                    continue
                retain_pair(folder,state);retained=pipeline.read(folder/f'endpoints-map{n:02d}/manifest.json');rd=folder/f'pair{n:02d}';rd.mkdir()
                p=fresh.new_protocol(reference,rd,retained['endpoints'],retained['history_rows'],16);p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz')
                p['sources']['retained_manifest']=pipeline.claim(folder/f'endpoints-map{n:02d}/manifest.json')
                p['numerical_backtracking']={'alpha':ALPHAS[name],'fixed_base_accepted_index':20,'direction_family':name,'diagnostic_only':True,'physical_time_advanced':False}
                exact_trial(load_arrays(folder/'trial_material.npz'),base,r,old,name);native_identity(p)
                p['outer_iteration']['direction_is_latest_confirmed_response']=(name=='control')
                p['outer_iteration']['diagnostic_only']=True
                set_authorization(p,name)
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];path=rd/'feedback_protocol.json';reused.immutable(path,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',case=name,after_maps=n)
                with reused.feedback_stop_guard():
                    if name=='control':
                        stable=zero_feedback(rd,p,path,state['history'][-2:]);result=pipeline.read(rd/'baseline_summary.json')
                    else:result=pair.run_pair(path,pipeline.sha256(path));verify_step21_pair(rd,p,result)
                reused.verify(list(p['sources'].values())+p['common_code_claims'])
                report={'diagnostic_only':True,'promoted':False,'feedback_evaluated':True,'original_gates':result['gate_checks'],'physical_response_failures':result.get('material_response_failures',{}),'pair_supported':False}
                if not report['physical_response_failures']:
                    vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                    if name=='control':
                        baseline[str(n)]=vectors
                        report['fresh_control_minus_r20_norms']=asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2']))
                        report['drift_is_error_bound']=False
                        report['baseline_stable']=stable
                    else:
                        report['fresh_baseline_comparison']=cross_comparisons(vectors,baseline[str(n)],old['cell_mass_g_cm2'])
                        report['pair_supported']=all_pair_gates(result) and report['fresh_baseline_comparison']['passed']
                case_reports[str(n)]=report;reused.immutable(rd/'decision.json',report);reused.archive(out,name+f'-map{n:02d}-feedback')
                if report['physical_response_failures']:reports[name]=case_reports;return 'physical_domain_rejected'
                if name=='control' and not stable:
                    reports[name]=case_reports;return 'baseline_unstable'
                # 原门失败只记录，固定物质精度预算不因此变成物质接受。
            reports[name]=case_reports
            return 'baseline_stable' if name=='control' else 'diagnostic_budget_complete'
        with relay_dispatch():terminal=direction_sequence(evaluate)
        reused.verify(plan['claims']+plan['code']);reused.immutable(out/'summary.json',{'status':terminal,'cases':reports,'diagnostic_only':True,'accepted_outer_steps':20,'new_material_steps':0})
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
