"""Convert a finite archived legacy residual at an identified material state.

This is an algebraic diagnostic, not a fresh radiation evaluation. A caller must
verify the encoded state, legacy residual, physical old state, and codec identity.
"""
from __future__ import annotations

import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def recover_equation_residual(
    codec: GroundStateLogSimplexCodec,
    encoded_base: np.ndarray,
    legacy_residual: np.ndarray,
    old_gas_heat_erg_g: np.ndarray,
) -> np.ndarray:
    """Recover the new four-component residual, within codec round-off.

    Legacy residual = encoded target - encoded base. The target must be a
    physically decodable state. No conversion exists here for failed/null legacy
    responses; callers must not supply synthetic zeros in their place.
    """
    base = np.asarray(encoded_base, dtype=np.float64)
    legacy = np.asarray(legacy_residual, dtype=np.float64)
    scale = np.asarray(old_gas_heat_erg_g, dtype=np.float64)
    if (base.shape != (codec.vector_size,) or legacy.shape != base.shape
            or scale.shape != (codec.cell_count,)
            or not all(np.all(np.isfinite(a)) for a in (base, legacy, scale))
            or np.any(scale <= 0)):
        raise ValueError('invalid baseline vector or fixed old-gas scale')
    candidate = codec.decode(base)
    response = codec.decode(base + legacy)
    # 目标总能量已经编码在旧响应中；不另外假设Q或修改物理dt。
    result = -legacy.reshape(codec.cell_count, 4).copy()
    result[:, 0] = (
        candidate.specific_material_energy_erg_g
        - response.specific_material_energy_erg_g
    ) / scale
    if not np.all(np.isfinite(result)):
        raise ArithmeticError('recovered equation residual is nonfinite')
    return result
