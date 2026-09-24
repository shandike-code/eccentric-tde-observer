"""Fresh x20 control followed by one bounded half-amplitude directional probe."""
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
PRIOR='outputs/hpc/common-step21-20260924'
BASE='outputs/hpc/common-confirmation20-20260924/confirm2'
SOURCE=PRIOR
ALPHAS={'control':0.,'half':1/256}
LIMITS={'control':4,'half':8}
CONTRACTION={'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass','candidate_maximum_cell_contraction_pass'}


def exact_trial(trial,base,r,old,alpha):
    if alpha not in ALPHAS.values() or float(trial['relaxation'])!=alpha:raise ValueError('undeclared amplitude')
    if float(base['relaxation'])!=0 or not np.array_equal(base['encoded_state'],base['base_encoded_state']):raise ValueError('not zero base')
    if not np.array_equal(base['base_residual'],r) or not np.array_equal(base['finite_direction'],r):raise ValueError('base denominator changed')
    for k,v in [('base_encoded_state',base['encoded_state']),('base_residual',r),('finite_direction',r),('encoded_state',base['encoded_state']+alpha*r)]:
        if not np.array_equal(trial[k],v):raise ValueError('trial identity changed: '+k)
    for k in ('density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(trial[k],base[k]):raise ValueError('physical identity changed: '+k)
    phase=int(trial['phase_index'])
    if not np.array_equal(trial['density_g_cm3'],old['density_g_cm3'][phase]) or float(trial['step_duration_s'])!=float(old['step_duration_s'][phase]):raise ValueError('physical old layer changed')
    codec=GroundStateLogSimplexCodec(len(trial['temperature_k']));decoded=codec.decode(trial['encoded_state'])
    for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        if not np.array_equal(trial[k],getattr(decoded,k)):raise ValueError('native decode changed: '+k)
    if not ground_state_material_trial_within_trust_region(codec,base['encoded_state'],trial['encoded_state'],maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,maximum_population_fraction_change=.05):raise ValueError('trust region failed')


def make_trial(base,r,old,alpha):
    if alpha not in ALPHAS.values():raise ValueError('undeclared amplitude')
    t={k:np.array(v,copy=True) for k,v in base.items()};t.update(encoded_state=base['encoded_state']+alpha*r,relaxation=np.array(alpha))
    if alpha:
        d=GroundStateLogSimplexCodec(len(t['temperature_k'])).decode(t['encoded_state'])
        for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):t[k]=np.array(getattr(d,k))
    exact_trial(t,base,r,old,alpha);return t


def permits_smaller(report):
    """Only resolved, physical contraction rejection permits the second amplitude."""
    from operations.prepare_half_step_after_audit import REQUIRED_GATES
    if not report.get('feedback_evaluated') or report.get('physical_response_failures') or report.get('pair_supported'):return False
    gates=report.get('original_gates',{})
    return (set(gates)==REQUIRED_GATES and {k for k,v in gates.items() if v is not True}<=CONTRACTION
        and (not all(gates.values()) or not report['fresh_baseline_comparison']['passed']))


def amplitude_sequence(evaluate):
    if evaluate('control')!='baseline_stable':return 'stopped_at_control'
    result=evaluate('half')
    if result=='supported':return 'half_supported_requires_review'
    if result=='contraction_rejected':return 'half_rejected_requires_direction_review'
    return 'stopped_at_half'


def control_allows_probe(stable,report):
    return bool(stable and not report.get('physical_response_failures') and
                report['prior_rejected_candidates']['pair08']['passed'] is False)


def validate_failure_audit(audit,terminal):
    if terminal['job_id']!=76808 or terminal['state']!='COMPLETED' or audit['accepted_outer_steps']!=20:raise RuntimeError('source audit missing')
    if set(audit['pairs'])!={'pair04','pair08'}:raise RuntimeError('incomplete audit')
    gates=audit['pairs']['pair08']['gate_checks']
    from operations.prepare_half_step_after_audit import REQUIRED_GATES
    if set(gates)!=REQUIRED_GATES or {k for k,v in gates.items() if not v}!={'candidate_maximum_cell_contraction_pass'}:raise RuntimeError('failure mechanism changed')
    if audit['pairs']['pair08']['fresh_baseline_comparison']['passed']:raise RuntimeError('failure comparison changed')


