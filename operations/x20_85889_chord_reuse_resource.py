"""Explicit single-slab reuse resource driver; production inputs are fixed by history."""
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
import numpy as np
from operations import x20_85889_chord_scan as core
from operations import x20_85889_chord_scan_reuse as reuse
from operations import x20_85889_chord_resource as v1
from operations import x20_85889_chord_resource_v2 as v2
from operations import x20_85889_chord_binding as binding
from operations import x20_85889_chord_reuse_contract as contract

SECONDS = 1500
RSS_BYTES = 6442450944


class Timeline:
    def __init__(self, guard, output=None):
        self.guard = guard; self.origin = guard.started; self.rows = []; self.output = output

    @contextmanager
    def stage(self, name, payload=0):
        self.guard.check(); start = time.monotonic()-self.origin
        yield
        end = time.monotonic()-self.origin
        self.guard.check()
        row = dict(name=name, start_s=start, end_s=end, seconds=end-start,
                   payload_bytes=payload, payload_bytes_per_second=payload/(end-start) if end>start else None,
                   cumulative_peak_rss_bytes=core.peak_rss_bytes())
        self.rows.append(row)
        if self.output: v1.write_new(self.output/f'phase-{len(self.rows):02d}.json', row)


def authenticated_probe(claims, shape, guard, timeline=None, progress=lambda name, data: None):
    """All full hashes precede the only new-kernel call. Buffers and descriptors stay alive."""
    v2.validate_claims(claims, shape)
    if any(type(c['size_bytes']) is not int for c in claims): raise ValueError('integer source size')
    t = timeline or Timeline(guard); initial = [core.checked_stat(c) for c in claims]
    total = sum(c['size_bytes'] for c in claims)
    with t.stage('field-hash-before', total): before = core.hash_pass(claims, initial, guard)
    before_s = t.rows[-1]['seconds']
    progress('field-hash-before', dict(sha256=before, source_stats=initial, seconds=before_s))
    nbytes = 32*shape[1]*shape[2]*8; buffers = []; fields = []; hashes = []; read_s = []
    with ExitStack() as stack:
        handles = [stack.enter_context(Path(c['path']).open('rb')) for c in claims]
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
        with t.stage('slab'): row = reuse.slab_statistics(fields, guard.check)
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
    return dict(status=contract.STATUS, version=3, probe=probe, source_claims=claims,
        source_stats_before=initial, source_stats_after=final, full_sha256_before=before, full_sha256_after=after,
        full_hash_seconds_before=before_s, full_hash_seconds_after=after_s, field_bytes_read=2*total+12*nbytes,
        full_field_sha_refreshed=True, full_field_statistics_complete=False, full_scan_authorized=False,
        physical_inference_authorized=False, strict_error_bound=False, new_maps=0, new_feedback=0, new_material=0,
        kernel_calls=1, phases=t.rows, python=platform.python_version(), platform=platform.platform())


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


def execute(run, work):
    run = Path(run); run.mkdir(parents=False, exist_ok=False)
    stopped = []; previous = {}
    guard = core.Guard(seconds=SECONDS, rss_bytes=RSS_BYTES, stop=lambda:bool(stopped))
    for sig in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, lambda n, frame:stopped.append(n))
    try:
        v1.write_new(run/'started.json', dict(status='incomplete', version=3, started_unix=time.time(),
            pid=os.getpid(), program_seconds=SECONDS, rss_limit_bytes=RSS_BYTES))
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
    p = argparse.ArgumentParser()
    for key in ('expected-commit', 'run', 'inventory', 'source-review', 'history'):
        p.add_argument('--'+key, required=True)
    a = p.parse_args(); repo = Path.cwd(); v1.allocation(os.environ); v1.checkout(repo, a.expected_commit)
    run = Path(a.run).resolve()
    if not run.is_relative_to(repo/'outputs/hpc') or run == repo/'outputs/hpc': raise ValueError('new hpc directory required')
    def work(guard, out, timeline):
        from operations.x20_85889_chord_live import live_check
        with timeline.stage('allocation-code-history'):
            raw = subprocess.check_output(['scontrol', 'show', 'job', '-o', os.environ['SLURM_JOB_ID']], text=True, timeout=10)
            contract.scheduler_tokens(raw)
            v1.write_new(out/'allocation.json', v2.scheduler_allocation(os.environ['SLURM_JOB_ID'], raw))
            code = code_manifest(repo); v1.write_new(out/'code-before.json', code)
            reference, blobs = contract.history(a.history)
            for name, blob in blobs.items():
                with (out/name).open('xb') as f: f.write(blob)
            if reference['shape'] != [9632, 32, 4096]: raise ValueError('production history layout')
            arithmetic = dict(rounding_mode_code=core.rounding_mode(), nmant=np.finfo(np.longdouble).nmant,
                              maxexp=np.finfo(np.longdouble).maxexp, numpy=np.__version__)
            if not contract.exact(arithmetic, contract.ARITHMETIC): raise ValueError('production arithmetic')
        received = repo/binding.RUN
        protocol = contract.read(received/'accelerated/pair16/feedback_protocol.json')
        locations = {k:repo/protocol['sources'][k]['path'] for k in binding.PHYSICAL_SHA}
        with timeline.stage('binding-before'):
            bound = binding.bind(repo, received, Path(a.inventory), Path(a.source_review), locations)
            v1.write_new(out/'binding-before.json', bound)
        with timeline.stage('live-before', 303877902):
            live = live_check(repo, bound, guard); v1.write_new(out/'live-before.json', live)
        claims = [dict(c, path=str(repo/c['path'])) for c in bound['field_claims']]
        if bound['shape'] != reference['shape']: raise ValueError('production shape')
        identities = lambda cs:[(x['size_bytes'], x['sha256']) for x in cs]
        if identities(claims) != identities(reference['source_claims']): raise ValueError('production history fields')
        result = authenticated_probe(claims, bound['shape'], guard, timeline,
            lambda name, data:v1.write_new(out/(name+'.json'), data))
        with timeline.stage('binding-after'):
            after = binding.bind(repo, received, Path(a.inventory), Path(a.source_review), locations)
            if after != bound: raise ValueError('small sources changed')
            v1.write_new(out/'binding-after.json', after)
        with timeline.stage('live-after', 303877902):
            live_after = live_check(repo, after, guard)
            stable = lambda x:{k:v for k,v in x.items() if k != 'environment_metadata_reads'}
            if stable(live) != stable(live_after): raise ValueError('live sources changed')
            v1.write_new(out/'live-after.json', live_after)
        with timeline.stage('code-after'):
            v1.checkout(repo, a.expected_commit); current = code_manifest(repo)
            contract.check_code(current, code); v1.write_new(out/'code-after.json', current)
        with timeline.stage('comparison'):
            comparison = contract.compare(result['probe'], reference)
            v1.write_new(out/'comparison.json', comparison)
        result.update(git_commit=a.expected_commit, git_clean_before_after=True, job_id=os.environ['SLURM_JOB_ID'],
            peak_rss_bytes=core.peak_rss_bytes(), live_before=live, live_after=live_after,
            comparison=comparison, archive_bytes_read=607755804,
            historical_bytes_read=sum(len(b) for b in blobs.values()),
            code_bytes_read=2*sum(c['size_bytes'] for c in code.values()))
        return result
    return execute(run, work)


if __name__ == '__main__': raise SystemExit(main())
