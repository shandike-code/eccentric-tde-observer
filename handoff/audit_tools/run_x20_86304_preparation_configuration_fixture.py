"""Disposable synthetic old/master context planning after the process seal.

Run only with an external source pack, isolated Python and an external timeout.
No scientific source files are accepted by this entry point.
"""
import sys
import time
STARTED = time.monotonic()
import base64
import codecs
import hashlib
import importlib
import io
import json
import os


def main():
    # -I -S suppresses cwd/PYTHONPATH/user site/.pth startup execution. Explicit
    # site directory is supplied by the trusted outer launcher, not site.main().
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError('requires -I -S interpreter')
    sys.path.append(sys.argv[1])
    raw_pack = open(sys.argv[2], 'rb').read(32*1024**2)
    if hashlib.sha256(raw_pack).hexdigest() != sys.argv[3]:
        raise ValueError('external source pack SHA')
    pack = json.loads(raw_pack)
    for name in pack['environment_imports']:
        importlib.import_module(name)
    import concurrent.futures.process
    import concurrent.futures.thread
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot
    import numpy as np
    import stat
    import ctypes
    from importlib import abc
    import zipfile
    import platform
    import resource
    import signal
    codecs.lookup('cp437')
    # Bootstrap only the frozen guard/input/adapter sources, with their real
    # module names. No original scientific project module executes pre-seal.
    from types import ModuleType
    roots = {'operations': ModuleType('operations')}
    roots['operations'].__path__ = []
    sys.modules.update(roots)
    boot_names = ('operations.x20_86304_preparation_boundary',
                  'operations.x20_86304_preparation_inputs',
                  'operations.x20_86304_preparation_memory')
    for name in boot_names:
        row = pack['bootstrap'][name]
        raw = row['source'].encode()
        if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('bootstrap SHA')
        module = ModuleType(name)
        module.__file__ = pack['root'] + '/' + row['path']
        sys.modules[name] = module
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    boundary = sys.modules[boot_names[0]]
    adapter = sys.modules[boot_names[2]]
    guard = boundary.StopGuard(STARTED)
    guard.install()
    rows = dict(pack['modules'])
    rows.pop('operations')  # Explicit empty bootstrap namespace above.
    loader = adapter.frozen_project(rows, pack['root'])
    if any(n in sys.modules for n in rows):
        raise ValueError('project imported during environment preload')
    environment = {n: getattr(m, '__file__', None) for n, m in list(sys.modules.items())
                   if n not in boot_names and n != 'operations'}
    seal = boundary.seal()
    loader.install()
    target=importlib.import_module('operations.x20_86304_preparation_configuration')
    fixture_row=pack['fixture']
    raw_fixture=fixture_row['source'].encode()
    if hashlib.sha256(raw_fixture).hexdigest()!=fixture_row['sha256'] or len(raw_fixture)!=fixture_row['size_bytes']:
        raise ValueError('fixture source SHA')
    fixture_scope={}
    exec(compile(raw_fixture,pack['root']+'/'+fixture_row['path'],'exec'),fixture_scope)
    blobs,claims,warm,expected=fixture_scope['fixture'](9632)
    configured=target.configure_from_bytes(blobs,claims,warm,expected,guard.check)
    result=fixture_scope['facts'](configured,blobs,claims)
    result.update(seal=seal,executed_project_origins=adapter.origins(loader),resources=guard.check(),
        startup_isolated_no_site=True,environment_preload_project_free=True,
        environment_origins=environment,frozen_project_module_count=len(rows))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
