"""Tiny disposable-process fault injection; never accepts scientific input paths."""
import argparse
import ctypes
import codecs
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

from operations import x20_86304_preparation_boundary as boundary


def child(mode, directory):
    started = time.monotonic()
    import numpy as np
    codecs.lookup('cp437')  # ZIP directory decoder: environment preload, not project code.
    from operations.x20_86304_preparation_inputs import Budget, MeteredBytes
    # All test inputs are created here, before sealing, inside this tiny fixture.
    root = Path(directory)
    target = root / 'synthetic.dat'
    target.write_bytes(b'synthetic only\n')
    (root / 'alias.bin').symlink_to('synthetic.dat')
    os.link(target, root / 'hard.bin')
    holder = io.BytesIO()
    np.savez(holder, x=np.arange(12, dtype=np.float64).reshape(4, 3))
    raw = holder.getvalue()
    del holder
    entry = b'import os\nvalue = 42\n'
    failing = ('import os\nos.stat(' + repr(str(target)) + ')\n').encode()
    modules = boundary.FrozenModules({
        'sealed_good': (entry, hashlib.sha256(entry).hexdigest(), '/frozen/good.py', False),
        'sealed_bad': (failing, hashlib.sha256(failing).hexdigest(), '/frozen/bad.py', False)})
    libc = ctypes.CDLL(None, use_errno=True)
    libc.open.argtypes = [ctypes.c_char_p, ctypes.c_int]
    libc.open.restype = ctypes.c_int
    guard = boundary.StopGuard(time.monotonic() if mode == 'signal-time' else started, seconds=0.15 if mode == 'signal-time' else 10,
                               rss_bytes=1 if mode == 'rss' else 1024**3)
    if mode == 'rss':
        try:
            guard.install()
        except RuntimeError as error:
            print(json.dumps({'mode': mode, 'rejected': str(error)}))
            return
        raise AssertionError('RSS not rejected')
    guard.install()
    backend = boundary.seal()
    modules.install()
    if mode == 'hard-time':
        # Simulates C/foreign code ignoring cooperative signals; parent must kill.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        time.sleep(5)
        raise AssertionError('external deadline missing')
    if mode == 'signal-time':
        try:
            time.sleep(5)
        except RuntimeError:
            try:
                guard.check()
            except RuntimeError as error:
                print(json.dumps({'mode': mode, 'rejected': str(error), 'backend': backend}))
                return
        raise AssertionError('wall signal not sticky')
    denied = []
    unproven = []
    def reject(name, action):
        try:
            action()
        except (PermissionError, ModuleNotFoundError):
            denied.append(name)
        except OSError as error:
            unproven.append({'operation': name, 'errno': error.errno})
        else:
            raise AssertionError('access allowed: ' + name)
    for basename in ('synthetic.dat', 'alias.bin', 'hard.bin', 'absent.dat'):
        name = str(root / basename)
        reject(basename + ':open', lambda: open(name, 'rb'))
        reject(basename + ':stat', lambda: os.stat(name))
        reject(basename + ':lstat', lambda: os.lstat(name))
        reject(basename + ':readlink', lambda: os.readlink(name))
        ctypes.set_errno(0)
        result = libc.open(name.encode(), 0)
        if result != -1:
            raise AssertionError('libc open allowed')
        if ctypes.get_errno() in (1, 13):
            denied.append(basename + ':libc-open')
        else:
            unproven.append({'operation': basename + ':libc-open', 'errno': ctypes.get_errno()})
    reject('listdir', lambda: os.listdir(root))
    reject('import-time-stat', lambda: __import__('sealed_bad'))
    reject('unknown-import', lambda: __import__('sealed_missing'))
    reject('fork', os.fork)
    reject('exec', lambda: os.execv('/usr/bin/true', ['true']))
    __import__('sealed_good')
    if sys.modules['sealed_good'].value != 42:
        raise AssertionError('memory import failed')
    budget = Budget(256 * 1024)
    reader = MeteredBytes(raw, budget, [], 'synthetic.npz')
    with np.load(reader, allow_pickle=False) as archive:
        array = np.array(archive['x'], copy=True)
    if not np.array_equal(array, np.arange(12, dtype=np.float64).reshape(4, 3)):
        raise AssertionError('in-memory NumPy decode differs')
    facts = guard.check()
    print(json.dumps({'mode': mode, 'backend': backend, 'denied': denied,
                      'unproven': unproven, 'all_path_probes_denied': not unproven,
                      'memory_imports': modules.executed,
                      'synthetic_npz_bytes': len(raw),
                      'consumer_returned_bytes': budget.used,
                      'array_sha256': hashlib.sha256(array.tobytes()).hexdigest(),
                      'resources': facts, 'synthetic_only': True,
                      'environment_preload_protected': False,
                      'native_adapter_integrated': False}))


def exercise(output):
    output.mkdir()
    records = []
    for mode in ('normal', 'rss', 'signal-time', 'hard-time'):
        directory = output / mode
        directory.mkdir()
        argv = [sys.executable, __file__, '--child', mode, '--directory', str(directory)]
        started = time.monotonic()
        with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, start_new_session=True) as process:
            timed_out = False
            try:
                stdout, stderr = process.communicate(timeout=3 if mode == 'hard-time' else 15)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
            record = {'mode': mode, 'returncode': process.returncode,
                      'elapsed_s': time.monotonic() - started,
                      'external_timeout': timed_out,
                      'stdout': stdout.decode(), 'stderr': stderr.decode()}
        (output / (mode + '.json')).write_text(json.dumps(record, indent=2) + '\n')
        if mode == 'hard-time':
            assert timed_out and process.returncode == -signal.SIGKILL, record
        else:
            assert process.returncode == 0 and not stderr and not timed_out, record
            value = json.loads(stdout)
            if mode == 'normal':
                assert len(value['denied']) + len(value['unproven']) == 25
                assert value['memory_imports'] == ['sealed_good']
                if sys.platform == 'linux':
                    assert value['all_path_probes_denied'] is True, value
            else:
                assert 'rejected' in value
        records.append(record)
    (output / 'result.json').write_text(json.dumps({
        'synthetic_only': True, 'cases': records,
        'whole_lifecycle_environment_boundary_verified': False,
        'actual_source_manifest_prepared': False,
        'new_production_authorized': False}, indent=2) + '\n')
    print(json.dumps({'synthetic_cases_completed': len(records), 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', choices=('normal', 'rss', 'signal-time', 'hard-time'))
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if args.child:
        child(args.child, args.directory)
    else:
        exercise(args.directory)
