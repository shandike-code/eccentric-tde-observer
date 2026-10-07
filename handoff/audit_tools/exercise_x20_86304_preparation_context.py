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
    pack = json.loads(sys.stdin.buffer.read(32*1024**2))
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
    context_module = importlib.import_module('operations.x20_86304_preparation_context')
    guard.check()
    old = {'density_g_cm3':np.ones((2,128)), 'temperature_k':np.full((2,128),10000.),
           'hydrogen_fraction':np.broadcast_to([.75,.25],(2,128,2)).copy(),
           'helium_fraction':np.broadcast_to([.5,.25,.25],(2,128,3)).copy(),
           'cell_mass_g_cm2':np.ones(128),'step_duration_s':np.ones(2)}
    master = {'active_edge_hz':np.arange(1.,9634.),'maximum_beta':np.array(0.)}
    meter = adapter.ArrayLoader()
    raw_sources = {}; loaded = {}
    for name, data in [('old',old),('master',master)]:
        stream=io.BytesIO();np.savez_compressed(stream,**data);raw=stream.getvalue()
        raw_sources[name]=base64.b64encode(raw).decode()
        loaded[name]=meter.npz(raw,hashlib.sha256(raw).hexdigest(),name)
    context=context_module.context_from_arrays(loaded['old'],loaded['master'],guard.check)
    def array_fact(a):
        return dict(dtype=a.dtype.str,shape=list(a.shape),sha256=hashlib.sha256(a.tobytes()).hexdigest(),
                    data_base64=base64.b64encode(a.tobytes()).decode())
    def stencil_fact(stencil):
        return {k:(array_fact(v) if isinstance(v,np.ndarray) else v) for k,v in vars(stencil).items()}
    facts={k:context[k] for k in ('phase','following','duration_s','selected_block_index','identified_live_bytes')}
    facts['arrays']={k:array_fact(context[k]) for k in ('face_beta','parent_beta','beta','mu','weight')}
    facts['full']={k:array_fact(v) for k,v in context['full'].items()}
    facts['stencil']=stencil_fact(context['stencil'])
    facts['blocks']=[{k:(stencil_fact(v) if k=='local_stencil' else v) for k,v in vars(b).items()} for b in context['blocks']]
    imported=adapter.origins(loader)
    print(json.dumps(dict(synthetic=True,production_ready=False,whole_lifecycle_guard_verified=False,
        complete_native_context_verified=False,seal=seal,source_npz=raw_sources,context=facts,
        executed_project_origins=imported,meter=meter.facts(),resources=guard.check(),
        startup_isolated_no_site=True,environment_preload_project_free=True,
        environment_origins=environment,frozen_project_module_count=len(rows))))


if __name__ == '__main__':
    main()
