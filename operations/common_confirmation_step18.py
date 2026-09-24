"""Fresh baseline and two same-trial confirmations of the supported half-amplitude step18."""
import argparse
from copy import deepcopy
import json
import os
import shutil
import signal
import tarfile
import time
import numpy as np
from operations import common_native_feedback as fresh
from operations.common_confirmation_batch import all_pair_gates,validate_zero,cross_comparisons,sequence,native_identity,LIMITS
from operations.common_outer_step18 import verify_step18_pair
from operations.common_step18_backtrack import exact_trial
from operations.constrained_hybrid_batch import relay_dispatch
from diagnostics import interval_diagnostic as driver
from eccentric_tde_observer.coupled_material_newton_krylov import ground_state_material_trial_within_trust_region
pipeline=fresh.pipeline;pair=fresh.pair;reused=fresh.reused;ROOT=fresh.ROOT;load_arrays=fresh.load_arrays
PRIOR='outputs/hpc/common-step18-backtrack-20260924'
CONTROL='outputs/hpc/common-confirmation17-20260924/confirm2'


def confirmation_protocol(reference,folder,endpoints,rows,trial_claim,is_control):
    p=fresh.new_protocol(reference,folder,endpoints,rows,16)
    # 原回溯端点清单属于祖先，不可标成这次确认的端点。
    p['sources'].pop('retained_manifest',None)
    p['sources']['trial_material']=trial_claim
    p['numerical_backtracking']={'alpha':0. if is_control else 1/128,
        'fixed_base_accepted_index':17,'fixed_direction':'r17','physical_time_advanced':False}
    return p


def validate_base_against_accepted(base,accepted):
    # 元数据可由第17步试探重置为第18步零控制，物理物质和encoded本身不可改。
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g',
              'density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(base[k],accepted[k]):raise RuntimeError('zero control not accepted x17: '+k)


