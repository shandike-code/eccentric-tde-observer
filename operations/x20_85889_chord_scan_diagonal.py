"""Slab-only matrix-diagonal sharing candidate; no I/O or production entry point.

缓存仅在一次调用内存活；不使用Gram重建直接小差，不改变原归约。
调用期间六个输入数组必须保持不变。本模块不写入调用者的数组。
"""
import numpy as np
from operations.x20_85889_chord_scan import (
    COEFFICIENTS, COMBINATIONS, LABELS, decimal_text, dot, rounding_mode,
)


from operations.x20_85889_chord_scan_square import reconstruction_square


def subtract_key(left, right):
    # 有序binary64表达式树，不能用代数相等或数组地址合并。
    return ('subtract_binary64', left, right)


class _SlabCache:
    def __init__(self, fields, check):
        self.fields = fields
        self.check = check
        self.binary64 = {}
        self.longdouble = {}
        self.products = {}
        self.errors = {}
        self.maxima = {}

    def raw(self, key):
        self.check()
        if isinstance(key, int):
            return self.fields[key]
        if key not in self.binary64:
            _, left, right = key
            with np.errstate(over='raise', invalid='raise', under='ignore'):
                value = self.raw(left) - self.raw(right)
            value.flags.writeable = False
            self.binary64[key] = value
        return self.binary64[key]

    def vector(self, key):
        self.check()
        if key not in self.longdouble:
            value = self.raw(key).astype(np.longdouble)
            value.flags.writeable = False
            self.longdouble[key] = value
        return self.longdouble[key]

    def gram(self, keys):
        n = len(keys)
        values = [[None] * n for _ in range(n)]
        absolute = [[None] * n for _ in range(n)]
        for i in range(n):
            for j in range(i, n):
                self.check()  # 命中缓存仍检查停止、墙钟及RSS。
                key = (keys[i], keys[j])
                if key not in self.products:
                    left = self.vector(keys[i])
                    right = self.vector(keys[j])
                    # 两次取数与停止检查保留；资格只认有序表达式键相同。
                    if keys[i] == keys[j]:
                        a = b = reconstruction_square(left)
                    else:
                        a, b = dot(left, right)
                    self.products[key] = (decimal_text(a), decimal_text(b))
                a, b = self.products[key]
                values[i][j] = values[j][i] = a
                absolute[i][j] = absolute[j][i] = b
        return dict(value=values, absolute=absolute)

    def linf(self, key):
        self.check()
        if key not in self.maxima:
            self.maxima[key] = decimal_text(abs(self.vector(key)).max())
        return self.maxima[key]

    def reconstruction(self, key, coefficients, basis_keys, bound):
        self.check()
        cache_key = (key, tuple(coefficients), tuple(basis_keys))
        if cache_key not in self.errors:
            v = self.vector(key)
            formed = np.zeros_like(v)
            for c, b in zip(coefficients, basis_keys):
                if c:
                    formed += c * self.vector(b)
            delta = v - formed
            if np.any(abs(delta) > bound):
                raise ArithmeticError('basis reconstruction inconsistent')
            linf = decimal_text(abs(delta).max())
            self.check()
            square = decimal_text(reconstruction_square(delta))
            self.errors[cache_key] = (square, linf)
        return self.errors[cache_key]


def slab_statistics(fields, check=lambda: None):
    """Return the original numeric schema, reusing only identical expressions."""
    rounding_mode()
    check()
    if len(fields) != 6 or not fields[0].size:
        raise ValueError('six nonempty fields required')
    if any(x.dtype != np.dtype('<f8') or x.shape != fields[0].shape or
           not np.isfinite(x).all() or np.any(x < 0) for x in fields):
        raise ValueError('wrong shape/dtype or nonphysical original intensity')
    cache = _SlabCache(fields, check)
    basis_keys = [subtract_key(i, j) for i, j in ((4, 1), (1, 0), (2, 1), (4, 3), (5, 4))]
    for key in basis_keys:
        cache.vector(key)
    out = dict(gram=cache.gram(basis_keys), count=int(fields[0].size),
               minima=[decimal_text(x.min()) for x in fields],
               maxima=[decimal_text(x.max()) for x in fields], pairs=[])
    # 与原代码完全相同的左至右源尺度形成；这里只移出不变bound。
    source_scale = sum(x.astype(np.longdouble) for x in fields)
    bound = (32*np.longdouble(np.finfo(np.float64).eps)*source_scale +
             8*np.longdouble(np.nextafter(0., 1.)))
    bound_max = decimal_text(bound.max())
    for index, (a, h) in enumerate(COMBINATIONS):
        check()
        d, ra, rh = subtract_key(h, a), subtract_key(a+1, a), subtract_key(h+1, h)
        e = subtract_key(rh, ra)  # 先binary64支内差，再binary64缺陷差。
        mapped = subtract_key(h+1, a+1)
        keys = (d, e, mapped, ra, rh)
        direct = [cache.vector(key) for key in keys]
        identity = direct[2] - (direct[0] + direct[1])
        if np.any(abs(identity) > bound):
            raise ArithmeticError('formation identity inconsistent')
        errors, error_linf = [], []
        for key, coefficients in zip(keys, COEFFICIENTS[index]):
            square, linf = cache.reconstruction(key, coefficients, basis_keys, bound)
            errors.append(square)
            error_linf.append(linf)
        out['pairs'].append(dict(label=LABELS[a]+'_'+LABELS[h],
            moments=cache.gram(keys), reconstruction_error_square=errors,
            reconstruction_error_linf=error_linf, linf=[cache.linf(key) for key in keys],
            identity_linf=decimal_text(abs(identity).max()), identity_bound_max=bound_max))
    check()
    return out
