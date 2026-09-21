"""One bounded A -> B -> C allocation; immutable inputs and eight-map hard cap."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
import pipeline
from diagnostics import interval_diagnostic as driver
from operations import paired_block_krylov as local
from operations.composite_hybrid_audit import GATES, hybrid, audit, checks
from operations.prepare_extension_run import carry_trial
from operations.prepare_encoded_backtrack import load_arrays,audit_native_trial
from operations.radiation_history_diagnostic import identical_material
from operations.validate_half_history_candidate import initialized_identity
from operations.review_small_step_evidence import Snapshot
from scripts import phase7b9_formal_feedback_pair_adapter as pair

PILOT='outputs/hpc/paired-block-krylov-20260921'
WORKERS=16
LIMITS={'A-base-full':1,'A-base-half':1,'A-trial-full':1,'A-trial-half':1,'B-base':2,'B-trial':2}
TERMINAL={'complete','science_rejected','failed'}


class Stopped(Exception): pass


def stop(number, frame):
    driver.signal_stop(number,frame)


def checkpoint():
    if pipeline.STOP: raise Stopped('stop requested; no further map batches dispatched')


@contextmanager
def feedback_stop_guard():
    """Preserve the frozen evaluator's batch commits; stop before its next batch."""
    original=pair._run_feedback_state
    def guarded(protocol,*args,**kwargs):
        checkpoint()
        original_processes=pair.subprocess
        concurrency=int(protocol['configuration']['maximum_concurrent_processes'])
        class Processes:
            started=0
            def __getattr__(self,name):return getattr(original_processes,name)
            def Popen(self,*a,**k):
                # 已派发批次必须全部收尾并提交，才在下一批的首个进程处响应停止。
                if self.started % concurrency == 0:checkpoint()
                process=original_processes.Popen(*a,**k);self.started+=1
                return process
        pair.subprocess=Processes()
        try:return original(protocol,*args,**kwargs)
        finally:pair.subprocess=original_processes
    pair._run_feedback_state=guarded
    try:yield
    finally:pair._run_feedback_state=original


def verify(claims):
    bad=pipeline.verify_claims(ROOT,claims,hash_files=True)
    if bad: raise RuntimeError('input identity changed: '+str(bad))


def immutable(path,payload):
    if path.exists():
        if pipeline.read(path)!=payload:raise RuntimeError('immutable declaration differs: '+str(path))
    else:pipeline.write_json(path,payload)


def budget(states):
    total=0; pairs=0
    for name,state in states.items():
        if name not in LIMITS:raise RuntimeError('undeclared child')
        if state.get('status') in driver.FAULT_STATUSES:raise RuntimeError('child fault: '+name)
        used=len(state['history'])+int(state.get('active_map') is not None)
        if used>LIMITS[name]:raise RuntimeError('child map budget exceeded')
        total+=used
        rounds=len(state.get('diagnostic',{}).get('rounds',[]))+int(bool(state.get('pending_feedback')))
        if rounds>int(name.startswith('B-')):raise RuntimeError('child feedback budget exceeded')
        pairs+=rounds
    if total>8 or pairs>2:raise RuntimeError('batch hard budget exceeded')
    return {'maps_committed_or_active':total,'feedback_pairs_completed_or_pending':pairs}


def child_states(out):
    return {name:pipeline.read(out/name/'state.json') for name in LIMITS if (out/name/'state.json').exists()}


def mark(out,status,**extra):
    path=out/'status.json'; state=pipeline.read(path) if path.exists() else {}
    if state.get('status') in TERMINAL and status!=state['status']:
        raise RuntimeError('terminal status cannot be replaced')
    state.update(status=status,updated_unix=time.time(),**budget(child_states(out)),**extra)
    pipeline.write_json(path,state)
    print({'batch_status':status,'maps':state['maps_committed_or_active'],
           'pairs':state['feedback_pairs_completed_or_pending']},flush=True)


