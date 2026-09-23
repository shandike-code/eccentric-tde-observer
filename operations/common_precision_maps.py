"""Bounded fixed-matter maps with retained endpoints for common-domain feedback."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import time
import numpy as np
from operations import common_feedback_bridge as bridge
from operations import composite_hybrid_batch as reused
from operations.constrained_hybrid_batch import relay_dispatch
from diagnostics import interval_diagnostic as driver
from operations.prepare_encoded_backtrack import load_arrays
from operations.radiation_history_diagnostic import identical_material
from operations.prepare_half_step_after_audit import REQUIRED_GATES
pipeline=reused.pipeline
ROOT=reused.ROOT
SOURCE='outputs/hpc/step16-backtrack-20260923/full'
BRIDGE='outputs/hpc/common-feedback-bridge-v2-20260923'
FAILED={'last_two_atomic_heating_pass','last_two_direct_heating_pass','last_two_formal_heating_pass','inner_noise_resolved_pass'}


def eligible(report):
    gates=report['pair_gate_checks']
    return (set(gates)==REQUIRED_GATES and {k for k,v in gates.items() if v is not True}==FAILED
        and report['accepted_outer_steps_remain']==15 and not report['material_step_promoted']
        and all(np.isfinite(r['minimum_gas_heat_erg_g']) and r['minimum_gas_heat_erg_g']>0 for r in report['responses'].values())
        and set(report['responses'])=={'previous','final'})


def allow_second_half(history):
    if len(history)!=4:raise ValueError('decision requires four committed maps')
    # 这是追加预算门，不是反馈或物质接受门；不把辐射残差当加热误差界。
    return (all(np.isfinite(r[k]) for r in history for k in ('residual','boundary_l1','boundary_bolometric','maximum_worker_rss_mib'))
        and history[-1]['residual']<history[0]['residual']
        and all(0<=r['residual']<1e-4 and 0<=r['boundary_l1']<1e-3 and 0<=r['boundary_bolometric']<1e-3 and r['maximum_worker_rss_mib']<6144 for r in history[-2:]))


def retain_pair(out,state):
    n=len(state['history']);dest=out/f'endpoints-map{n:02d}'
    if dest.exists():raise FileExistsError(dest)
    dest.mkdir();rows=state['history'][-2:]
    if rows[0]['output_sha256']!=rows[1]['input_sha256']:raise RuntimeError('nonconsecutive pair')
    records={}
    for label,row,kind in (('previous',rows[0],'input'),('final',rows[1],'input'),('mapped_final',rows[1],'output')):
        source=ROOT/row[kind+'_path'];target=dest/(label+'.dat')
        if pipeline.sha256(source)!=row[kind+'_sha256']:raise RuntimeError('rotating slot changed before retention')
        shutil.copyfile(source,target);c=pipeline.claim(target)
        if c['sha256']!=row[kind+'_sha256'] or c['size_bytes']!=pipeline.STATE_BYTES:raise RuntimeError('retained bytes differ')
        records[label]=c
    reused.immutable(dest/'manifest.json',{'new_map_count':n,'endpoints':records,'history_rows':rows,
        'feedback_evaluated':False,'material_accepted':False,'required_feedback_domain':'common comoving frequency window'})


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,updated_unix=time.time(),new_material_steps=0,**kw))
    mark('preparing')
    try:
        report=pipeline.read(ROOT/BRIDGE/'reassessment.json')
        if not eligible(report):raise RuntimeError('bridge no longer justifies this fixed-candidate refinement')
        receipt=pipeline.read(ROOT/(BRIDGE+'.process.json'))
        if receipt['returncode']!=0 or not receipt['memory_guard_passed']:raise RuntimeError('bridge resource receipt failed')
        review=pipeline.read(ROOT/'handoff/evidence/20260923-common-feedback-bridge-review.json')
        if review['gate_checks']!=report['pair_gate_checks'] or not review['new_source_and_old_atomic_fields_verified_bitwise']:raise RuntimeError('Mac audit mismatch')
        cfg=pipeline.read(ROOT/SOURCE/'config.json');state=pipeline.read(ROOT/SOURCE/'state.json')
        if state['active_map'] or len(state['history'])!=4 or pipeline.sha256(ROOT/SOURCE/'config.json')!=state['config_sha256']:raise RuntimeError('source map state changed')
        # 旧run的pending反馈原样保留；本独立分支以新协议已结算的桥报告为前提。
        proto=pipeline.read(ROOT/BRIDGE/'feedback_protocol.json')
        trial=load_arrays(ROOT/SOURCE/'trial_material.npz');frozen=load_arrays(ROOT/proto['sources']['trial_material']['path'])
        identical_material(trial,frozen)
        bridge.validate_identity(trial,load_arrays(ROOT/proto['sources']['outer_base_material']['path']),np.load(ROOT/proto['sources']['base_residual']['path']),load_arrays(ROOT/proto['sources']['physical_old_time_level']['path']))
        row=state['history'][-1]
        if state['slots'][state['current_slot']]!=row['output_path'] or state['current_sha256']!=row['output_sha256']:raise RuntimeError('seed not latest output')
        seed={'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES}
        code=[pipeline.claim(f) for d in ('operations','diagnostics') for f in sorted((ROOT/d).iterdir()) if f.suffix in ('.py','.sbatch')]
        claims=cfg['sources']+[seed]+[pipeline.claim(ROOT/p) for p in (SOURCE+'/state.json',SOURCE+'/config.json',SOURCE+'/trial_material.npz',BRIDGE+'/reassessment.json',BRIDGE+'/feedback_protocol.json',BRIDGE+'.process.json','handoff/evidence/20260923-common-feedback-bridge-review.json','handoff/protocols/common-precision-maps-v1.md')]
        reused.verify(claims+code)
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained-checkpoint space')
        plan={'cases':{'trial':{'trial':pipeline.claim(ROOT/SOURCE/'trial_material.npz'),'config':pipeline.claim(ROOT/SOURCE/'config.json')}},
            'code':code,'claims':claims,'environment':pipeline.environment(),'maximum_new_maps':8,'first_stage_maps':4,
            'conditional_second_stage_maps':4,'retained_pairs_after_maps':[4,8],'feedback_evaluated':False,'new_material_steps':0,'seed':seed,
            'scope':'same exact 1/64 trial; numerical radiation precision only; common-domain feedback must follow separately'}
        reused.immutable(out/'declaration.json',plan);reused.LIMITS={'maps':8}
        with relay_dispatch():
            folder,cfg,s=reused.child(out,'maps','trial',seed,plan)
            signal.signal(signal.SIGUSR1,reused.stop);signal.signal(signal.SIGTERM,reused.stop)
            for _ in range(8):
                reused.checkpoint();mark('mapping',completed_maps=len(s['history']))
                if not driver.run_one_map(folder,cfg,s,folder/'state.json'):raise reused.Stopped('partial map committed')
                if s['status'] in driver.FAULT_STATUSES:raise RuntimeError('map resource/fault status')
                n=len(s['history'])
                if n in (4,8):
                    retain_pair(out,s);reused.archive(out,f'map{n:02d}-retained')
                    if n==4:
                        proceed=allow_second_half(s['history']);reused.immutable(out/'second-stage-decision.json',{'continue':proceed,'history':s['history'],'feedback_not_inferred':True})
                        if not proceed:
                            mark('stopped_after_four',completed_maps=4,feedback_pending=True);return
        reused.verify(claims+code);mark('maps_complete_feedback_required',completed_maps=8,feedback_pending=True)
        reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
