"""Explicit single-slab diagonal resource driver; current 86304 inputs use a separately frozen source manifest."""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import platform
import signal
import subprocess
import time
import traceback
import sys
import resource
import numpy as np
from operations import x20_85889_chord_scan as core
from operations import x20_85889_chord_scan_diagonal as diagonal
from operations import x20_85889_chord_resource as v1
from operations import x20_85889_chord_resource_v2 as v2
from operations import x20_86304_radiation_contract as contract

SECONDS = 1500
RSS_BYTES = 6442450944


def process_observation():
    """瞬时进程树RSS与已结束子进程历史rusage分别记录，不能相加冒充峰值。"""
    raw=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,comm='],text=True,timeout=5)
    rows=[]
    for line in raw.splitlines():
        parts=line.split(None,3)
        if len(parts)==4: rows.append(dict(pid=int(parts[0]),ppid=int(parts[1]),rss_bytes=int(parts[2])*1024,command=parts[3]))
    descendants={os.getpid()}
    while True:
        expanded=descendants|{r['pid'] for r in rows if r['ppid'] in descendants}
        if expanded==descendants: break
        descendants=expanded
    selected=[r for r in rows if r['pid'] in descendants]
    for r in selected:
        if r['pid']!=os.getpid() and Path(r['command']).name not in ('ps','git','scontrol'): raise ValueError('unexpected numerical child')
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(sampled_processes=selected,instantaneous_tree_rss_bytes=sum(r['rss_bytes'] for r in selected),
        ended_children_maxrss_native_units=usage.ru_maxrss,ended_children_user_s=usage.ru_utime,
        ended_children_system_s=usage.ru_stime,platform=sys.platform,
        historical_child_peak_is_not_concurrent_tree_peak=True)


class Timeline:
    def __init__(self, guard, output=None):
        self.guard = guard; self.origin = guard.started; self.rows = []; self.output = output

    @contextmanager
    def stage(self, name, payload=0):
        self.guard.check(); start = time.monotonic()-self.origin
        yield
        end = time.monotonic()-self.origin
        self.guard.check()
        observation=process_observation()
        row = dict(process_observation=observation, name=name, start_s=start, end_s=end, seconds=end-start,
                   payload_bytes=payload, payload_bytes_per_second=payload/(end-start) if end>start else None,
                   cumulative_peak_rss_bytes=core.peak_rss_bytes())
        self.rows.append(row)
        if self.output: v1.write_new(self.output/f'phase-{len(self.rows):02d}.json', row)


