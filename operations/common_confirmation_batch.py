"""Fresh common-domain zero control, then two conditional same-trial confirmations."""
import argparse
from dataclasses import asdict
import json
import os
import shutil
import signal
import tarfile
import time
import numpy as np
from operations import common_native_feedback as fresh
from operations.constrained_hybrid_batch import relay_dispatch
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from diagnostics import interval_diagnostic as driver
from eccentric_tde_observer.coupled_material_newton_krylov import ground_state_material_trial_within_trust_region

pipeline=fresh.pipeline;pair=fresh.pair;reused=fresh.reused;ROOT=fresh.ROOT
load_arrays=fresh.load_arrays
CONTROL='outputs/hpc/step16-backtrack-20260923/control'
PRIOR='outputs/hpc/common-native-pairs-20260923'
LIMITS={'control':4,'confirm1':2,'confirm2':2}


def all_pair_gates(report):
    gates=report['gate_checks']
    return set(gates)==REQUIRED_GATES and all(v is True for v in gates.values())


def validate_zero(t,base,residual,old):
    """A zero control has no finite-step signal and must never be accepted as one."""
    reused.identical_material(t,base)
    if float(t['relaxation'])!=0 or not np.array_equal(t['encoded_state'],t['base_encoded_state']):
        raise RuntimeError('not the frozen zero control')
    if not np.array_equal(t['base_residual'],residual):raise RuntimeError('zero control baseline changed')
    phase=int(t['phase_index'])
    if (not np.array_equal(t['density_g_cm3'],old['density_g_cm3'][phase])
        or float(t['step_duration_s'])!=float(old['step_duration_s'][phase])):
        raise RuntimeError('zero control physical context changed')
    decoded=pair.GroundStateLogSimplexCodec(len(t['temperature_k'])).decode(t['encoded_state'])
    for k in ('temperature_k','hydrogen_fraction','helium_fraction'):
        if not np.array_equal(t[k],getattr(decoded,k)):raise RuntimeError('zero control decode differs')


def cross_comparisons(candidate,base,mass):
    """Compare both candidate endpoints against both fresh baseline endpoints."""
    if set(candidate)!={'previous','final'} or set(base)!={'previous','final'}:
        raise ValueError('four endpoint combinations required')
    result={}
    for a,x in candidate.items():
        for b,y in base.items():
            xn=asdict(fresh.bridge.encoded_residual_norms(x,mass))
            yn=asdict(fresh.bridge.encoded_residual_norms(y,mass))
            if any(not np.isfinite(v) or v<=0 for v in yn.values()):raise ValueError('invalid baseline norm')
            ratios={k:xn[k]/yn[k] for k in xn}
            if any(not np.isfinite(v) or v<0 for v in ratios.values()):raise ValueError('invalid contraction ratio')
            result[a+'_vs_'+b]=ratios
    return {'ratios':result,'passed':all(v<1 for r in result.values() for v in r.values())}


def sequence(evaluate):
    """Hard budget and fail-closed dependencies, independent of numerical workers."""
    for name in LIMITS:
        if not evaluate(name,LIMITS[name]):return 'stopped_at_'+name
    return 'confirmed_requires_mac_review'


