"""Bounded disposable-process supervisor; no native production entry point.

The caller must authenticate the executable, arguments and inputs separately.
This is a resource boundary, not a filesystem or hostile-code sandbox.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time


def supervise(argv, destination, *, outer_seconds=150.0, output_limit=8*1024**2):
    """Persist bounded stdout/stderr and a sticky parent-observed outcome.

    Includes process creation and pipe draining in the deadline. No retries.
    The child must install its own 120 s / 1 GiB StopGuard at entry.
    """
    if (not isinstance(argv, (tuple, list)) or not argv or
            any(type(x) is not str or not x or '\0' in x for x in argv) or
            not os.path.isabs(argv[0]) or
            type(outer_seconds) not in (float, int) or
            not math.isfinite(outer_seconds) or not 0 < outer_seconds <= 150 or
            type(output_limit) is not int or not 0 < output_limit <= 8*1024**2):
        raise ValueError('invalid bounded launch')
    destination = Path(destination)
    destination.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    state = {'schema': '86304-preparation-supervisor-v1', 'argv': list(argv),
             'outer_limit_s': outer_seconds, 'output_limit_bytes': output_limit,
             'reason': None, 'returncode': None, 'kill_sent': False,
             'success': False, 'whole_lifecycle_guard_verified': False,
             'production_authorized': False}
    # 父进程只保存停止事实；正常退出不认证物理输入或 native 配置。
    with (destination/'intent.json').open('x') as f:
        json.dump(state, f); f.flush(); os.fsync(f.fileno())
    child = None
    selector = selectors.DefaultSelector()
    streams = {}; counts = {'stdout': 0, 'stderr': 0}
    hashes = {name: hashlib.sha256() for name in counts}
    previous = {}
    def stopped(signum, frame):
        if state['reason'] is None:
            state['reason'] = 'parent_signal:' + str(signum)
    def kill():
        if child is not None and not state['kill_sent']:
            try:
                os.killpg(child.pid, signal.SIGKILL)
                state['kill_sent'] = True
            except ProcessLookupError:
                pass
    try:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
            previous[signum] = signal.signal(signum, stopped)
        for name in counts:
            streams[name] = (destination/(name+'.log')).open('xb')
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 close_fds=True, start_new_session=True)
        for name, pipe in [('stdout', child.stdout), ('stderr', child.stderr)]:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map() or child.poll() is None:
            remaining = outer_seconds - (time.monotonic()-started)
            if remaining <= 0 and state['reason'] is None:
                state['reason'] = 'outer_deadline'
            if state['reason'] is not None:
                kill()
            # Once failed, stop consuming output; the bounded prefix remains.
            if state['reason'] is not None:
                break
            for key, _ in selector.select(min(0.05, max(0., remaining))):
                raw = os.read(key.fileobj.fileno(), 65536)
                if not raw:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                name = key.data
                available = output_limit - sum(counts.values())
                kept = raw[:available]
                streams[name].write(kept)
                counts[name] += len(kept); hashes[name].update(kept)
                if len(raw) > available:
                    state['reason'] = 'output_limit'
                    kill()
                    break
        if state['reason'] is None:
            state['returncode'] = child.wait(timeout=max(.001, outer_seconds-(time.monotonic()-started)))
            if state['returncode'] != 0:
                state['reason'] = 'child_exit'
    except BaseException as error:
        if state['reason'] is None:
            state['reason'] = 'parent_exception:' + type(error).__name__
        kill()
        raise
    finally:
        if child is not None:
            if state['reason'] is not None:
                kill()
            # Reap after SIGKILL; a kernel uninterruptible task can delay this.
            # Do not claim an OS scheduling/reaping latency bound.
            state['returncode'] = child.wait()
            for pipe in (child.stdout, child.stderr):
                pipe.close()
        selector.close()
        for stream in streams.values():
            stream.flush(); os.fsync(stream.fileno()); stream.close()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        state['elapsed_s'] = time.monotonic()-started
        if state['elapsed_s'] >= outer_seconds and state['reason'] is None:
            state['reason'] = 'outer_deadline'
        state['success'] = state['reason'] is None and state['returncode'] == 0
        state['outputs'] = {name: {'size_bytes': counts[name], 'sha256': hashes[name].hexdigest()}
                            for name in counts}
        with (destination/'outcome.json').open('x') as f:
            json.dump(state, f, indent=2); f.flush(); os.fsync(f.fileno())
    return state


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: full native preparation is not accepted')