def latest_seed(state):
    if state.get('active_map') or state.get('pending_feedback'):raise RuntimeError('source radiation unsettled')
    row=state['history'][-1]
    if state['current_sha256']!=row['output_sha256'] or state['slots'][state['current_slot']]!=row['output_path']:raise RuntimeError('latest seed mismatch')
    return {'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES}


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
    verify_step18_pair(folder,p,result)
    return all(gates.values())



def prepare(out):
    review_path=ROOT/'handoff/evidence/20260924-common-step18-backtrack-review.json';review=pipeline.read(review_path)
    if review['accepted_outer_steps']!=17 or not review['pairs']['half08']['all_16_pair_gates']:raise RuntimeError('Mac candidate audit missing')
    if pipeline.read(ROOT/PRIOR/'status.json')['status']!='half_supported_requires_review':raise RuntimeError('candidate not supported')
    terminal=pipeline.read(ROOT/'handoff/evidence/20260924-step18-backtrack-76434-terminal.json')
    if terminal['job_id']!=76434 or terminal['state']!='COMPLETED':raise RuntimeError('source scheduler failure')
    receipt=review['archive'];reused.verify([receipt])
    with tarfile.open(ROOT/receipt['path']) as archive:
        inventory={c['path']:c for c in json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    claims=[pipeline.claim(review_path),pipeline.claim(ROOT/'handoff/evidence/20260924-step18-backtrack-76434-terminal.json')]
    for relative in ('half/trial_material.npz','half/config.json','half/state.json',
                     'control/state.json','control/config.json','control/trial_material.npz',
                     'half/pair08/feedback_protocol.json','half/pair08/feedback_summary.json',
                     'half/pair08/previous_response.npz','half/pair08/final_response.npz',
                     'half/endpoints-map08/manifest.json'):
        actual=pipeline.claim(ROOT/PRIOR/relative);expected=inventory[relative]
        if any(actual[k]!=expected[k] for k in ('sha256','size_bytes')):raise RuntimeError('candidate differs from audited archive')
        claims.append(actual)
    summary=pipeline.read(ROOT/PRIOR/'half/pair08/feedback_summary.json')
    if not all_pair_gates(summary) or summary['comparison']!=review['pairs']['half08']['comparison']:raise RuntimeError('source gate mismatch')
    if not review['pairs']['half08']['fresh_baseline_comparison']['passed']:raise RuntimeError('fresh control comparison failed')
    observed=pipeline.read(ROOT/PRIOR/'half/pair08/feedback_protocol.json')
    reference_path=ROOT/'outputs/hpc/common-step18-20260924/inputs/feedback_reference.json'
    reference=pipeline.read(reference_path);sources=reference['sources'];claims.append(pipeline.claim(reference_path))
    # 从原模板建新协议，避免把共同域包装器误记成祖先legacy adapter。
    for key in ('outer_base_material','base_residual','physical_old_time_level'):
        if sources[key]!=observed['sources'][key]:raise RuntimeError('original reference provenance changed')
    base=load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
    old=load_arrays(ROOT/sources['physical_old_time_level']['path']);trial=load_arrays(ROOT/PRIOR/'half/trial_material.npz')
    exact_trial(trial,base,r,old,1/128);validate_zero(base,base,r,old)
    accepted=load_arrays(ROOT/CONTROL/'trial_material.npz')
    # 仅零控制的迭代元数据改变；真正进入native的物理物质必须等于已接受x17。
    validate_base_against_accepted(base,accepted)
    codec=pair.GroundStateLogSimplexCodec(128)
    if not ground_state_material_trial_within_trust_region(codec,base['encoded_state'],trial['encoded_state'],
        maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,maximum_population_fraction_change=.05):raise RuntimeError('trust region failed')
    acceptance=pipeline.read(ROOT/'handoff/evidence/20260924-accepted-step17.json');reused.verify(acceptance['claims'])
    if acceptance['accepted_outer_steps']!=17:raise RuntimeError('step17 is not accepted')
    claims.append(pipeline.claim(ROOT/'handoff/evidence/20260924-accepted-step17.json'))
    state=pipeline.read(ROOT/PRIOR/'control/state.json');cfg=pipeline.read(ROOT/PRIOR/'control/config.json')
    if state['config_sha256']!=pipeline.sha256(ROOT/PRIOR/'control/config.json'):raise RuntimeError('base config mismatch')
    seeds={'control':latest_seed(state),'confirm1':pipeline.read(ROOT/PRIOR/'half/endpoints-map08/manifest.json')['endpoints']['mapped_final']}
    claims+=list(seeds.values())+[pipeline.claim(ROOT/CONTROL/f) for f in ('state.json','config.json','trial_material.npz','common-feedback/final_response.npz')]
    if not np.array_equal(r,load_arrays(ROOT/CONTROL/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r17 changed')
    claims+=[sources[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]
    # 私有输入只含trial/config，不伪造一个已经计算过的零控制state。
    prepared=out/'inputs/base';prepared.mkdir(parents=True)
    np.savez(prepared/'trial_material.npz',**base);validate_zero(load_arrays(prepared/'trial_material.npz'),base,r,old)
    cfg=deepcopy(cfg);cfg['candidate_relaxation']=0.;pipeline.write_json(prepared/'config.json',cfg)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/common_confirmation_step18.sbatch',
        'tests/test_common_confirmation_step18.py','handoff/protocols/common-confirmation-step18-v1.md')]
    plan={'cases':{'base':{'trial':pipeline.claim(prepared/'trial_material.npz'),'config':pipeline.claim(prepared/'config.json')},
        'trial':{'trial':pipeline.claim(ROOT/PRIOR/'half/trial_material.npz'),'config':pipeline.claim(ROOT/PRIOR/'half/config.json')}},
        'code':code,'claims':claims,'seeds':seeds,'limits':LIMITS,'maximum_new_maps':8,'maximum_feedback_pairs':3,
        'accepted_outer_steps':17,'automatic_promotion':False,'physical_dt_changed':False,'environment':pipeline.environment()}
    for label,alpha in (('base',0.),('trial',1/128)):
        check=deepcopy(reference);check['sources']['trial_material']=plan['cases'][label]['trial']
        exact_trial(load_arrays(ROOT/check['sources']['trial_material']['path']),base,r,old,alpha)
        native_identity(check)
    claims+=list(plan['cases']['base'].values());reused.verify(claims+code)
    reused.immutable(out/'declaration.json',plan)
    return plan,reference,base,r,old


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage must be disabled')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,updated_unix=time.time(),accepted_outer_steps=17,new_material_steps=0,**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('checkpoint budget')
        plan,reference,base,r,old=prepare(out);claims=plan['claims'];code=plan['code'];seeds=plan['seeds']
        reused.LIMITS=LIMITS.copy();reports={};base_vectors={}
        def evaluate(name,count):
            reused.checkpoint();mark('mapping',case=name,budget=count)
            label='base' if name=='control' else 'trial'
            folder,cfg,s=reused.child(out,name,label,seeds[name],plan)
            for _ in range(count):
                reused.checkpoint()
                if not driver.run_one_map(folder,cfg,s,folder/'state.json'):raise reused.Stopped('partial map retained')
                if s['status'] in driver.FAULT_STATUSES:raise RuntimeError('mapping fault')
                mark('mapping',case=name,completed_maps=len(s['history']),budget=count)
            if len(s['history'])!=count:raise RuntimeError('map budget mismatch')
            rows=s['history'][-2:];endpoints={e:{'path':v['input_path'],'sha256':v['input_sha256'],'size_bytes':pipeline.STATE_BYTES}
                for e,v in zip(('previous','final'),rows)}
            # 此child到此不再写入，三槽保留两个已测输入与最新后继，下一确认另建child。
            rd=folder/'common-feedback';rd.mkdir()
            p=confirmation_protocol(reference,rd,endpoints,rows,pipeline.claim(folder/'trial_material.npz'),name=='control')
            if name=='control':
                p['classification']='zero-displacement baseline only; finite-step acceptance forbidden'
                p['authorization'].update(accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass=False,
                    accept_finite_trial_only_if_all_acceptance_gates_pass=False,
                    accept_material_step=False,zero_displacement_control=True)
                validate_zero(load_arrays(folder/'trial_material.npz'),base,r,old)
            else:exact_trial(load_arrays(folder/'trial_material.npz'),base,r,old,1/128)
            native_identity(p);fresh.attach_code(p);p['common_code_claims']+=code
            path=rd/'feedback_protocol.json';reused.immutable(path,p)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',case=name)
            with reused.feedback_stop_guard():
                if name=='control':passed=zero_feedback(rd,p,path,rows)
                else:
                    result=pair.run_pair(path,pipeline.sha256(path));verify_step18_pair(rd,p,result)
                    passed=all_pair_gates(result) and not result.get('material_response_failures')
            reused.verify(list(p['sources'].values())+p['common_code_claims'])
            report={'physics_pair_passed':passed,'promoted':False}
            if passed:
                vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                if name=='control':
                    base_vectors.update(vectors);report['prior_candidates']={}
                    for prior in ('pair08',):
                        v={e:load_arrays(ROOT/PRIOR/'half'/prior/(e+'_response.npz'))['residual'] for e in vectors}
                        report['prior_candidates'][prior]=cross_comparisons(v,vectors,old['cell_mass_g_cm2'])
                    passed=all(v['passed'] for v in report['prior_candidates'].values())
                else:
                    report['fresh_baseline_comparison']=cross_comparisons(vectors,base_vectors,old['cell_mass_g_cm2'])
                    passed=report['fresh_baseline_comparison']['passed']
            report['continue']=passed;reports[name]=report;reused.immutable(folder/'decision.json',report)
            if name=='confirm1' and passed:
                row=s['history'][-1];seeds['confirm2']={'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES}
            reused.archive(out,name+'-complete');return passed
        with relay_dispatch():status=sequence(evaluate)
        reused.verify(claims+code);reused.immutable(out/'summary.json',{'status':status,'cases':reports,'accepted_outer_steps':17,'new_material_steps':0})
        mark(status);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
