"""Three conditional nonlinear steps and a final fixed-material confirmation.

The sequence changes scheduling granularity only. Original physics, amplitudes,
response replays, acceptance tests, memory guards and each child's budget remain.
"""
from __future__ import annotations
import argparse
import fcntl
import os
from pathlib import Path
import signal
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
from operations import numbered_confirmation_step as stage
pipeline=stage.pipeline
reused=stage.reused
SOURCE='outputs/hpc/confirm2-then-step3-20260921/next-step'
FIRST_INDEX=4
STEP_COUNT=3
MAXIMUM_MAPS=78
MAXIMUM_PAIRS=27
TERMINAL={'complete_requires_review','science_stopped','accepted_shape_requires_review','failed'}


def cycle_paths(out):
    return [out/f'step{i}' for i in range(FIRST_INDEX,FIRST_INDEX+STEP_COUNT)]


def all_states(out):
    result=[]
    for p in cycle_paths(out):
        result.extend(stage.confirm.states(p/'confirmation').values())
        result.extend(stage.batch.child_states(p/'next-step').values())
    result.extend(stage.confirm.states(out/'final-confirmation').values())
    return result


def budget(out):
    stages={}
    for p in cycle_paths(out):
        if (p/'status.json').exists() and pipeline.read(p/'status.json')['status']=='failed':
            raise RuntimeError('cycle failure is terminal')
        stages[p.name]=stage.budget(p)
    final=out/'final-confirmation'
    if (final/'status.json').exists() and pipeline.read(final/'status.json')['status']=='failed':
        raise RuntimeError('final confirmation failure is terminal')
    stage.confirm.budget(final)
    tail=stage.counts(stage.confirm.states(final))
    nm=sum(x['maps_committed_or_active'] for x in stages.values())+tail['completed_maps']+tail['active_maps']
    npair=sum(x['pairs_completed_or_pending'] for x in stages.values())+tail['completed_pairs']+tail['pending_pairs']
    if nm>MAXIMUM_MAPS or npair>MAXIMUM_PAIRS:raise RuntimeError('sequence budget exceeded')
    return {'cycles':stages,'final_confirmation':tail,'maps_committed_or_active':nm,
            'pairs_completed_or_pending':npair}


def mark(out,status,**extra):
    p=out/'status.json';old=pipeline.read(p) if p.exists() else {}
    if old.get('status') in TERMINAL and status not in (old['status'],'failed'):
        raise RuntimeError('sequence terminal status immutable')
    old.update(status=status,updated_unix=time.time(),**extra)
    if status!='failed':old.update(budget(out))
    pipeline.write_json(p,old);print(old,flush=True)


def declare(out):
    expected={'source':SOURCE,'first_outer_step_index':FIRST_INDEX,'maximum_new_steps':STEP_COUNT,
        'maximum_maps':MAXIMUM_MAPS,'maximum_pairs':MAXIMUM_PAIRS,
        'per_cycle_maps':24,'per_cycle_pairs':8,'final_confirmation_maps':6,'final_confirmation_pairs':3,
        'alphas':stage.batch.ALPHAS,'physical_time_advanced':False,'gates_relaxed':False,
        'automatic_resubmit':False,'coupled_column_accepted':False}
    p=out/'declaration.json'
    if p.exists():
        d=pipeline.read(p);reused.verify(d['pinned'])
        if any(d.get(k)!=v for k,v in expected.items()):raise RuntimeError('sequence contract changed')
        return d
    pinned=[pipeline.claim(f) for name in ('operations','diagnostics') for f in sorted((ROOT/name).iterdir()) if f.suffix in ('.py','.sbatch')]
    pinned.extend(pipeline.claim(ROOT/SOURCE/f) for f in ('status.json','declaration.json','full/state.json',
        'full/feedback-round2/feedback_summary.json','full/feedback-round2/feedback_protocol.json',
        'full/feedback-round2/fresh_control_comparison.json'))
    expected.update(pinned=pinned,environment=pipeline.environment())
    reused.immutable(p,expected);return expected


