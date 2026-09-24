"""One bounded fixed-x18 precision diagnostic after audited inner-budget exhaustion."""
import argparse
import json
import os
import shutil
import signal
import tarfile
import time
import numpy as np
from operations import common_native_feedback as fresh
from operations.common_outer_step18 import verify_step18_pair
from operations.common_confirmation_batch import cross_comparisons,all_pair_gates
from operations.common_precision_maps import retain_pair,allow_second_half
from operations.constrained_hybrid_batch import relay_dispatch
from diagnostics import interval_diagnostic as driver
pipeline=fresh.pipeline;pair=fresh.pair;reused=fresh.reused;ROOT=fresh.ROOT;load_arrays=fresh.load_arrays
SOURCE='outputs/hpc/common-step18-20260924'
BASE='outputs/hpc/common-confirmation17-20260924/confirm2'


def eligible(summary,history):
    if (summary.get('status')!='budget_complete_not_accepted' or summary.get('accepted_outer_steps')!=17
        or summary.get('new_material_steps')!=0 or len(history)!=8
        or summary.get('pairs')!={str(n):dict(inner_pair_ready=False,feedback_evaluated=False) for n in (4,8)}):return False
    fields=('residual','boundary_l1','boundary_bolometric','maximum_worker_rss_mib')
    if not all(np.isfinite(r[k]) for r in history for k in fields):return False
    return (all(r['residual']>=1e-4 and 0<=r['boundary_l1']<1e-3 and 0<=r['boundary_bolometric']<1e-3
                and 0<r['maximum_worker_rss_mib']<6144 for r in history)
        and all(b['residual']<a['residual'] for a,b in zip(history,history[1:])))