def native_identity(p):
    t=load_arrays(ROOT/p['sources']['trial_material']['path'])
    adapted=pair.adapt_phase7b7j_worker_protocol(p,pair._validate_worker_template_sources(p),'final')
    ctx=fresh.native.phase7b7f.phase7b7e.phase7b5x._context(adapted)
    m=fresh.native.phase7b7i._second_full_material(adapted)
    for k,f in [('temperature_k','temperature_parent'),('hydrogen_fraction','hydrogen_parent'),
                ('helium_fraction','helium_parent'),('density_g_cm3','density_parent')]:
        if not np.array_equal(m[f],np.concatenate((t[k],t[k][::-1]))):raise RuntimeError('native material mismatch')
    if ctx['phase']!=int(t['phase_index']) or ctx['duration_s']!=float(t['step_duration_s']):raise RuntimeError('native time mismatch')


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
    fresh.verify_complete_pair(folder,p,result)
    return all(gates.values())


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage disabled required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,updated_unix=time.time(),accepted_outer_steps=15,new_material_steps=0,**kw))
    mark('preparing')
    try:
        review=pipeline.read(ROOT/'handoff/evidence/20260923-common-native-pairs-review.json')
        if review['accepted_outer_steps']!=15 or not all(v['all_16_pair_gates'] for v in review['pairs'].values()):raise RuntimeError('Mac review failed')
        receipt=review['archive'];reused.verify([receipt])
        with tarfile.open(ROOT/receipt['path']) as archive:
            inventory=json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))
        inventory={c['path']:c for c in inventory['files']}
        if pipeline.read(ROOT/PRIOR/'status.json')['status']!='complete_requires_baseline_and_confirmation':raise RuntimeError('prior job incomplete')
        terminal=pipeline.read(ROOT/'handoff/evidence/20260923-common-native-75987-terminal.json')
        if terminal['state']!='COMPLETED' or terminal['job_id']!=75987:raise RuntimeError('prior job not completed')
        reference=pipeline.read(ROOT/fresh.REFERENCE/'feedback_protocol.json')
        sources=reference['sources'];base=load_arrays(ROOT/sources['outer_base_material']['path'])
        old=load_arrays(ROOT/sources['physical_old_time_level']['path']);r=np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
        trial=load_arrays(ROOT/fresh.MAPS/'maps/trial_material.npz');control=load_arrays(ROOT/CONTROL/'trial_material.npz')
        fresh.bridge.validate_identity(trial,base,r,old);validate_zero(control,base,r,old)
        codec=pair.GroundStateLogSimplexCodec(128)
        if not ground_state_material_trial_within_trust_region(codec,base['encoded_state'],trial['encoded_state'],
            maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,
            maximum_population_fraction_change=.05):raise RuntimeError('original trust region failed')
        state=pipeline.read(ROOT/CONTROL/'state.json');cfg=pipeline.read(ROOT/CONTROL/'config.json')
        if state.get('active_map') or state.get('pending_feedback') or state['config_sha256']!=pipeline.sha256(ROOT/CONTROL/'config.json'):raise RuntimeError('baseline source unsettled')
        row=state['history'][-1]
        if state['current_sha256']!=row['output_sha256'] or state['slots'][state['current_slot']]!=row['output_path']:raise RuntimeError('control seed identity')
        seeds={'control':{'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES},
            'confirm1':pipeline.read(ROOT/fresh.MAPS/'endpoints-map08/manifest.json')['endpoints']['mapped_final']}
        code=fresh.code_claims()+[pipeline.claim(ROOT/f) for f in ('operations/common_confirmation_batch.sbatch',
            'tests/test_common_confirmation_batch.py','handoff/protocols/common-confirmation-v1.md')]
        claims=[pipeline.claim(ROOT/f) for f in (CONTROL+'/state.json',CONTROL+'/config.json',CONTROL+'/trial_material.npz',
            fresh.MAPS+'/maps/config.json',fresh.MAPS+'/maps/trial_material.npz',fresh.REFERENCE+'/feedback_protocol.json',
            'handoff/evidence/20260923-common-native-pairs-review.json','handoff/evidence/20260923-common-native-75987-terminal.json')]
        claims+=list(seeds.values())+[sources[k] for k in ('outer_base_material','trial_material','physical_old_time_level','base_residual')]
        for name in ('map04','map08'):
            folder=ROOT/PRIOR/name;s=pipeline.read(folder/'feedback_summary.json')
            if not all_pair_gates(s) or s['comparison']!=review['pairs'][name]['comparison']:raise RuntimeError('prior pair changed')
            for file in ('feedback_summary.json','feedback_protocol.json','previous_response.npz','final_response.npz'):
                actual=pipeline.claim(folder/file);prior=inventory[name+'/'+file]
                if actual['sha256']!=prior['sha256'] or actual['size_bytes']!=prior['size_bytes']:
                    raise RuntimeError('prior endpoint differs from Mac-reviewed archive')
                claims.append(actual)
        reused.verify(claims+code)
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('checkpoint disk budget')
        plan={'cases':{k:{'trial':pipeline.claim(ROOT/v/'trial_material.npz'),'config':pipeline.claim(ROOT/v/'config.json')}
                      for k,v in [('base',CONTROL),('trial',fresh.MAPS+'/maps')]},'code':code,'claims':claims,
            'seeds':seeds,'limits':LIMITS,'maximum_new_maps':8,'maximum_feedback_pairs':3,
            'original_base_residual_retained':sources['base_residual'],'environment':pipeline.environment(),
            'accepted_outer_steps':15,'automatic_promotion':False,'physical_dt_changed':False}
        reused.immutable(out/'declaration.json',plan);reused.LIMITS=LIMITS.copy();reports={};base_vectors={}
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
            rd=folder/'common-feedback';rd.mkdir();p=fresh.new_protocol(reference,rd,endpoints,rows,16)
            p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz')
            if name=='control':
                p['classification']='zero-displacement baseline only; finite-step acceptance forbidden'
                p['authorization'].update(accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass=False,
                    accept_finite_trial_only_if_all_acceptance_gates_pass=False,
                    accept_material_step=False,zero_displacement_control=True)
                validate_zero(load_arrays(folder/'trial_material.npz'),base,r,old)
            else:fresh.exact_identity(p)
            native_identity(p);fresh.attach_code(p);p['common_code_claims']+=code
            path=rd/'feedback_protocol.json';reused.immutable(path,p)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',case=name)
            with reused.feedback_stop_guard():
                if name=='control':passed=zero_feedback(rd,p,path,rows)
                else:
                    result=pair.run_pair(path,pipeline.sha256(path));fresh.verify_complete_pair(rd,p,result)
                    passed=all_pair_gates(result) and not result.get('material_response_failures')
            reused.verify(list(p['sources'].values())+p['common_code_claims'])
            report={'physics_pair_passed':passed,'promoted':False}
            if passed:
                vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                if name=='control':
                    base_vectors.update(vectors);report['prior_candidates']={}
                    for prior in ('map04','map08'):
                        v={e:load_arrays(ROOT/PRIOR/prior/(e+'_response.npz'))['residual'] for e in vectors}
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
        reused.verify(claims+code);reused.immutable(out/'summary.json',{'status':status,'cases':reports,'accepted_outer_steps':15,'new_material_steps':0})
        mark(status);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