def continuation_ready(folder):
    """Do not silently generalize the source replay to half or early acceptance."""
    s=pipeline.read(folder/'status.json')
    if s['status']!='formal_acceptance_requires_review':return False
    if s['candidate']!='full':return False
    state=pipeline.read(folder/'full/state.json')
    return (state.get('active_map') is None and not state.get('pending_feedback')
        and len(state['history'])==8 and len(state['diagnostic']['rounds'])==2)


def transition(out,index,source):
    folder=ROOT/source;rd=folder/'full/feedback-round2'
    # 每步进入前冻结来源，后续确认再重求原物质响应；不能用报告文字代替数值重放。
    payload={'accepted_outer_step_index':index,'source':source,
        'source_status':pipeline.claim(folder/'status.json'),'state':pipeline.claim(folder/'full/state.json'),
        'protocol':pipeline.claim(rd/'feedback_protocol.json'),'summary':pipeline.claim(rd/'feedback_summary.json'),
        'fresh_control':pipeline.claim(rd/'fresh_control_comparison.json'),'physical_time_advanced':False}
    reused.immutable(out/f'accepted-step{index}.json',payload)


def execute(out):
    budget(out)
    if (out/'status.json').exists() and pipeline.read(out/'status.json')['status'] in TERMINAL:return
    declare(out);reused.checkpoint()
    # 保留所有历史辐射态：预留全预算的保守空间，不靠删除旧态完成连跑。
    if __import__('shutil').disk_usage(out).free<MAXIMUM_MAPS*pipeline.STATE_BYTES:
        raise RuntimeError('insufficient retained-state space for sequence')
    source=SOURCE
    for index,folder in zip(range(FIRST_INDEX,FIRST_INDEX+STEP_COUNT),cycle_paths(out),strict=True):
        reused.checkpoint();budget(out)
        stage.configure(source,index-1)
        transition(out,index-1,source)
        folder.mkdir(exist_ok=True);mark(out,'running',current_outer_step=index,current_stage='confirmation_then_step')
        stage.execute(folder);budget(out);reused.checkpoint()
        result=pipeline.read(folder/'status.json')
        if result['status']!='formal_acceptance_requires_review' or result.get('fresh_control_corroborated') is not True:
            mark(out,'science_stopped',reason='cycle did not produce corroborated acceptance',stopped_cycle=index)
            reused.archive(out,'science-stopped');return
        source=str((folder/'next-step').relative_to(ROOT))
        if not continuation_ready(ROOT/source):
            mark(out,'accepted_shape_requires_review',accepted_outer_step=index,accepted_source=source,
                reason='half or early acceptance is preserved but outside automatic source-replay contract')
            reused.archive(out,'accepted-shape-review');return
    reused.checkpoint();budget(out)
    final_index=FIRST_INDEX+STEP_COUNT-1
    stage.configure(source,final_index);transition(out,final_index,source)
    tail=out/'final-confirmation';tail.mkdir(exist_ok=True)
    mark(out,'running',current_outer_step=final_index,current_stage='final_confirmation')
    stage.run_confirmation(tail);budget(out);reused.checkpoint()
    if not stage.confirmation_passed(tail):
        mark(out,'science_stopped',reason='final same-material precision confirmation failed',accepted_outer_step=final_index)
    else:
        mark(out,'complete_requires_review',accepted_outer_step=final_index,
            new_accepted_steps=STEP_COUNT,final_precision_confirmation_passed=True,coupled_column_accepted=False)
    reused.archive(out,'sequence-finished')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);a=p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out=pipeline.safe_path(ROOT,a.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=True)
    with (out/'sequence.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signal.signal(signal.SIGUSR1,reused.stop);signal.signal(signal.SIGTERM,reused.stop)
        with stage.relay_dispatch():
            try:execute(out)
            except reused.Stopped as exc:
                mark(out,'interrupted',reason=str(exc));reused.archive(out,'interrupted')
            except Exception as exc:
                pending=any(s.get('status')=='diagnosis_incomplete' and (s.get('pending_feedback') or {}).get('stage')=='ledger' for s in all_states(out))
                mark(out,'diagnosis_incomplete' if pending else 'failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':main()