def prepare(out):
    review_path=ROOT/'handoff/evidence/20260924-common-step18-inner-review.json'
    terminal_path=ROOT/'handoff/evidence/20260924-step18-76383-terminal.json'
    review=pipeline.read(review_path);terminal=pipeline.read(terminal_path)
    if (terminal['job_id']!=76383 or terminal['state']!='COMPLETED' or review['accepted_outer_steps']!=17
        or not review['candidate_identity_verified'] or review['feedback_evaluated']
        or review['maps']!=8 or review['independent_process_receipts']!=608):raise RuntimeError('source not independently audited')
    receipt=review['archive'];reused.verify([receipt])
    with tarfile.open(ROOT/receipt['path']) as archive:
        inventory={c['path']:c for c in json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    claims=[pipeline.claim(review_path),pipeline.claim(terminal_path)]
    for name in ('status.json','summary.json','maps/state.json','maps/config.json','maps/trial_material.npz',
                 'inputs/feedback_reference.json','inputs/outer_base_material.npz','inputs/base_residual.npy','endpoints-map08/manifest.json'):
        actual=pipeline.claim(ROOT/SOURCE/name);expected=inventory[name]
        if any(actual[k]!=expected[k] for k in ('size_bytes','sha256')):raise RuntimeError('source differs from reviewed archive')
        claims.append(actual)
    state=pipeline.read(ROOT/SOURCE/'maps/state.json')
    if state['active_map'] or state.get('pending_feedback') or state['history']!=review['history']:raise RuntimeError('source unsettled or replaced')
    if not eligible(pipeline.read(ROOT/SOURCE/'summary.json'),state['history']):raise RuntimeError('precision diagnostic not justified')
    reference=pipeline.read(ROOT/SOURCE/'inputs/feedback_reference.json');sources=reference['sources']
    base=load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
    old=load_arrays(ROOT/sources['physical_old_time_level']['path']);trial=load_arrays(ROOT/SOURCE/'maps/trial_material.npz')
    fresh.bridge.validate_identity(trial,base,r,old)
    # Reuse the exact accepted x17 endpoint pair; never reset the residual denominator.
    previous_review=pipeline.read(ROOT/'handoff/evidence/20260924-common-confirmation17-review.json')
    reused.verify([previous_review['archive']])
    with tarfile.open(ROOT/previous_review['archive']['path']) as archive:
        previous_inventory={c['path']:c for c in json.load(archive.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    vectors={}
    for e in ('previous','final'):
        f=ROOT/BASE/'common-feedback'/f'{e}_response.npz';actual=pipeline.claim(f)
        expected=previous_inventory[f'confirm2/common-feedback/{e}_response.npz']
        if any(actual[k]!=expected[k] for k in ('size_bytes','sha256')):raise RuntimeError('baseline response replaced')
        vectors[e]=load_arrays(f)['residual'];claims.append(actual)
    if not np.array_equal(r,vectors['final']):raise RuntimeError('r17 denominator changed')
    acceptance_path=ROOT/'handoff/evidence/20260924-accepted-step17.json';acceptance=pipeline.read(acceptance_path)
    if acceptance['accepted_outer_steps']!=17 or acceptance['coupled_column_converged']:raise RuntimeError('acceptance record changed')
    reused.verify(acceptance['claims']);claims.append(pipeline.claim(acceptance_path))
    retained=pipeline.read(ROOT/SOURCE/'endpoints-map08/manifest.json')
    seed=retained['endpoints']['mapped_final'];last=state['history'][-1]
    if (seed['sha256']!=last['output_sha256'] or state['current_sha256']!=last['output_sha256']
        or last['output_path']!=state['slots'][state['current_slot']]):raise RuntimeError('seed is not latest mapped successor')
    claims+=[seed]+list(sources.values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/common_step18_precision.sbatch',
        'tests/test_common_step18_precision.py','handoff/protocols/common-step18-precision-v1.md')]
    plan={'cases':{'trial':{'trial':pipeline.claim(ROOT/SOURCE/'maps/trial_material.npz'),
        'config':pipeline.claim(ROOT/SOURCE/'maps/config.json')}},'seed':seed,'code':code,'claims':claims,
        'environment':pipeline.environment(),'accepted_outer_steps':17,'maximum_new_maps':8,'first_stage_maps':4,
        'conditional_second_stage_maps':4,'maximum_feedback_pairs':2,'feedback_after_maps':[4,8],
        'automatic_promotion':False,'fixed_candidate':True,'physical_dt_changed':False}
    reused.verify(claims+code);reused.immutable(out/'declaration.json',plan)
    return plan,reference,vectors,old['cell_mass_g_cm2']

def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage must be disabled')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=17,new_material_steps=0,updated_unix=time.time(),**kw))
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
                    if n==4:
                        mark('stopped_after_four_inner_not_ready',completed_maps=4)
                        reused.immutable(out/'summary.json',{'status':'stopped_after_four_inner_not_ready','pairs':reports,'accepted_outer_steps':17,'new_material_steps':0})
                        reused.archive(out,'stopped-inner');return
                    reused.archive(out,f'map{n:02d}-inner-not-ready');continue
                if n==4 and not allow_second_half(state['history']):
                    mark('stopped_after_four_without_progress',completed_maps=4)
                    reused.archive(out,'stopped-progress');return
                rd=out/f'pair{n:02d}';rd.mkdir()
                p=fresh.new_protocol(reference,rd,retained['endpoints'],retained['history_rows'],16)
                p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz')
                p['sources']['retained_manifest']=pipeline.claim(out/f'endpoints-map{n:02d}/manifest.json')
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];fresh.exact_identity(p)
                path=rd/'feedback_protocol.json';reused.immutable(path,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',after_maps=n)
                with reused.feedback_stop_guard():result=pair.run_pair(path,pipeline.sha256(path))
                post=verify_step18_pair(rd,p,result)
                report={'original_gates':result['gate_checks'],'all_original_gates':all_pair_gates(result),
                    'physical_response_failures':result.get('material_response_failures',{}),'postcheck':pipeline.claim(rd/'postcheck.json')}
                if not report['physical_response_failures']:
                    vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                    report['fresh_baseline_comparison']=cross_comparisons(vectors,base_vectors,mass)
                    report['pair_supported']=report['all_original_gates'] and report['fresh_baseline_comparison']['passed']
                reports[str(n)]=report;reused.immutable(rd/'decision.json',report)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'map{n:02d}-feedback')
                if report['physical_response_failures']:
                    mark('physical_domain_rejected',after_maps=n);reused.archive(out,'physical-domain-rejected');return
        reused.verify(plan['claims']+plan['code'])
        supported=reports.get('8',{}).get('pair_supported',False)
        terminal='candidate_supported_requires_review' if supported else 'budget_complete_not_accepted'
        reused.immutable(out/'summary.json',{'status':terminal,'pairs':reports,'accepted_outer_steps':17,'new_material_steps':0})
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
