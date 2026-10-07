"""Bounded-header memory configuration composition, with no native worker call.

External claims still need an independently accepted scientific source manifest.
This component does not acquire files or authorize production.
"""
import hashlib
import json
import math
from pathlib import PurePosixPath
import numpy as np

from operations.x20_86304_preparation_inputs import claim
from operations.x20_86304_preparation_memory import trial_and_mirrors
from operations.x20_86304_preparation_context import context_from_arrays, validate_arrays

from operations.x20_86304_preparation_headers import HeaderArrayLoader, header_from_bytes

ROLES = ('fixed', 'template', 'trial', 'base', 'residual', 'old', 'master')


def _json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result: raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def number(value):
        value = float(value)
        if not math.isfinite(value): raise ValueError('nonfinite JSON')
        return value
    def constant(value): raise ValueError('nonfinite JSON')
    result = json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=constant)
    if type(result) is not dict: raise ValueError('JSON object required')
    return result


def _bind(declared, authenticated):
    # 旧模板允许只声明 path/SHA；有大小时也必须匹配，不改原科学来源。
    if (type(declared) is not dict or
            any(declared.get(k) != authenticated[k] for k in ('path','sha256')) or
            ('size_bytes' in declared and (type(declared['size_bytes']) is not int or
                                         declared['size_bytes'] != authenticated['size_bytes']))):
        raise ValueError('source role binding')


def _warm(row):
    if type(row) is not dict or set(row) != {'path','size_bytes','sha256'}:
        raise ValueError('warm claim')
    name = row['path']
    if (type(name) is not str or not name or '\\' in name or '\0' in name or
            PurePosixPath(name).is_absolute() or
            any(x in ('','.','..') for x in name.split('/')) or
            PurePosixPath(name).suffix != '.dat' or
            type(row['size_bytes']) is not int or row['size_bytes'] <= 0 or
            type(row['sha256']) is not str or len(row['sha256']) != 64 or
            any(c not in '0123456789abcdef' for c in row['sha256'])):
        raise ValueError('lexical warm claim')
    return dict(row)


def configure_from_bytes(blobs, claims, warm_seed, expected, check):
    """Return fixed/template/context/material without path resolution or patching."""
    if set(blobs) != set(ROLES) or set(claims) != set(ROLES):
        raise ValueError('complete memory roles required')
    if (type(expected) is not dict or set(expected) != {'phase','duration_s','shape'} or
            type(expected['phase']) is not int or expected['phase'] < 0 or
            type(expected['duration_s']) not in (float,int) or
            not math.isfinite(expected['duration_s']) or expected['duration_s'] <= 0 or
            type(expected['shape']) is not list or len(expected['shape']) != 3 or
            any(type(n) is not int or n <= 0 for n in expected['shape'])):
        raise ValueError('external geometry expectation')
    suffixes = dict(fixed='.json',template='.json',trial='.npz',base='.npz',
                    residual='.npy',old='.npz',master='.npz')
    paths = set(); authenticated_bytes = 0
    for role in ROLES:
        check(); row = claims[role]; raw = blobs[role]
        path = claim(row)
        if (path.suffix != suffixes[role] or str(path) in paths or
                type(raw) is not bytes or len(raw) != row['size_bytes'] or
                hashlib.sha256(raw).hexdigest() != row['sha256'] or
                (role != 'old' and len(raw) >= 1024**2)):
            raise ValueError('authenticated role bytes: ' + role)
        paths.add(str(path)); authenticated_bytes += len(raw)
    warm = _warm(warm_seed)
    shape = expected['shape']
    if warm['size_bytes'] != math.prod(shape)*8: raise ValueError('warm shape size')
    fixed = _json(blobs['fixed']); template = _json(blobs['template'])
    _bind(fixed['sources']['phase7b7i_template_protocol'], claims['template'])
    _bind(template['sources']['phase7b4r_material'], claims['old'])
    _bind(template['sources']['phase7b5p_master_input'], claims['master'])
    keys = ('physical_frequency_groups','angular_direction_count','radiation_depth_cell_count')
    for document in (fixed,template):
        cfg = document['configuration']
        if any(type(cfg[k]) is not int or cfg[k] != n for k,n in zip(keys,shape)):
            raise ValueError('configuration shape')
    if type(template['configuration']['phase_index']) is not int or template['configuration']['phase_index'] != expected['phase']:
        raise ValueError('template phase')
    # 与旧 _template_protocol 同序赋值；warm 路径只词法核验，不访问大场元数据。
    fixed['sources']['current_material_state'] = dict(claims['trial'])
    template['sources']['initial_radiation_state']['path'] = warm['path']
    template['sources']['second_material_iterate'] = dict(fixed['sources']['current_material_state'])
    meter = HeaderArrayLoader(check)
    loaded = {}
    for role in ('trial','base','old','master'):
        check(); loaded[role] = meter.npz(blobs[role],claims[role]['sha256'],role)
    raw = blobs['residual']
    header = header_from_bytes(raw, meter.ledger, check)
    if header['dtype'] != '<f8' or header['shape'] != [512] or header['fortran_order']:
        raise ValueError('residual layout')
    residual = meter.array(raw, header)
    validate_arrays(loaded['old'], loaded['master'])
    trial = loaded['trial']; base = loaded['base']
    meter.ledger.reserve('trial-base-comparison-bytes',
                         sum(a.nbytes for a in trial.values()) +
                         sum(a.nbytes for a in base.values()))
    if set(trial) != set(base) or any(trial[k].dtype != base[k].dtype or
            trial[k].shape != base[k].shape or trial[k].tobytes() != base[k].tobytes() for k in trial):
        raise ValueError('all trial/base arrays must match control')
    phase = trial['phase_index']
    if phase.shape != () or phase.dtype.kind not in 'iu' or int(phase) != expected['phase'] or not 0 <= int(phase) < loaded['old']['density_g_cm3'].shape[0]:
        raise ValueError('trial phase')
    dt = trial['step_duration_s']
    if dt.shape != () or dt.dtype != np.dtype('float64') or float(dt) != expected['duration_s']:
        raise ValueError('trial duration')
    check()
    material = trial_and_mirrors(trial,base,residual,loaded['old'],meter)
    context = context_from_arrays(loaded['old'],loaded['master'],check)
    actual_shape = [context['stencil'].physical_group_count,len(context['mu']),len(context['beta'])]
    if (actual_shape != shape or context['phase'] != expected['phase'] or
            context['duration_s'] != expected['duration_s']):
        raise ValueError('native geometry versus external expectation')
    next_group = 0
    for block in context['blocks']:
        if block.core_group_start != next_group or block.core_group_stop != min(next_group+128,shape[0]):
            raise ValueError('frequency ownership')
        next_group = block.core_group_stop
    if next_group != shape[0]: raise ValueError('frequency coverage')
    check()
    return dict(fixed=fixed,template=template,context=context,material=material,
                warm_seed=warm,meter=meter.facts(),authenticated_input_bytes=authenticated_bytes,
                residual_view_bytes=residual.nbytes,production_authorized=False)


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: lifecycle, complete metering and production acceptance pending')
