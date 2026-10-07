"""Disposable tiny synthetic exercise of frozen original imports and exact_trial.

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
    directions = importlib.import_module('operations.common_step21_directions')
    column = importlib.import_module('scripts.phase7b5x_full_depth_block_probe')
    guard.check()
    imported = adapter.origins(loader)
    # Synthetic control: two phases and 128 half-column cells, no physical data.
    cells = 128
    codec = directions.GroundStateLogSimplexCodec(cells)
    encoded = np.tile(np.array([30., -.5, -.25, .125]), cells)
    decoded = codec.decode(encoded)
    residual = np.zeros(4*cells)
    base = {k: np.array(getattr(decoded, k), copy=True) for k in
            ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    base.update(density_g_cm3=np.full(cells, 1e-10), phase_index=np.array(0),
                step_duration_s=np.array(1.), relaxation=np.array(0.),
                encoded_state=encoded, base_encoded_state=encoded.copy(),
                base_residual=residual, finite_direction=residual.copy())
    old = {k: np.stack((base[k], base[k])) for k in
           ('density_g_cm3','temperature_k','hydrogen_fraction','helium_fraction')}
    old.update(step_duration_s=np.ones(2),cell_mass_g_cm2=np.full(cells, 1e-10))
    raw = io.BytesIO(); np.savez_compressed(raw, **base); raw = raw.getvalue()
    inputs = sys.modules[boot_names[1]]
    expected_facts = inputs.expected_fingerprints(raw, raw, inputs.Budget(512*1024**2),
                                                inputs.Budget(256*1024**2))
    meter = adapter.ArrayLoader()
    loaded = meter.npz(raw, hashlib.sha256(raw).hexdigest(), 'synthetic-base')
    mirrors = adapter.trial_and_mirrors(loaded, loaded, residual, old, meter)
    # Original pure column function, no rewritten arithmetic or monkeypatch.
    geometry = column._full_column(old)
    expected = {}
    for key, source in [('density_parent','density_g_cm3'),('temperature_parent','temperature_k'),
                        ('hydrogen_parent','hydrogen_fraction'),('helium_parent','helium_fraction')]:
        value = loaded[source]
        expected[key] = expected_facts['mirrors'][key]['sha256']
        if hashlib.sha256(mirrors[key].tobytes()).hexdigest() != expected[key]:
            raise ValueError('independent mirror mismatch')
    for key, value in loaded.items():
        fact = dict(dtype=value.dtype.str, shape=list(value.shape),
                    sha256=hashlib.sha256(value.tobytes()).hexdigest())
        if fact != expected_facts['arrays'][key]:
            raise ValueError('independent raw NPY decode mismatch')
    if not np.array_equal(geometry['edge_cm'],np.tile(np.arange(-128.,129.),(2,1))):
        raise ValueError('independent uniform column mismatch')
    failures = {}
    for key in ('encoded_state','temperature_k','density_g_cm3','step_duration_s'):
        bad = dict(loaded); bad[key] = loaded[key].copy(); bad[key].flat[0] += 1
        try: adapter.trial_and_mirrors(bad, loaded, residual, old, meter)
        except ValueError as error: failures[key] = str(error)
        else: raise AssertionError('corrupt trial accepted')
    for operation in ('stat','open','readlink'):
        try:
            if operation == 'open': open('synthetic-absent.dat','rb')
            else: getattr(os,operation)('synthetic-absent.dat')
        except OSError as error: failures['path:'+operation] = error.errno
        else: raise AssertionError('filesystem operation accepted')
    imported = adapter.origins(loader)
    facts = guard.check()
    print(json.dumps({'synthetic':True,'production_ready':False,'seal':seal,
        'startup_isolated_no_site':True,'environment_preload_project_free':True,
        'environment_origins':environment,'executed_project_origins':imported,
        'frozen_project_module_count':len(rows),'exact_trial_original_passed':True,
        'original_column_passed':True,'mirror_sha256':expected,'failures':failures,
        'npz_bytes':len(raw),'synthetic_npz_base64':base64.b64encode(raw).decode(),
        'independent_raw_fingerprints':expected_facts,
        'oracle_meter_scope':'separate old standard-library parser, not adapter meter',
        'meter':meter.facts(),'resources':facts,
        'whole_lifecycle_guard_verified':False,'complete_native_context_verified':False}))


if __name__ == '__main__':
    main()
