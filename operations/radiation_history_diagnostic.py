"""Fixed-matter history diagnostics; observed differences are not error bounds."""
from dataclasses import asdict
import numpy as np
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms


def identical_material(a, b):
    """Require every field, including native inputs and archived metadata, to match."""
    if set(a) != set(b):
        raise ValueError('material field inventory differs')
    for key in a:
        x, y = np.asarray(a[key]), np.asarray(b[key])
        if x.dtype != y.dtype or x.shape != y.shape or not np.array_equal(x, y):
            raise ValueError('material differs: '+key)
        if np.issubdtype(x.dtype, np.number) and not np.isfinite(x).all():
            raise ValueError('nonfinite material: '+key)


def require_ownership(blocks, groups=9632, count=76):
    if sorted(b['block_index'] for b in blocks) != list(range(count)):
        raise ValueError('frequency block inventory mismatch')
    owner = np.zeros(groups, dtype=int)
    for b in blocks:
        start, stop = b['core_group_start'], b['core_group_stop']
        if not 0 <= start < stop <= groups:
            raise ValueError('invalid frequency core')
        owner[start:stop] += 1
    if not np.all(owner == 1):
        raise ValueError('frequency ownership overlap or gap')


def difference_metrics(a, b, mass):
    """Vector difference norms and squared contributions, not differences of norms."""
    x, y = np.asarray(a).reshape(-1, 4), np.asarray(b).reshape(-1, 4)
    if x.shape != y.shape:
        raise ValueError('residual shapes differ')
    delta = x-y
    norms = asdict(encoded_residual_norms(delta, mass))
    m = np.asarray(mass)
    weighted = delta**2 * (m/m.sum())[:, None]
    # 中文：编码分量是对数气体热能与电离布居比；其平方贡献不是物理能量份额。
    return {'norms': norms, 'component_squared_l2': (delta**2).sum(axis=0).tolist(),
            'component_squared_mass_norm': weighted.sum(axis=0).tolist(),
            'cell_squared_l2': (delta**2).sum(axis=1).tolist(),
            'cell_squared_mass_norm': weighted.sum(axis=1).tolist(),
            'delta': delta.tolist(), 'strict_error_bound': False}