def archive(out,stage):
    """Snapshot small evidence only; dat and captured large block arrays stay external."""
    dest=out/'archives';dest.mkdir(exist_ok=True)
    tag=f'{stage}-{time.time_ns()}'; manifest=[]; paths=[]
    for p in sorted(out.rglob('*')):
        if (not p.is_file() or p.is_relative_to(dest) or p.suffix in {'.dat','.tmp','.lock'}
            or p.stat().st_size>32*1024**2):continue
        paths.append(p);manifest.append({'path':p.relative_to(out).as_posix(),
            'size_bytes':p.stat().st_size,'sha256':pipeline.sha256(p)})
    mp=dest/(tag+'.json');pipeline.write_json(mp,{'files':manifest,'stage':stage})
    target=dest/(tag+'.tar.gz'); temp=target.with_suffix('.tmp')
    with tarfile.open(temp,'w:gz') as tar:
        for p in paths:tar.add(p,arcname=p.relative_to(out).as_posix())
        tar.add(mp,arcname='ARCHIVE_MANIFEST.json')
    temp.replace(target)
    pipeline.write_json(dest/(tag+'-receipt.json'),pipeline.claim(target))


def capture_worker(out,label,index):
    """Isolated adapter saves arrays returned by the unchanged local correction."""
    original=local.evaluate_direction
    claims={};arrays={}
    def captured(x,y,direction,source_map):
        candidate,fresh,result=original(x,y,direction,source_map)
        arrays.update(direction=direction,candidate=candidate)
        return candidate,fresh,result
    local.evaluate_direction=captured
    try:local.worker(out,label,index)
    finally:local.evaluate_direction=original
    started=time.monotonic()
    for name,value in arrays.items():
        path=out/f'{label}-block{index:02d}-{name}.npy';tmp=path.with_suffix('.tmp')
        with tmp.open('wb') as f:np.save(f,value,allow_pickle=False)
        tmp.replace(path);claims[name]=pipeline.claim(path)
    report=pipeline.read(out/f'{label}-block{index:02d}.json')
    pipeline.write_json(out/f'{label}-block{index:02d}-receipt.json',{'arrays':claims,
        'report':pipeline.claim(out/f'{label}-block{index:02d}.json'),
        'array_capture_wall_s':time.monotonic()-started,
        'passed':report['eligible_for_further_block_review']})


def prepare(out):
    declaration=out/'declaration.json'
    if declaration.exists():
        plan=pipeline.read(declaration);verify(plan['code'])
        for case in plan['cases'].values():verify(list(case.values()))
        if plan['gates']!=GATES or plan['child_map_limits']!=LIMITS:raise RuntimeError('declared controls changed')
        return plan
    snap=Snapshot(out)
    pilot=snap.read(PILOT+'/declaration.json')
    summary=snap.read(PILOT+'/summary.json')
    if not summary['all_four_local_cases_passed']:raise RuntimeError('pilot not eligible')
    cases=pilot['cases']
    for case in cases.values():
        verify(list(case.values()))
        cfg=pipeline.read(ROOT/case['config']['path']);verify(cfg['sources'])
        for c in cfg['sources']:
            if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
        for c in case.values():
            if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
        audit_native_trial(cfg,load_arrays(ROOT/case['trial']['path']))
    local.zero_matches_candidate(*(load_arrays(ROOT/cases[k]['trial']['path']) for k in ('base','trial')))
    # 冻结所有编排代码，避免恢复时悄悄换算法；历史核心另由 sources 锁定。
    names=sorted(set(p for folder in ('operations','diagnostics') for p in (ROOT/folder).glob('*') if p.suffix in {'.py','.sbatch'}))
    code=[pipeline.claim(p) for p in names]
    for c in code:snap.save(c['path'],c['sha256'])
    plan={'cases':cases,'gates':GATES,'child_map_limits':LIMITS,'maximum_maps':8,'maximum_pairs':2,
          'workers':WORKERS,'local_workers':2,'local_restart':8,'local_cycles':2,
          'code':code,'environment':pipeline.environment(),
          'physical_dt_changed':False,'formal_baseline_changed':False,
          'baseline_is_diagnostic_only':True,'shape':list(pipeline.SHAPE)}
    immutable(declaration,plan);return plan


