"""Bounded step 21 from the independently confirmed common-domain step 20.

The postcheck body is retained from common_native_feedback (48fbed7 lineage);
Its explicit accepted-step counter is now 20; historical functions stay frozen.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import signal
import tarfile
import time
import numpy as np
from operations import common_native_feedback as fresh
from operations import common_feedback_bridge as bridge
from operations.common_confirmation_batch import cross_comparisons,all_pair_gates,native_identity
from operations.common_step18_backtrack import exact_trial
from operations.common_precision_maps import retain_pair
from operations.second_outer_step import rebase_trial
from operations.constrained_hybrid_batch import relay_dispatch
from diagnostics import interval_diagnostic as driver
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec,ground_state_material_trial_within_trust_region
pipeline=fresh.pipeline;pair=fresh.pair;reused=fresh.reused;ROOT=fresh.ROOT;load_arrays=fresh.load_arrays
SOURCE='outputs/hpc/common-confirmation20-20260924'
ACCEPTANCE='handoff/evidence/20260924-accepted-step20.json'


def validate_acceptance(record,terminal):
    if (record['accepted_outer_steps']!=20 or record['previous_accepted_outer_steps']!=19
        or record['accepted_target_is_response'] or record['coupled_column_converged']
        or record['physical_time_advanced'] or record['job_id']!=76727
        or record['candidate']!=SOURCE+'/confirm2/trial_material.npz'
        or terminal['job_id']!=76727 or terminal['state']!='COMPLETED'):
        raise RuntimeError('invalid independently confirmed step20 provenance')


def make_candidate(base,residual):
    if float(base['relaxation'])!=0 or not np.array_equal(base['encoded_state'],base['base_encoded_state']):raise ValueError('not a zero baseline')
    if not np.array_equal(base['base_residual'],residual) or not np.array_equal(base['finite_direction'],residual):raise ValueError('direction/denominator mismatch')
    codec=GroundStateLogSimplexCodec(len(base['temperature_k']));x=base['encoded_state']+residual/128
    if not ground_state_material_trial_within_trust_region(codec,base['encoded_state'],x,
        maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,
        maximum_population_fraction_change=.05):raise ValueError('step21 outside unchanged trust region')
    d=codec.decode(x);t={k:np.array(v,copy=True) for k,v in base.items()}
    for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):t[k]=np.array(getattr(d,k))
    t.update(encoded_state=x,relaxation=np.array(1/128));return t


def verify_step21_pair(out,p,result):
    responses={};t=load_arrays(ROOT/p['sources']['trial_material']['path']);old=load_arrays(ROOT/p['sources']['physical_old_time_level']['path']);phase=int(t['phase_index'])
    for label in ('previous','final'):
        m=pipeline.read(out/'feedback'/f'{label}_manifest.json');fb=load_arrays(out/f'{label}_feedback.npz');ownership=np.zeros(9632,int)
        receipts=[]
        for row in m['completed_blocks']:
            reused.verify([row['legacy_partial'],row['legacy_report'],row['common_arrays']])
            raw=load_arrays(ROOT/row['legacy_partial']['path']);common=load_arrays(ROOT/row['common_arrays']['path']);a=load_arrays(ROOT/row['partial_path'])
            if row['partial_sha256']!=pipeline.sha256(ROOT/row['partial_path']):raise RuntimeError('new partial changed')
            if set(a)!=set(raw) or any(not np.array_equal(a[k],common['common_formal_erg_s_cm3'] if k==bridge.FORMAL else raw[k]) for k in a):raise RuntimeError('worker field substitution differs')
            ownership[row['core_group_start']:row['core_group_stop']]+=1
            paths=list((out/'feedback'/label).glob(f"block{row['block_index']:02d}.process-*.json"))
            if len(paths)!=1:raise RuntimeError('ambiguous process receipt')
            q=pipeline.read(paths[0]);receipts.append(q)
            if q['returncode']!=0 or not q['memory_guard_passed']:raise RuntimeError('independent memory/process gate failed')
        checks,*_=bridge.state_checks(fb,m['completed_blocks'],ownership,m['accumulated_wall_runtime_s'],m['maximum_process_peak_rss_mib'],p['formal_state_gates'])
        if not all(checks.values()) or not m['state_gate_passed']:raise RuntimeError('full state postcheck failed')
        book=bridge.ledger(fb,t['density_g_cm3'],float(t['step_duration_s']),old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
        np.savez(out/f'{label}_energy_ledger.npz',**book)
        responses[label]={'minimum_gas_erg_g':float(book['remaining'].min()),'failed_gas_cells':int(np.count_nonzero(book['remaining']<=0)),
            'full_state_checks':checks,'maximum_native_mib':m['maximum_process_peak_rss_mib'],
            'maximum_proc_kib':max(q['native_observed_peak_kib'] for q in receipts),'state_wall_s':m['accumulated_wall_runtime_s']}
        if label not in result.get('material_response_failures',{}):
            response,v,ctx=pair._material_response_residual(p,fb);bridge.verify_response_ledger(book,response)
            np.savez(out/f'{label}_response.npz',residual=v,temperature_k=response.temperature_k,hydrogen_fraction=response.hydrogen_fraction,
                helium_fraction=response.helium_fraction,target_specific_material_energy_erg_g=response.target_specific_material_energy_erg_g)
            responses[label]['norms']=asdict(bridge.encoded_residual_norms(v,ctx['cell_mass']))
            if label=='final' and not result.get('material_response_failures') and not np.array_equal(v,np.load(out/'material_residual.npy')):raise RuntimeError('response replay mismatch')
    report={'responses':responses,'gate_checks':result['gate_checks'],'comparison':result['comparison'],
        'material_response_failures':result.get('material_response_failures',{}),'pair_decision':result['decision'],
        'accepted_outer_steps_remain':20,'material_step_promoted':False,'frequency_truncation_convergence_established':False}
    reused.immutable(out/'postcheck.json',report);return report


def prepare(out):
    acceptance=pipeline.read(ROOT/ACCEPTANCE)
    terminal_path=ROOT/'handoff/evidence/20260924-confirmation20-76727-terminal.json'
    validate_acceptance(acceptance,pipeline.read(terminal_path))
    reused.verify(acceptance['claims'])
    review=pipeline.read(ROOT/'handoff/evidence/20260924-common-confirmation20-review.json')
    receipt=review['archive'];reused.verify([receipt])
    with tarfile.open(ROOT/receipt['path']) as archive:
        inventory={c['path']:c for c in json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    # 新base=x20本身，绝不把响应目标G(x20)偷当成已接受物质。
    source=ROOT/SOURCE/'confirm2';rd=source/'common-feedback'
    state=pipeline.read(source/'state.json');proto=pipeline.read(rd/'feedback_protocol.json')
    claims=[pipeline.claim(ROOT/ACCEPTANCE),pipeline.claim(terminal_path),pipeline.claim(ROOT/'handoff/evidence/20260924-common-confirmation20-review.json')]
    for case in ('control','confirm1','confirm2'):
        folder=ROOT/SOURCE/case
        for name in ('state.json','config.json','trial_material.npz','decision.json','common-feedback/feedback_protocol.json',
                     'common-feedback/previous_feedback.npz','common-feedback/final_feedback.npz',
                     'common-feedback/previous_response.npz','common-feedback/final_response.npz'):
            claim=pipeline.claim(folder/name);expected=inventory[case+'/'+name]
            if any(claim[k]!=expected[k] for k in ('sha256','size_bytes')):raise RuntimeError('source differs from reviewed archive')
            claims.append(claim)
        if not pipeline.read(folder/'decision.json')['continue']:raise RuntimeError('confirmation chain failed')
        if case!='control' and not all_pair_gates(pipeline.read(folder/'common-feedback/feedback_summary.json')):
            raise RuntimeError('source original pair gate failed')
    if state['active_map'] or len(state['history'])!=2:raise RuntimeError('unsettled confirmation')
    reused.verify(list(proto['sources'].values()))
    t=load_arrays(source/'trial_material.npz');old=load_arrays(ROOT/proto['sources']['physical_old_time_level']['path'])
    vectors={}
    for e in ('previous','final'):
        _,v,_=pair._material_response_residual(proto,load_arrays(rd/(e+'_feedback.npz')))
        if not np.array_equal(v,load_arrays(rd/(e+'_response.npz'))['residual']):raise RuntimeError('native response replay differs')
        vectors[e]=v
    r=vectors['final'];base=rebase_trial(t,r,old);trial=make_candidate(base,r)
    exact_trial(trial,base,r,old,1/128)
    inputs=out/'inputs';inputs.mkdir();np.savez(inputs/'outer_base_material.npz',**base)
    np.save(inputs/'base_residual.npy',r);np.savez(inputs/'trial_material.npz',**trial)
    reused.identical_material(trial,load_arrays(inputs/'trial_material.npz'))
    row=state['history'][-1]
    if row['output_sha256']!=state['current_sha256'] or row['output_path']!=state['slots'][state['current_slot']]:raise RuntimeError('wrong warm seed')
    seed={'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES};reused.verify([seed])
    cfg=deepcopy(pipeline.read(source/'config.json'));cfg['candidate_relaxation']=1/128
    pipeline.write_json(inputs/'config.json',cfg)
    reference=pipeline.read(ROOT/fresh.REFERENCE/'feedback_protocol.json')
    if reference['sources']['physical_old_time_level']!=proto['sources']['physical_old_time_level']:raise RuntimeError('physical layer changed')
    # 明示更换非线性基态及残差分母；物理旧层、dt和接受门不变。
    for k,file in [('trial_material','trial_material.npz'),('outer_base_material','outer_base_material.npz'),('base_residual','base_residual.npy')]:
        reference['sources'][k]=pipeline.claim(inputs/file)
    reference['outer_iteration']={'index':21,'base_accepted_index':20,'base_is_accepted_trial':True,
        'physical_time_advanced':False,'direction_is_latest_confirmed_response':True}
    exact_trial(load_arrays(inputs/'trial_material.npz'),base,r,old,1/128)
    native_identity(reference)
    reused.immutable(inputs/'feedback_reference.json',reference)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/common_outer_step21.sbatch',
        'tests/test_common_outer_step21.py','handoff/protocols/common-outer-step21-v1.md')]
    claims+=[seed]+[pipeline.claim(p) for p in inputs.iterdir()]
    reused.verify(claims+code)
    plan={'cases':{'trial':{'trial':pipeline.claim(inputs/'trial_material.npz'),'config':pipeline.claim(inputs/'config.json')}},
        'seed':seed,'code':code,'claims':claims,'environment':pipeline.environment(),'accepted_outer_steps':20,
        'maximum_new_maps':8,'maximum_feedback_pairs':2,'feedback_after_maps':[4,8],
        'new_step_index':21,'alpha':1/128,'automatic_promotion':False,'physical_dt_changed':False}
    reused.immutable(out/'declaration.json',plan)
    return plan,reference,vectors,old['cell_mass_g_cm2']


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage must be disabled')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('retained checkpoint space insufficient')
        plan,reference,base_vectors,mass=prepare(out);reused.LIMITS={'maps':8};reports={}
        with relay_dispatch():
            folder,cfg,state=reused.child(out,'maps','trial',plan['seed'],plan)
            for _ in range(8):
                reused.checkpoint();mark('mapping',completed_maps=len(state['history']))
                if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
                if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('map resource failure')
                n=len(state['history'])
                if n not in (4,8):continue
                retain_pair(out,state);retained=pipeline.read(out/f'endpoints-map{n:02d}/manifest.json')
                if not pipeline.pair_ready(state['history'],1e-4):
                    reports[str(n)]={'inner_pair_ready':False,'feedback_evaluated':False}
                    reused.archive(out,f'map{n:02d}-inner-not-ready');continue
                rd=out/f'pair{n:02d}';rd.mkdir()
                p=fresh.new_protocol(reference,rd,retained['endpoints'],retained['history_rows'],16)
                p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz')
                p['sources']['retained_manifest']=pipeline.claim(out/f'endpoints-map{n:02d}/manifest.json')
                fresh.attach_code(p);p['common_code_claims']+=plan['code']
                exact_trial(load_arrays(folder/'trial_material.npz'),load_arrays(ROOT/p['sources']['outer_base_material']['path']),np.load(ROOT/p['sources']['base_residual']['path'],allow_pickle=False),load_arrays(ROOT/p['sources']['physical_old_time_level']['path']),1/128)
                native_identity(p)
                path=rd/'feedback_protocol.json';reused.immutable(path,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',after_maps=n)
                with reused.feedback_stop_guard():result=pair.run_pair(path,pipeline.sha256(path))
                post=verify_step21_pair(rd,p,result)
                report={'original_gates':result['gate_checks'],'all_original_gates':all_pair_gates(result),
                    'physical_response_failures':result.get('material_response_failures',{}),'postcheck':pipeline.claim(rd/'postcheck.json')}
                if not report['physical_response_failures']:
                    vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                    report['fresh_baseline_comparison']=cross_comparisons(vectors,base_vectors,mass)
                    report['pair_supported']=report['all_original_gates'] and report['fresh_baseline_comparison']['passed']
                reports[str(n)]=report;reused.immutable(rd/'decision.json',report)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'map{n:02d}-feedback')
                if report['physical_response_failures']:
                    terminal='physical_domain_rejected'
                    reused.immutable(out/'summary.json',{'status':terminal,'pairs':reports,'accepted_outer_steps':20,'new_material_steps':0})
                    mark(terminal,after_maps=n);reused.archive(out,'complete');return
        reused.verify(plan['claims']+plan['code'])
        supported=reports.get('8',{}).get('pair_supported',False)
        terminal='candidate_supported_requires_review' if supported else 'budget_complete_not_accepted'
        reused.immutable(out/'summary.json',{'status':terminal,'pairs':reports,'accepted_outer_steps':20,'new_material_steps':0})
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