def zero_feedback(folder,p,path,history):
    sha=pipeline.sha256(path);feedbacks={};vectors={};failures={}
    for label in ('previous','final'):
        reused.checkpoint();m=pair._run_feedback_state(p,path,sha,label)
        if (m['status']!='complete' or not m['state_gate_passed'] or m['protocol_sha256']!=sha
            or m['state_sha256']!=p['sources'][label+'_radiation']['sha256']):
            raise RuntimeError('zero control feedback gate/lineage failed')
        f=folder/(label+'_feedback.npz')
        if pipeline.sha256(f)!=m['feedback_artifact_sha256']:raise RuntimeError('zero feedback bytes changed')
        feedbacks[label]=load_arrays(f)
        try:_,vectors[label],_=pair._material_response_residual(p,feedbacks[label])
        except pair.PhysicalDomainError as exc:failures[label]={'error':str(exc)}
    comparison=pair._feedback_stability_comparison(feedbacks['previous'],feedbacks['final'])
    gates=pair._feedback_stability_gate_checks(comparison,p['acceptance_gates'])
    gates.update(inner_pair_ready=bool(pipeline.pair_ready(history,1e-4)),physical_response_pass=not failures)
    if not failures:np.save(folder/'material_residual.npy',vectors['final'])
    result={'gate_checks':gates,'comparison':comparison,'material_response_failures':failures,
        'decision':{'baseline_control_only':True,'finite_trial_accepted_as_one_nonlinear_step':False,
                    'accept_dynamic_nlte_solution':False},'protocol_sha256':sha}
    reused.immutable(folder/'baseline_summary.json',result)
    verify_step21_pair(folder,p,result)
    return all(gates.values())