def corrections(out):
    # 一次只派两个小块，信号后收尾当前批，不再派下一批。
    for label in ('base','trial'):
        checkpoint(); jobs=[]
        for index in local.BLOCKS:
            receipt=out/f'{label}-block{index:02d}-receipt.json'
            if receipt.exists():
                r=pipeline.read(receipt);verify([r['report'],*r['arrays'].values()])
                if not r['passed']:raise RuntimeError('local correction failed')
                continue
            log=(out/f'{label}-block{index:02d}-capture.log').open('a')
            proc=subprocess.Popen([sys.executable,__file__,'--run',str(out.relative_to(ROOT)),
                '--worker',label,'--block',str(index)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            jobs.append((proc,log))
        codes=[]
        for proc,log in jobs:codes.append(proc.wait());log.close()
        if any(codes):raise RuntimeError('correction worker failed: '+str(codes))
        for index in local.BLOCKS:
            if not pipeline.read(out/f'{label}-block{index:02d}-receipt.json')['passed']:
                raise RuntimeError('local correction gate failed')


def candidate(out,case,label,fraction):
    tag='full' if fraction==1 else 'half';path=out/f'{label}-{tag}.dat';receipt=out/f'{label}-{tag}-candidate.json'
    if receipt.exists():
        c=pipeline.read(receipt);verify([c]);return c
    if path.exists():raise RuntimeError('candidate without committed receipt; manual recovery required')
    replacements={i:ROOT/pipeline.read(out/f'{label}-block{i:02d}-receipt.json')['arrays']['candidate']['path'] for i in local.BLOCKS}
    hybrid(ROOT/case['input']['path'],path,replacements,fraction,pipeline.SHAPE)
    c=pipeline.claim(path);immutable(receipt,c);return c


def child(out,name,label,seed,plan):
    folder=out/name;limit=LIMITS[name]
    intent={'name':name,'label':label,'seed':seed,'maps':limit,'trial':plan['cases'][label]['trial']}
    immutable(out/(name+'-intent.json'),intent);folder.mkdir(exist_ok=True)
    cfgpath=folder/'config.json';statepath=folder/'state.json'
    source=ROOT/plan['cases'][label]['trial']['path'];trial=load_arrays(source)
    if not cfgpath.exists():
        carry_trial(source.parent,folder);identical_material(trial,load_arrays(folder/'trial_material.npz'))
        cfg=deepcopy(pipeline.read(ROOT/plan['cases'][label]['config']['path']))
        cfg.update(run=str(folder.relative_to(ROOT)),workers=WORKERS,maximum_maps=limit,
                   seed='warm',warm_seed=seed,radiation_threshold=1e-4)
        cfg['sources']=list(cfg['sources'])+[seed,pipeline.claim(folder/'trial_material.npz'),pipeline.claim(out/'declaration.json')]+plan['code']
        immutable(cfgpath,cfg)
    cfg=pipeline.read(cfgpath)
    if cfg['warm_seed']!=seed or cfg['maximum_maps']!=limit:raise RuntimeError('child intent changed')
    identical_material(trial,load_arrays(folder/'trial_material.npz'))
    if not statepath.exists():
        pipeline.write_json(statepath,{'config_sha256':pipeline.sha256(cfgpath),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[str((folder/f'state_{i}.dat').relative_to(ROOT)) for i in range(3)],
            'current_slot':0,'active_map':None})
    state=pipeline.read(statepath)
    if state['config_sha256']!=pipeline.sha256(cfgpath):raise RuntimeError('child config changed')
    if state['status']=='initializing':
        pipeline.write_json(folder/'native_trial_audit.json',audit_native_trial(cfg,trial))
        pipeline.run_pipeline(folder,0,False)
        signal.signal(signal.SIGUSR1,stop);checkpoint()
        state=pipeline.read(statepath)
        initialized_identity(state,seed,trial,load_arrays(folder/'trial_material.npz'))
        pipeline.write_json(folder/'initialized_identity.json',{'passed':True,'trial':pipeline.claim(folder/'trial_material.npz'),
            'native':audit_native_trial(cfg,trial)})
    if not (folder/'initialized_identity.json').exists():
        # 初始化已完成但写证明前中断：仅允许空历史、同一初值的严格重验。
        initialized_identity(state,seed,trial,load_arrays(folder/'trial_material.npz'))
        pipeline.write_json(folder/'initialized_identity.json',{'passed':True,'recovered':True,'native':audit_native_trial(cfg,trial)})
    return folder,cfg,state


def baseline_round(folder,cfg,state,statepath):
    """Evaluate alpha=0 through original state evaluator, never material acceptance."""
    pending=state['pending_feedback'];rd=ROOT/pending['round_dir'];rd.mkdir(exist_ok=True)
    if pending['stage']=='protocol':
        raw=driver.build_round_protocol(folder,cfg,state,rd);payload=pipeline.read(raw)
        payload['authorization'].update(accept_material_step=False,zero_displacement_control=True)
        path=rd/'baseline_control_protocol.json';immutable(path,payload)
        pending.update(stage='feedback',protocol_path=str(path.relative_to(ROOT)),protocol_sha256=pipeline.sha256(path))
        pipeline.write_json(statepath,state)
    path=ROOT/pending['protocol_path'];verify([{'path':pending['protocol_path'],'sha256':pending['protocol_sha256'],'size_bytes':path.stat().st_size}])
    loaded=pair.load_frozen_pair_protocol(path,pending['protocol_sha256'],validate_sources=True)
    pair._validate_worker_template_sources(loaded)
    claims=pending.get('feedback_claims',{})
    if pending['stage']!='ledger':
        for endpoint in ('previous','final'):
            checkpoint()
            m=pair._run_feedback_state(loaded,path,pending['protocol_sha256'],endpoint)
            c=pipeline.claim(ROOT/m['feedback_artifact_path'])
            s=loaded['sources'][endpoint+'_radiation']
            if (not m['state_gate_passed'] or m['status']!='complete' or m['state_sha256']!=s['sha256']
                or m['state_path']!=s['path'] or m['protocol_sha256']!=pending['protocol_sha256']
                or c['sha256']!=m['feedback_artifact_sha256']):
                raise RuntimeError('baseline feedback gate or lineage failure')
            claims[endpoint]=c
        pending.update(stage='ledger',feedback_claims=claims);pipeline.write_json(statepath,state)
    verify(list(claims.values()))
    try:report=driver.run_ledger(folder,rd,claims)
    except Exception:
        state['status']='diagnosis_incomplete';pipeline.write_json(statepath,state);raise
    for key,source in [('trial_material','trial_material'),('old_time_level','physical_old_time_level')]:
        if report['inputs'][key]['sha256']!=loaded['sources'][source]['sha256']:
            raise RuntimeError('baseline ledger input differs from protocol')
    record={'baseline_control_only':True,'accepted':False,'protocol_sha256':pending['protocol_sha256'],
            'feedback_claims':claims,'ledger':str((rd/'material_energy_ledger.json').relative_to(ROOT))}
    immutable(rd/'round_summary.json',record)
    state.setdefault('diagnostic',{}).setdefault('rounds',[]).append(record)
    state.pop('pending_feedback');state['status']='baseline_control_complete';pipeline.write_json(statepath,state)


def settle(folder,cfg,state,statepath,label):
    if not state.get('pending_feedback'):return
    checkpoint()
    with feedback_stop_guard():
        if label=='base':baseline_round(folder,cfg,state,statepath)
        else:driver.complete_round(folder,cfg,state,statepath)


def maps(out,name,label,seed,plan):
    folder,cfg,state=child(out,name,label,seed,plan);statepath=folder/'state.json'
    budget(child_states(out))
    settle(folder,cfg,state,statepath,label) # 欠反馈先结清；任何新map不得越过它。
    while len(state['history'])<LIMITS[name]:
        checkpoint();budget(child_states(out))
        if not driver.run_one_map(folder,cfg,state,statepath):raise Stopped('partial map committed')
        budget(child_states(out))
    return folder,cfg,state


def stage_a(out,plan):
    reports={}
    for label,case in plan['cases'].items():
        records={}
        for tag,fraction in [('full',1.),('half',.5)]:
            checkpoint();seed=candidate(out,case,label,fraction)
            folder,cfg,state=maps(out,'A-'+label+'-'+tag,label,seed,plan)
            records[tag]=state['history'][0]
        original=pipeline.read(ROOT/case['state']['path'])['history'][-1]
        paths=[ROOT/case['input']['path'],ROOT/case['output']['path']]
        for tag in ('full','half'):paths.extend(ROOT/records[tag][k+'_path'] for k in ('input','output'))
        field=audit(paths,pipeline.SHAPE);gate=checks(field,original,records['full'],records['half'])
        reports[label]={'field':field,'checks':gate,'passed':all(gate.values()),'maps':records}
        immutable(out/(label+'-A-result.json'),reports[label]);archive(out,'A-'+label)
    result={'cases':reports,'passed':all(r['passed'] for r in reports.values())}
    for case in plan['cases'].values():verify(list(case.values()))
    immutable(out/'A-result.json',result);return result


def stage_b(out,plan,a):
    # 恢复首先处理任何子运行所欠反馈；不能先推进另一个物质态。
    for label in ('base','trial'):
        path=out/('B-'+label)/'state.json'
        if path.exists():
            state=pipeline.read(path)
            if state.get('pending_feedback'):settle(path.parent,pipeline.read(path.parent/'config.json'),state,path,label)
    for label in ('base','trial'):
        checkpoint();row=a['cases'][label]['maps']['full']
        seed={'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES}
        folder,cfg,state=maps(out,'B-'+label,label,seed,plan)
        if state.get('diagnostic',{}).get('rounds'):continue
        if not pipeline.pair_ready(state['history'],1e-4):
            immutable(folder/'pair_rejected.json',{'reason':'two original inner/boundary gates not met','history':state['history']})
            return False
        checkpoint();driver.start_round(folder,cfg,state,folder/'state.json');budget(child_states(out))
        settle(folder,cfg,state,folder/'state.json',label);archive(out,'B-'+label)
    return True


def stage_c(out,plan):
    from dataclasses import asdict
    from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
    from diagnostics.material_energy_ledger import ledger
    from operations.audit_outer_contraction import decomposition
    results={};vectors={}
    for label in ('base','trial'):
        rd=out/('B-'+label)/'feedback-round1'
        path=rd/('baseline_control_protocol.json' if label=='base' else 'feedback_protocol.json')
        protocol=pipeline.read(path);old=load_arrays(ROOT/protocol['sources']['physical_old_time_level']['path'])
        trial=load_arrays(ROOT/protocol['sources']['trial_material']['path']);phase=int(trial['phase_index'])
        mass=old['cell_mass_g_cm2'];vectors[label]={};results[label]={}
        for endpoint in ('previous','final'):
            fb=load_arrays(rd/(endpoint+'_feedback.npz'))
            response,residual,context=pair._material_response_residual(protocol,fb)
            book=ledger(fb,trial['density_g_cm3'],float(trial['step_duration_s']),old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            if not all(np.isfinite(v).all() for v in book.values()):raise ValueError('nonfinite ledger')
            for got,want in ((book['target'],response.target_specific_material_energy_erg_g),(book['new_h'],response.hydrogen_fraction),(book['new_he'],response.helium_fraction)):
                if not np.allclose(got,want,rtol=1e-12,atol=0):raise ValueError('independent ledger disagrees')
            vectors[label][endpoint]=residual
            results[label][endpoint]={'norms':asdict(encoded_residual_norms(residual,mass)),
                'minimum_gas_heat_erg_g':float(np.min(book['remaining'])),'response_ledger_agree':True}
        results[label]['adjacent_drift']=asdict(encoded_residual_norms(vectors[label]['final']-vectors[label]['previous'],mass))
    archived=trial['base_residual']
    results['frozen_formal_baseline']=asdict(encoded_residual_norms(archived,mass))
    results['final_candidate_minus_base']=asdict(encoded_residual_norms(vectors['trial']['final']-vectors['base']['final'],mass))
    results['formal_comparisons']={e:decomposition(archived,vectors['trial'][e],mass) for e in ('previous','final')}
    results['diagnostic_comparisons']={e:decomposition(vectors['base'][e],vectors['trial'][e],mass) for e in ('previous','final')}
    for label in ('base','trial'):
        drift=results[label]['adjacent_drift'];scale=results['frozen_formal_baseline']
        results[label]['adjacent_drift_over_frozen_baseline']={k:drift[k]/scale[k] for k in scale}
    results['limitations']=['Adjacent drift is not a bound on the true inner error.','Baseline diagnostics do not replace the frozen formal acceptance denominator.','A finite accepted material step is not a coupled atmosphere or a disk spectrum.']
    immutable(out/'C-result.json',results)


def execute(out):
    if (out/'status.json').exists() and pipeline.read(out/'status.json')['status'] in TERMINAL:return
    mark(out,'preparing');plan=prepare(out);checkpoint()
    for label in ('base','trial'):
        path=out/('B-'+label)/'state.json'
        if path.exists():
            state=pipeline.read(path)
            if state.get('pending_feedback'):
                settle(path.parent,pipeline.read(path.parent/'config.json'),state,path,label)
    if shutil.disk_usage(out).free<25*pipeline.STATE_BYTES:raise RuntimeError('less than 235 GiB free for retained candidates/slots')
    mark(out,'A');corrections(out);checkpoint();a=stage_a(out,plan)
    if not a['passed']:mark(out,'science_rejected',reason='A full-field gates');archive(out,'rejected-A');return
    mark(out,'B')
    if not stage_b(out,plan,a):mark(out,'science_rejected',reason='B original inner gates');archive(out,'rejected-B');return
    mark(out,'C');checkpoint();stage_c(out,plan);archive(out,'C')
    mark(out,'complete',accepted_material_step=pipeline.read(out/'B-trial/state.json')['status']=='one_material_trial_accepted')
    archive(out,'complete')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True)
    p.add_argument('--worker',choices=('base','trial'));p.add_argument('--block',type=int,choices=local.BLOCKS)
    args=p.parse_args();pipeline.require_allocation(2 if args.worker else WORKERS)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc')
    if args.worker:capture_worker(out,args.worker,args.block);return
    out.mkdir(parents=True,exist_ok=True)
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signal.signal(signal.SIGUSR1,stop);signal.signal(signal.SIGTERM,stop)
        try:execute(out)
        except Stopped as exc:mark(out,'interrupted',reason=str(exc));archive(out,'interrupted')
        except Exception as exc:
            # 故障终态不能被预算结束覆盖；保留原异常及阶段证据。
            path=out/'status.json';state=pipeline.read(path) if path.exists() else {}
            ledger_pending=any(s.get('status')=='diagnosis_incomplete' and s.get('pending_feedback',{}).get('stage')=='ledger'
                               for s in child_states(out).values())
            state.update(status='diagnosis_incomplete' if ledger_pending else 'failed',error=repr(exc),failed_at=time.time());pipeline.write_json(path,state)
            archive(out,'failed');raise


if __name__=='__main__':main()
