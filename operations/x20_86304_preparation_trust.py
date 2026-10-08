"""Explicit-array trust and control identity; no production configuration entry.

Named ndarray payload reservations exclude Python objects, NumPy reductions and
private workspace. Scalar equality results are charged one byte explicitly.
Reservations are cumulative expression capacities, not allocator/live/RSS bounds.
"""
import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from eccentric_tde_observer.source import PhysicalDomainError
from operations.x20_86304_preparation_codec import decode


def within_trust_region(codec, current_encoded_state, trial_encoded_state, ledger, check, *,
                        maximum_relative_temperature_change,
                        maximum_absolute_material_energy_increment_fraction,
                        maximum_population_fraction_change):
    """Keep both decodes and the original three dimensionless trust limits."""
    if not isinstance(codec, GroundStateLogSimplexCodec):
        raise TypeError('material trust region requires a GroundStateLogSimplexCodec')
    temperature_limit = float(maximum_relative_temperature_change)
    energy_limit = float(maximum_absolute_material_energy_increment_fraction)
    population_limit = float(maximum_population_fraction_change)
    if (not all(np.isfinite(v) for v in (temperature_limit, energy_limit, population_limit))
            or not 0. < temperature_limit < 1. or not 0. < energy_limit < 1.
            or not 0. < population_limit < 1.):
        raise PhysicalDomainError('material trust-region limits are invalid')
    current = decode(codec, current_encoded_state, ledger, check)
    trial = decode(codec, trial_encoded_state, ledger, check)
    n = codec.cell_count
    def r(label, count, operation):
        check(); ledger.reserve('trust:'+label, count*8); return operation()
    # T 为 K，比能为 erg/g；各除以 current 后无量纲，保持原相减/abs/除法树。
    delta = r('temperature-delta', n, lambda: trial.temperature_k-current.temperature_k)
    absolute = r('temperature-absolute', n, lambda: np.abs(delta))
    relative = r('temperature-relative', n, lambda: absolute/current.temperature_k)
    temperature_change = float(np.max(relative))
    delta = r('energy-delta', n, lambda: trial.specific_material_energy_erg_g-current.specific_material_energy_erg_g)
    absolute = r('energy-absolute', n, lambda: np.abs(delta))
    relative = r('energy-relative', n, lambda: absolute/current.specific_material_energy_erg_g)
    energy_change = float(np.max(relative))
    delta = r('hydrogen-delta', 2*n, lambda: trial.hydrogen_fraction-current.hydrogen_fraction)
    absolute = r('hydrogen-absolute', 2*n, lambda: np.abs(delta))
    hydrogen_change = float(np.max(absolute))
    delta = r('helium-delta', 3*n, lambda: trial.helium_fraction-current.helium_fraction)
    absolute = r('helium-absolute', 3*n, lambda: np.abs(delta))
    population_change = max(hydrogen_change, float(np.max(absolute)))
    check()
    return bool(temperature_change <= temperature_limit and energy_change <= energy_limit
                and population_change <= population_limit)


def exact_control_trial(trial, base, residual, old, ledger, check):
    """Narrow original exact_trial(control) to fixed numeric ndarray layouts."""
    n = len(trial['temperature_k'])
    if not 1 <= n <= 128: raise ValueError('bounded cell count required')
    shapes = {'encoded_state':(4*n,), 'base_encoded_state':(4*n,),
              'base_residual':(4*n,), 'finite_direction':(4*n,),
              'density_g_cm3':(n,), 'temperature_k':(n,), 'hydrogen_fraction':(n,2),
              'helium_fraction':(n,3), 'specific_material_energy_erg_g':(n,),
              'relaxation':(), 'step_duration_s':(), 'phase_index':()}
    for record in (trial,base):
        for key, shape in shapes.items():
            a = record[key]
            dtype = np.dtype('int64') if key=='phase_index' else np.dtype('float64')
            if type(a) is not np.ndarray or a.dtype!=dtype or a.shape!=shape:
                raise ValueError('bounded identity layout: '+key)
    if type(residual) is not np.ndarray or residual.dtype!=np.dtype('float64') or residual.shape!=(4*n,):
        raise ValueError('bounded residual layout')
    rho, dt = old['density_g_cm3'], old['step_duration_s']
    if (type(rho) is not np.ndarray or rho.dtype!=np.dtype('float64') or rho.ndim!=2
            or rho.shape[1]!=n or not 1<=rho.shape[0]<=4096
            or type(dt) is not np.ndarray or dt.dtype!=np.dtype('float64') or dt.shape!=(rho.shape[0],)):
        raise ValueError('bounded old layout')
    phase = int(trial['phase_index'])
    if not 0<=phase<rho.shape[0]: raise ValueError('bounded phase')
    def r(label, count, operation, width=8):
        check(); ledger.reserve('identity:'+label, count*width); return operation()
    def equal(label, a, b):
        # exact ndarray/shape 已前置；原 equal_nan=False 比较保留数值相等语义（含 +/-0）。
        mask = r(label, a.size, lambda: a==b, 1)
        return bool(np.asanyarray(mask).all())
    if not np.all(r('residual-finite', 4*n, lambda: np.isfinite(residual), 1)):
        raise ValueError('invalid encoded residual')
    direction = r('direction-copy', 4*n, lambda: np.array(residual,copy=True)).reshape(-1,4).reshape(-1)
    alpha = 0.
    if float(trial['relaxation'])!=alpha: raise ValueError('undeclared amplitude')
    if float(base['relaxation'])!=0 or not equal('base-encoded',base['encoded_state'],base['base_encoded_state']):
        raise ValueError('not zero base')
    if not equal('base-residual',base['base_residual'],residual) or not equal('base-direction',base['finite_direction'],residual):
        raise ValueError('base denominator changed')
    # 原列表构造先算零乘法和加法，再开始四项比较；不能因 control 相同省略。
    scaled = r('scaled-direction',4*n,lambda: alpha*direction)
    encoded = r('encoded-sum',4*n,lambda: base['encoded_state']+scaled)
    for key, value in [('base_encoded_state',base['encoded_state']),('base_residual',residual),
                       ('finite_direction',direction),('encoded_state',encoded)]:
        if not equal('trial-'+key,trial[key],value):raise ValueError('trial identity changed: '+key)
    for key in ('density_g_cm3','phase_index','step_duration_s'):
        if not equal('physical-'+key,trial[key],base[key]):raise ValueError('physical identity changed: '+key)
    if not equal('old-density',trial['density_g_cm3'],rho[phase]) or float(trial['step_duration_s'])!=float(dt[phase]):
        raise ValueError('physical old layer changed')
    codec = GroundStateLogSimplexCodec(n)
    decoded = decode(codec, trial['encoded_state'], ledger, check)
    for key in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        if not equal('decoded-'+key,trial[key],getattr(decoded,key)):raise ValueError('native decode changed: '+key)
    if not within_trust_region(codec,base['encoded_state'],trial['encoded_state'],ledger,check,
            maximum_relative_temperature_change=.5,
            maximum_absolute_material_energy_increment_fraction=.25,
            maximum_population_fraction_change=.05):raise ValueError('trust region failed')
    check()


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: independent trust/control component; configuration incomplete')