def authenticated_probe(claims, shape, guard, timeline=None, progress=lambda name, data: None):
    """All full hashes precede the only new-kernel call. Buffers and descriptors stay alive."""
    contract.check_errstate(np.geterr())
    v2.validate_claims(claims, shape)
    for claim in claims:
        if any(p.is_symlink() for p in (Path(claim['path']),*Path(claim['path']).parents)): raise ValueError('field ancestor link')
    if any(type(c['size_bytes']) is not int for c in claims): raise ValueError('integer source size')
    t = timeline or Timeline(guard); initial = [core.checked_stat(c) for c in claims]
    total = sum(c['size_bytes'] for c in claims)
    with t.stage('field-hash-before', total): before = core.hash_pass(claims, initial, guard)
    before_s = t.rows[-1]['seconds']
    progress('field-hash-before', dict(sha256=before, source_stats=initial, seconds=before_s))
    nbytes = 32*shape[1]*shape[2]*8; buffers = []; fields = []; hashes = []; read_s = []
    with ExitStack() as stack:
        handles = [stack.enter_context(os.fdopen(os.open(c['path'],os.O_RDONLY|os.O_NOFOLLOW),'rb')) for c in claims]
        def unchanged():
            if ([core.signature(os.fstat(f.fileno())) for f in handles] != initial or
                [core.checked_stat(c) for c in claims] != initial): raise ValueError('source/handle changed')
        unchanged()
        for i, f in enumerate(handles):
            with t.stage(f'slice-read-{i}', nbytes):
                raw = f.read(nbytes)
                if len(raw) != nbytes: raise ValueError('short slice')
            read_s.append(t.rows[-1]['seconds']); buffers.append(raw)
            with t.stage(f'slice-hash-{i}'):
                hashes.append(hashlib.sha256(raw).hexdigest())
                fields.append(np.frombuffer(raw, dtype='<f8').reshape(32, *shape[1:]))
        unchanged()
        with t.stage('slab'): row = diagonal.slab_statistics(fields, guard.check)
        calculation_s = t.rows[-1]['seconds']; unchanged()
        for i, (f, sha) in enumerate(zip(handles, hashes)):
            with t.stage(f'slice-reread-{i}', nbytes):
                f.seek(0); raw = f.read(nbytes)
                if len(raw) != nbytes or hashlib.sha256(raw).hexdigest() != sha:
                    raise ValueError('slice changed')
        unchanged()
    probe = dict(status='resource_probe_complete_requires_review', shape=list(shape), first_group=0, group_count=32,
        source_claims=claims, source_stats_before=initial, source_stats_after=initial, slice_sha256=hashes,
        field_bytes_read=12*nbytes, read_seconds_first_pass=read_s, calculation_seconds=calculation_s,
        peak_rss_bytes=core.peak_rss_bytes(), slab=row,
        arithmetic=dict(rounding_mode_code=core.rounding_mode(), nmant=np.finfo(np.longdouble).nmant,
                        maxexp=np.finfo(np.longdouble).maxexp, numpy=np.__version__),
        full_field_sha_refreshed=False, full_field_statistics_complete=False, physical_inference_authorized=False,
        full_scan_authorized=False, new_maps=0, new_feedback=0, new_material=0, strict_error_bound=False)
    progress('probe', probe)
    with t.stage('field-hash-after', total): after = core.hash_pass(claims, initial, guard)
    after_s = t.rows[-1]['seconds']; final = [core.checked_stat(c) for c in claims]
    if final != initial or before != after: raise ValueError('source changed after statistics')
    progress('field-hash-after', dict(sha256=after, source_stats=final, seconds=after_s))
    contract.check_errstate(np.geterr())
    return dict(status=contract.STATUS, version=contract.SCHEMA, probe=probe, source_claims=claims,
        source_stats_before=initial, source_stats_after=final, full_sha256_before=before, full_sha256_after=after,
        full_hash_seconds_before=before_s, full_hash_seconds_after=after_s, field_bytes_read=2*total+12*nbytes,
        source_job=86304, global_h1=None, full_field_sha_refreshed=True, full_field_statistics_complete=False, full_scan_authorized=False,
        physical_inference_authorized=False, strict_error_bound=False, new_maps=0, new_feedback=0, new_material=0,
        kernel_calls=1, labels=['AP','AF','AM','HP','HF','HM'], phases=t.rows, python=platform.python_version(), platform=platform.platform())


def runtime_identity(repo, code):
    """核实际载入的项目模块；不把未执行的清单文件当执行证明。"""
    repo = Path(repo).resolve(); modules = {}
    project_names = {Path(p).stem for p in code}
    namespaces = ('operations', 'handoff', 'hpc', 'eccentric_tde_observer', 'scripts')
    for name, module in sorted(list(sys.modules.items())):
        file = getattr(module, '__file__', None)
        if not file: continue
        path = Path(file).absolute(); resolved = path.resolve()
        is_project = resolved.is_relative_to(repo) and not any(part.startswith('.venv') for part in resolved.relative_to(repo).parts)
        expected_project = name.split('.')[0] in namespaces or name in project_names
        if not is_project and not expected_project: continue
        if path != resolved or not resolved.is_relative_to(repo): raise ValueError('foreign/symlink project import: '+name)
        relative = str(resolved.relative_to(repo))
        spec = getattr(module, '__spec__', None)
        origin = getattr(spec, 'origin', None) or file
        if Path(origin).absolute() != resolved or relative not in code: raise ValueError('unfrozen module origin: '+name)
        raw = contract.bounded_bytes(resolved, 32*1024**2)
        fingerprint = dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if not contract.exact(fingerprint, code[relative]): raise ValueError('loaded module SHA: '+name)
        modules[name] = dict(relative_path=relative, file=str(resolved), origin=str(resolved), fingerprint=fingerprint)
    identity = dict(checkout=str(repo), modules=modules, errstate=np.geterr(),
        environment=dict(executable=str(Path(sys.executable).absolute()), python_version=platform.python_version(),
            numpy_file=str(Path(np.__file__).resolve()), numpy_origin=str(Path(np.__spec__.origin).resolve()), numpy_version=np.__version__))
    contract.check_identity(identity, code)
    return identity


def code_manifest(repo):
    """All tracked Python/sbatch dependencies; new files must be frozen before production."""
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode().split('\0')
    result = {}
    for name in names:
        if name.endswith(('.py', '.sbatch')):
            p = Path(repo)/name
            if p.is_symlink() or not p.is_file(): raise ValueError('ordinary code file required')
            raw = p.read_bytes(); result[name] = dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    contract.check_code(result, result)
    return result