def prepare(out):
    audit_path=ROOT/'handoff/evidence/20260925-common-step21-review.json';audit=pipeline.read(audit_path)
    terminal_path=ROOT/'handoff/evidence/20260925-step21-76808-terminal.json';terminal=pipeline.read(terminal_path)
    validate_failure_audit(audit,terminal)
    reused.verify([audit['archive']])
    with tarfile.open(ROOT/audit['archive']['path']) as archive:
        inventory={c['path']:c for c in json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    claims=[pipeline.claim(audit_path),pipeline.claim(terminal_path)]
    for name in ('maps/trial_material.npz','maps/config.json','inputs/outer_base_material.npz','inputs/base_residual.npy','inputs/feedback_reference.json','pair04/feedback_summary.json','pair04/previous_response.npz','pair04/final_response.npz','pair08/feedback_summary.json','pair08/feedback_protocol.json','pair08/previous_response.npz','pair08/final_response.npz'):
        c=pipeline.claim(ROOT/PRIOR/name);expected=inventory[name]
        if any(c[k]!=expected[k] for k in ('size_bytes','sha256')):raise RuntimeError('reviewed bytes changed')
        claims.append(c)
    observed=pipeline.read(ROOT/PRIOR/'pair08/feedback_protocol.json')
    reference=pipeline.read(ROOT/SOURCE/'inputs/feedback_reference.json')
    for k in ('outer_base_material','base_residual','physical_old_time_level'):
        if reference['sources'][k]!=observed['sources'][k]:raise RuntimeError('baseline reference changed')
    s=reference['sources'];base=load_arrays(ROOT/s['outer_base_material']['path']);r=np.load(ROOT/s['base_residual']['path'],allow_pickle=False);old=load_arrays(ROOT/s['physical_old_time_level']['path'])
    validate_zero(base,base,r,old);validate_base_against_accepted(base,load_arrays(ROOT/BASE/'trial_material.npz'))
    acceptance_path=ROOT/'handoff/evidence/20260924-accepted-step20.json';acceptance=pipeline.read(acceptance_path)
    validate_acceptance(acceptance,pipeline.read(ROOT/'handoff/evidence/20260924-confirmation20-76727-terminal.json'))
    reused.verify(acceptance['claims']);claims.append(pipeline.claim(acceptance_path))
    if not np.array_equal(r,load_arrays(ROOT/BASE/'common-feedback/final_response.npz')['residual']):raise RuntimeError('fixed r20 differs')
    seed=latest_seed(pipeline.read(ROOT/BASE/'state.json'));claims+=[seed]+list(s.values())
    claims+=[pipeline.claim(ROOT/BASE/f) for f in ('state.json','config.json','trial_material.npz')]
    inputs=out/'inputs';inputs.mkdir();cases={}
    for name,alpha in ALPHAS.items():
        folder=inputs/name;folder.mkdir();t=make_trial(base,r,old,alpha);np.savez(folder/'trial_material.npz',**t)
        cfg=deepcopy(pipeline.read(ROOT/BASE/'config.json'));cfg['candidate_relaxation']=alpha;pipeline.write_json(folder/'config.json',cfg)
        cases[name]={'trial':pipeline.claim(folder/'trial_material.npz'),'config':pipeline.claim(folder/'config.json')}
        check=deepcopy(reference);check['sources']['trial_material']=cases[name]['trial'];native_identity(check)
        exact_trial(load_arrays(folder/'trial_material.npz'),base,r,old,alpha)
        claims+=list(cases[name].values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/common_step21_probe.sbatch','tests/test_common_step21_probe.py','handoff/protocols/common-step21-probe-v1.md')]
    plan={'cases':cases,'seed':seed,'claims':claims,'code':code,'alphas':ALPHAS,'limits':LIMITS,'maximum_maps':12,'maximum_feedback_pairs':3,'accepted_outer_steps':20,'automatic_promotion':False,'physical_dt_changed':False,'environment':pipeline.environment()}
    reused.verify(claims+code);reused.immutable(out/'declaration.json',plan)
    return plan,reference,base,r,old


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage must be disabled')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<17*pipeline.STATE_BYTES:raise RuntimeError('checkpoint disk budget insufficient')
        plan,reference,base,r,old=prepare(out);reused.LIMITS=LIMITS.copy();reports={};baseline={};seeds={'control':plan['seed']}
        def evaluate(name):
            mark('mapping',case=name,budget=LIMITS[name]);folder,cfg,state=reused.child(out,name,name,seeds[name],plan);case_reports={}
            for _ in range(LIMITS[name]):
                reused.checkpoint()
                if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
                if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('mapping resource/fault state')
                n=len(state['history']);mark('mapping',case=name,completed_maps=n,budget=LIMITS[name])
                if n not in (4,8):continue
                if not pipeline.pair_ready(state['history'],1e-4):
                    case_reports[str(n)]={'feedback_evaluated':False,'inner_pair_ready':False};reused.archive(out,name+f'-map{n:02d}-inner-not-ready');continue
                retain_pair(folder,state);retained=pipeline.read(folder/f'endpoints-map{n:02d}/manifest.json');rd=folder/f'pair{n:02d}';rd.mkdir()
                p=fresh.new_protocol(reference,rd,retained['endpoints'],retained['history_rows'],16);p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz')
                p['sources']['retained_manifest']=pipeline.claim(folder/f'endpoints-map{n:02d}/manifest.json')
                p['numerical_backtracking']={'alpha':ALPHAS[name],'fixed_base_accepted_index':20,'fixed_direction':'r20','physical_time_advanced':False}
                exact_trial(load_arrays(folder/'trial_material.npz'),base,r,old,ALPHAS[name]);native_identity(p)
                if name=='control':
                    p['classification']='zero displacement baseline; finite-step acceptance forbidden'
                    p['authorization'].update(accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass=False,accept_finite_trial_only_if_all_acceptance_gates_pass=False,accept_material_step=False,zero_displacement_control=True)
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];path=rd/'feedback_protocol.json';reused.immutable(path,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',case=name,after_maps=n)
                with reused.feedback_stop_guard():
                    if name=='control':
                        stable=zero_feedback(rd,p,path,state['history'][-2:]);result=pipeline.read(rd/'baseline_summary.json')
                    else:result=pair.run_pair(path,pipeline.sha256(path));verify_step21_pair(rd,p,result)
                reused.verify(list(p['sources'].values())+p['common_code_claims'])
                report={'feedback_evaluated':True,'original_gates':result['gate_checks'],'physical_response_failures':result.get('material_response_failures',{}),'pair_supported':False}
                if not report['physical_response_failures']:
                    vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                    if name=='control':
                        baseline.update(vectors)
                        report['fresh_control_minus_r20_norms']=asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2']))
                        report['drift_is_error_bound']=False
                        report['prior_rejected_candidates']={}
                        for prior in ('pair04','pair08'):
                            v={e:load_arrays(ROOT/PRIOR/prior/(e+'_response.npz'))['residual'] for e in vectors}
                            report['prior_rejected_candidates'][prior]=cross_comparisons(v,vectors,old['cell_mass_g_cm2'])
                    else:
                        report['fresh_baseline_comparison']=cross_comparisons(vectors,baseline,old['cell_mass_g_cm2'])
                        report['pair_supported']=all_pair_gates(result) and report['fresh_baseline_comparison']['passed']
                case_reports[str(n)]=report;reused.immutable(rd/'decision.json',report);reused.archive(out,name+f'-map{n:02d}-feedback')
                if report['physical_response_failures']:reports[name]=case_reports;return 'physical_domain_rejected'
                if name=='control':
                    reports[name]=case_reports
                    if control_allows_probe(stable,report):
                        seeds['half']=latest_seed(state)
                        return 'baseline_stable'
                    return 'baseline_unstable'
                if n==8 and report['pair_supported']:reports[name]=case_reports;return 'supported'
            reports[name]=case_reports
            return 'contraction_rejected' if permits_smaller(case_reports.get('8',{})) else 'unresolved_or_other_rejection'
        with relay_dispatch():terminal=amplitude_sequence(evaluate)
        reused.verify(plan['claims']+plan['code']);reused.immutable(out/'summary.json',{'status':terminal,'cases':reports,'accepted_outer_steps':20,'new_material_steps':0})
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
