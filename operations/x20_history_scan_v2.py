"""Serial scan entry: four allocated CPUs are not four radiation workers.

Separate wrapper leaves job 80823's frozen x20_history_operator bytes untouched.
"""
import argparse,os,resource,signal,sys,time
from pathlib import Path
from operations import x20_history_operator as core
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused


def require_scan_allocation():
    # 流式扫描只有一个父进程；沿用一worker的8GiB守卫，再独立要求获配4CPU。
    pipeline.require_allocation(1)
    if int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<4:raise RuntimeError('four allocated CPUs required')
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')


def execute(out):
    require_scan_allocation();out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,mode='scan',accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        wrapper=[pipeline.claim(ROOT/p) for p in ('operations/x20_history_scan_v2.py','operations/x20_history_scan_v2.sbatch',
            'tests/test_x20_history_scan_allocation.py','handoff/protocols/x20-history-scan-resource-v2.md')]
        reused.immutable(out/'scan_driver_declaration.json',dict(code=wrapper,previous_failed_job=80822,
            allocated_cpus_required=4,simultaneous_scan_processes=1,previous_job_scanned_fields=0,science_protocol_unchanged=True))
        plan,geometry=core.prepare(out,'scan');mark('scanning')
        result=core.collect_scan([ROOT/c['path'] for c in plan['field_pairs']],pipeline.SHAPE,geometry,reused.checkpoint)
        reused.immutable(out/'prediction.json',result);reused.verify(plan['claims']+plan['code']+wrapper)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent memory guard')
        reused.immutable(out/'summary.json',dict(status='complete_requires_review',mode='scan',source_job=80554,
            new_maps=0,new_feedback_pairs=0,accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,
            strict_error_bound=False,scan_feasible=result['feasible'],affinity_pass=None,parent_peak_rss_bytes=peak,
            wall_s=time.monotonic()-started,historical_failures_retained=True,allocation_wrapper_version=2))
        mark('complete_requires_review');reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