def execute(run, work, execution_arguments=None):
    run = Path(run); run.mkdir(parents=False, exist_ok=False)
    stopped = []; previous = {}
    guard = core.Guard(seconds=SECONDS, rss_bytes=RSS_BYTES, stop=lambda:bool(stopped))
    for sig in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, lambda n, frame:stopped.append(n))
    try:
        v1.write_new(run/'started.json', dict(status='incomplete', version=contract.SCHEMA, started_unix=time.time(),
            arguments=execution_arguments or {}, pid=os.getpid(), program_seconds=SECONDS, rss_limit_bytes=RSS_BYTES,
            execution=dict(job_id=os.environ.get('SLURM_JOB_ID'), workdir=str(Path.cwd().resolve()),
                run=str(run.resolve()), driver=str(Path(__file__).resolve()))))
        timeline = Timeline(guard, run); result = work(guard, run, timeline)
        guard.check(); result['phases'] = timeline.rows
        v1.write_new(run/'result.json', result); guard.check()
        v1.write_new(run/'finished.json', dict(status=contract.STATUS, wall_s=time.monotonic()-guard.started,
            peak_rss_bytes=core.peak_rss_bytes(), scheduler_terminal_verified=False, full_scan_authorized=False))
        return 0
    except BaseException as error:
        v1.write_new(run/'failure.json', dict(status='failed_or_interrupted', error_type=type(error).__name__,
            error=str(error), traceback=traceback.format_exc(), signals=stopped,
            wall_s=time.monotonic()-guard.started, peak_rss_bytes=core.peak_rss_bytes(),
            scheduler_terminal_verified=False, full_scan_authorized=False))
        return 1
    finally:
        for sig, handler in previous.items(): signal.signal(sig, handler)



def main():
    p=argparse.ArgumentParser()
    for key in ('expected-commit','run','sources','code-freeze'): p.add_argument('--'+key,required=True)
    a=p.parse_args(); repo=Path.cwd().resolve(); run=Path(a.run).absolute()
    if not run.is_relative_to(repo/'outputs/hpc') or run==repo/'outputs/hpc': raise ValueError('exclusive hpc run')
    def work(guard,out,timeline):
        from operations import x20_86304_radiation_live as live
        with timeline.stage('allocation-code'):
            v1.allocation(os.environ); job=contract.new_job(os.environ['SLURM_JOB_ID']); v1.checkout(repo,a.expected_commit)
            raw=subprocess.check_output(['scontrol','show','job','-o',job],text=True,timeout=10)
            contract.scheduler_tokens(raw); v1.write_new(out/'allocation.json',v2.scheduler_allocation(job,raw))
            code=code_manifest(repo); contract.check_code(code,contract.read(a.code_freeze))
            v1.write_new(out/'code-before.json',code); runtime_identity(repo,code)
            arithmetic=dict(rounding_mode_code=core.rounding_mode(),nmant=np.finfo(np.longdouble).nmant,maxexp=np.finfo(np.longdouble).maxexp,numpy=np.__version__)
            if not contract.exact(arithmetic,contract.ARITHMETIC): raise ValueError('production arithmetic')
            sources=contract.read(a.sources); live.validate_manifest(sources)
        with timeline.stage('source-before',sources['payload_bytes_per_check']):
            before=live.check(repo,sources,guard); v1.write_new(out/'source-before.json',before)
            identity=runtime_identity(repo,code); contract.check_identity(identity,code,True)
            v1.write_new(out/'identity-before.json',identity)
        claims=[dict(c,path=str(repo/c['path'])) for c in contract.fields(sources['binding'])]
        result=authenticated_probe(claims,contract.SHAPE,guard,timeline,lambda n,d:v1.write_new(out/(n+'.json'),d))
        with timeline.stage('source-after',sources['payload_bytes_per_check']):
            after=live.check(repo,sources,guard)
            if not contract.exact(before,after): raise ValueError('current science sources changed')
            v1.write_new(out/'source-after.json',after)
        with timeline.stage('code-after'):
            v1.checkout(repo,a.expected_commit); current=code_manifest(repo); contract.check_code(current,code)
            v1.write_new(out/'code-after.json',current); later=runtime_identity(repo,code)
            contract.check_identity_pair(identity,later,code,True); v1.write_new(out/'identity-after.json',later)
        result.update(git_commit=a.expected_commit,git_clean_before_after=True,job_id=job,
            peak_rss_bytes=core.peak_rss_bytes(),source_before=before,source_after=after,
            source_payload_bytes=2*sources['payload_bytes_per_check'],archive_bytes_read=915885482,
            code_bytes_read=2*sum(c['size_bytes'] for c in code.values()))
        return result
    return execute(run,work,dict(expected_commit=a.expected_commit,run=str(run),sources=str(Path(a.sources).absolute()),code_freeze=str(Path(a.code_freeze).absolute())))

if __name__=='__main__': raise SystemExit(main())
