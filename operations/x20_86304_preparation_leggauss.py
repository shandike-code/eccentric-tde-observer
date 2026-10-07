"""Bounded Legendre component, NumPy 2.5.2 expression order.

Explicit ndarray result capacities only. No allocator, live-memory, RSS,
Python-object or LAPACK/private-workspace bound. Not connected to production.
"""
import numpy as np


def nodes_weights(degree, ledger, check):
    """Return original-order nodes/weights for a true Python int in 1..16."""
    if type(degree) is not int or not 1 <= degree <= 16:
        raise ValueError('degree must be a Python int in 1..16')
    if np.dtype(int).itemsize != 8:
        raise RuntimeError('requires 64-bit default integer')

    def result(label, count, operation):
        check()
        ledger.reserve('leggauss:' + label, count * 8)
        return operation()

    n = degree
    c = result('coefficients-int', n + 1, lambda: np.array([0] * n + [1]))
    # 固定最高阶系数为一；as_series 的 trim 不切片，common_type 为 double。
    cc = result('companion-series-copy', n + 1,
                lambda: np.array(c, copy=True, dtype=np.double))
    if n == 1:
        mat = result('companion-one', 1, lambda: np.array([[-cc[0] / cc[1]]]))
    else:
        mat = result('companion-zero', n * n, lambda: np.zeros((n, n), dtype=cc.dtype))
        a = result('scale-arange', n, lambda: np.arange(n))
        a = result('scale-times-two', n, lambda: 2 * a)
        a = result('scale-plus-one', n, lambda: a + 1)
        a = result('scale-sqrt', n, lambda: np.sqrt(a))
        scl = result('scale-inverse', n, lambda: 1. / a)
        top = mat.reshape(-1)[1::n + 1]
        bot = mat.reshape(-1)[n::n + 1]
        a = result('offdiag-arange', n - 1, lambda: np.arange(1, n))
        a = result('offdiag-left', n - 1, lambda: a * scl[:n - 1])
        a = result('offdiag-right', n - 1, lambda: a * scl[1:n])
        check(); top[...] = a
        check(); bot[...] = top
        a = result('last-coeff-ratio', n, lambda: cc[:-1] / cc[-1])
        b = result('last-scale-ratio', n, lambda: scl / scl[-1])
        a = result('last-product', n, lambda: a * b)
        a = result('last-factor', n, lambda: a * (n / (2 * n - 1)))
        check(); mat[:, -1] -= a
    # 仅预约返回数组；eigvalsh gufunc、矩阵副本和 LAPACK 工作区仍未计量。
    x = result('eigvalsh-return', n, lambda: np.linalg.eigvalsh(mat))
    check()

    def value(x, coefficients, prefix):
        cv = coefficients
        if cv.dtype.char in '?bBhHiIlLqQpP':
            cv = result(prefix + '-astype', len(cv), lambda: cv.astype(np.double))
        cv = cv.reshape(cv.shape + (1,) * x.ndim)
        if len(cv) == 1:
            c0, c1 = cv[0], 0
        elif len(cv) == 2:
            c0, c1 = cv[0], cv[1]
        else:
            nd = len(cv)
            c0, c1 = cv[-2], cv[-1]
            for i in range(3, len(cv) + 1):
                check()
                tmp = c0
                nd = nd - 1
                tag = prefix + '-step-' + str(i)
                a = result(tag + '-left-product', c1.size, lambda: c1 * ((nd - 1) / nd))
                c0 = result(tag + '-left-subtract', a.size, lambda: cv[-i] - a)
                a = result(tag + '-right-product', n, lambda: c1 * x)
                a = result(tag + '-right-scale', n, lambda: a * ((2 * nd - 1) / nd))
                c1 = result(tag + '-right-add', n, lambda: tmp + a)
        a = result(prefix + '-final-product', n, lambda: c1 * x)
        return result(prefix + '-final-add', n, lambda: c0 + a)

    dy = value(x, c, 'dy')
    dc = result('derivative-copy-int', n + 1, lambda: np.array(c, ndmin=1, copy=True))
    dc = result('derivative-astype', n + 1, lambda: dc.astype(np.double))
    check(); dc *= 1
    der = result('derivative-empty', n, lambda: np.empty((n,), dtype=dc.dtype))
    for j in range(n, 2, -1):
        check(); der[j - 1] = (2 * j - 1) * dc[j]
        check(); dc[j - 2] += dc[j]
    if n > 1:
        check(); der[1] = 3 * dc[2]
    check(); der[0] = dc[1]
    df = value(x, der, 'df')
    delta = result('newton-ratio', n, lambda: dy / df)
    check(); x -= delta
    fm = value(x, c[1:], 'fm')
    a = result('fm-abs', n, lambda: np.abs(fm))
    check(); fm /= a.max()
    a = result('df-abs', n, lambda: np.abs(df))
    check(); df /= a.max()
    a = result('weight-product', n, lambda: fm * df)
    w = result('weight-inverse', n, lambda: 1 / a)
    a = result('weight-sym-add', n, lambda: w + w[::-1])
    w = result('weight-sym-divide', n, lambda: a / 2)
    a = result('node-sym-subtract', n, lambda: x - x[::-1])
    x = result('node-sym-divide', n, lambda: a / 2)
    # 原 leggauss 权重规范化，非新增物理修补；原树与原 inplace 顺序保留。
    check(); w *= 2. / w.sum()
    check()
    return x, w
