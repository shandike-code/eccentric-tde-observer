"""Bounded explicit-array decode; original codec and preparation remain unchanged.

Reservations cover named ndarray payloads, not Python objects, scalar reductions,
ufunc/indexing private workspace, allocator totals, live memory or RSS. Imports
are outside this boundary. No production or exact_trial wiring is provided here.
"""
import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec, GroundStateMaterialState,
)
from eccentric_tde_observer.atmosphere import PROTON_MASS_G
from eccentric_tde_observer.radiation import BOLTZMANN_ERG_K
from eccentric_tde_observer.non_gray import (
    HYDROGEN_IONIZATION_ERG, HELIUM_I_IONIZATION_ERG, HELIUM_II_IONIZATION_ERG,
)
from eccentric_tde_observer.source import PhysicalDomainError


def decode(codec, encoded_state, ledger, check):
    """Preserve decode/energy expression order for exact f64 ndarrays, 1..128 cells."""
    if type(codec) is not GroundStateLogSimplexCodec or type(codec.cell_count) is not int or not 1 <= codec.cell_count <= 128:
        raise ValueError('bounded original codec required')
    n = codec.cell_count
    if type(encoded_state) is not np.ndarray or encoded_state.dtype != np.dtype('float64') or encoded_state.shape != (4*n,):
        raise ValueError('exact f64 encoded layout required')
    # 限定 ndarray/f64 后原 asarray 无复制；reshape 仍可为步进视图。
    vector = encoded_state
    def r(label, count, operation, itemsize=8):
        check()
        ledger.reserve('codec:' + label, int(count)*itemsize)
        return operation()
    def finite(label, a):
        return np.all(r(label + ':finite', a.size, lambda: np.isfinite(a), 1))
    def nonpositive(label, a):
        return np.any(r(label + ':nonpositive', a.size, lambda: a <= 0., 1))
    def readonly(a):
        check(); a.setflags(write=False); return a
    if not finite('vector', vector):
        raise PhysicalDomainError('encoded material vector is invalid')
    values = vector.reshape(n, 4)
    thermal = r('thermal', n, lambda: np.exp(values[:, 0]))
    ionized = r('ionized-empty', n, lambda: np.empty(n, dtype=np.float64))
    positive = r('positive', n, lambda: values[:, 1] >= 0., 1)
    check(); p = int(np.count_nonzero(positive)); q = n-p
    selected = r('positive-select', p, lambda: values[positive, 1])
    negative = r('positive-negate', p, lambda: -selected)
    exp_negative = r('positive-exp', p, lambda: np.exp(negative))
    denominator = r('positive-denominator', p, lambda: 1. + exp_negative)
    fraction = r('positive-fraction', p, lambda: 1. / denominator)
    check(); ionized[positive] = fraction
    inverse = r('negative-select-mask', n, lambda: ~positive, 1)
    selected = r('negative-select', q, lambda: values[inverse, 1])
    exp_positive = r('negative-exp', q, lambda: np.exp(selected))
    denominator = r('negative-denominator', q, lambda: 1. + exp_positive)
    fraction = r('negative-fraction', q, lambda: exp_positive / denominator)
    # 原赋值重新计算 ~positive；不复用前一个 mask 改变预约表。
    inverse = r('negative-write-mask', n, lambda: ~positive, 1)
    check(); ionized[inverse] = fraction
    neutral = r('neutral', n, lambda: 1. - ionized)
    hydrogen = r('hydrogen', 2*n, lambda: np.column_stack((neutral, ionized)))
    zeros = r('helium-zero', n, lambda: np.zeros(n, dtype=np.float64))
    score = r('helium-score', 3*n, lambda: np.column_stack((zeros, values[:, 2], values[:, 3])))
    shift = r('helium-shift', n, lambda: np.max(score, axis=1))
    shifted = r('helium-shifted', 3*n, lambda: score-shift[:, None])
    weight = r('helium-weight', 3*n, lambda: np.exp(shifted))
    sums = r('helium-sum', n, lambda: np.sum(weight, axis=1))
    helium = r('helium', 3*n, lambda: weight/sums[:, None])
    if (not finite('thermal', thermal) or nonpositive('thermal', thermal)
            or not finite('hydrogen', hydrogen) or not finite('helium', helium)
            or nonpositive('hydrogen', hydrogen) or nonpositive('helium', helium)):
        raise PhysicalDomainError('decoded material state reached the domain boundary')
    hp = codec.composition.hydrogen_mass_fraction / PROTON_MASS_G
    hep = codec.composition.helium_mass_fraction / (4.0*PROTON_MASS_G)
    nuclei = hp + hep
    def electrons(prefix):
        h = r(prefix+':hydrogen-electron', n, lambda: hp*hydrogen[:, 1])
        twice = r(prefix+':helium-double', n, lambda: 2.0*helium[:, 2])
        he = r(prefix+':helium-charge', n, lambda: helium[:, 1]+twice)
        he = r(prefix+':helium-electron', n, lambda: hep*he)
        return r(prefix+':electron', n, lambda: h+he)
    electron = electrons('coefficient')
    particles = r('coefficient:particles', n, lambda: nuclei+electron)
    coefficient = r('coefficient:value', n, lambda: 1.5*BOLTZMANN_ERG_K*particles)
    temperature = r('temperature', n, lambda: thermal/coefficient)
    # energy 原 _population_arrays 门：非负和单纯形误差，不能用 decode 门替代。
    tolerance = 128.0*np.finfo(np.float64).eps
    if not finite('energy-hydrogen', hydrogen) or not finite('energy-helium', helium):
        raise PhysicalDomainError('H/He populations must lie in their simplices')
    for label, a in (('energy-hydrogen', hydrogen), ('energy-helium', helium)):
        if np.any(r(label+':negative', a.size, lambda: a < 0., 1)):
            raise PhysicalDomainError('H/He populations must lie in their simplices')
    for label, a in (('energy-hydrogen', hydrogen), ('energy-helium', helium)):
        s = r(label+':sum', n, lambda: np.sum(a, axis=1))
        d = r(label+':sum-minus-one', n, lambda: s-1.)
        absolute = r(label+':sum-absolute', n, lambda: np.abs(d))
        if np.any(r(label+':sum-outside', n, lambda: absolute > tolerance, 1)):
            raise PhysicalDomainError('H/He populations must lie in their simplices')
    if not finite('energy-temperature', temperature) or nonpositive('energy-temperature', temperature):
        raise PhysicalDomainError('temperature must be finite, positive and cellwise')
    electron = electrons('energy')
    # 气体热能 erg/g：保留 (1.5*k*T)*(nuclei+electron)，不改为 coefficient*T。
    scaled = r('gas-scaled-temperature', n, lambda: 1.5*BOLTZMANN_ERG_K*temperature)
    particles = r('gas-particles', n, lambda: nuclei+electron)
    gas = r('gas', n, lambda: scaled*particles)
    h = r('ionization-h-number', n, lambda: hp*hydrogen[:, 1])
    h = r('ionization-h', n, lambda: h*HYDROGEN_IONIZATION_ERG)
    he1 = r('ionization-he1', n, lambda: helium[:, 1]*HELIUM_I_IONIZATION_ERG)
    he2 = r('ionization-he2', n, lambda: helium[:, 2]*(HELIUM_I_IONIZATION_ERG+HELIUM_II_IONIZATION_ERG))
    he = r('ionization-he-sum', n, lambda: he1+he2)
    he = r('ionization-he', n, lambda: hep*he)
    ionization = r('ionization', n, lambda: h+he)
    total = r('total', n, lambda: gas+ionization)
    if not finite('total', total) or nonpositive('total', total):
        raise ArithmeticError('ground-state material specific energy became invalid')
    energy = readonly(r('energy-copy', n, lambda: np.array(total, copy=True)))
    if not finite('temperature', temperature) or nonpositive('temperature', temperature):
        raise ArithmeticError('decoded material temperature became invalid')
    return GroundStateMaterialState(
        temperature_k=readonly(r('temperature-copy', n, lambda: np.array(temperature, copy=True))),
        hydrogen_fraction=readonly(r('hydrogen-copy', 2*n, lambda: np.array(hydrogen, copy=True))),
        helium_fraction=readonly(r('helium-copy', 3*n, lambda: np.array(helium, copy=True))),
        specific_material_energy_erg_g=readonly(r('decoded-energy-copy', n, lambda: np.array(energy, copy=True))),
    )


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: isolated decode, exact_trial and preparation incomplete')
