"""Split Gauss affine array results; leggauss internals explicitly unmetered.

The return allowance covers two leggauss output arrays only. Python/scalar
objects and NumPy/LAPACK private workspaces are not bounded by this ledger.
"""
import numpy as np


def split_weights(order, split_mu, ledger, check):
    if type(order) is not int or order < 2 or order > 32 or order % 2:
        raise ValueError('even angular order in 2..32 required')
    split = float(split_mu)
    if not np.isfinite(split) or not -1 < split < 1:
        raise ValueError('finite interior split required')
    n = order // 2
    def reserve(label, size):
        check()
        ledger.reserve('quadrature:' + label, size)
    reserve('leggauss-return-capacity', 2*n*8)
    node, base_weight = np.polynomial.legendre.leggauss(n)
    check()
    # 保留原仿射表达式树；每个显式数组结果在创建前预约。
    reserve('left-product', n*8); left = (split+1.0)*node
    reserve('left-add', n*8); left = left+split
    reserve('left-subtract', n*8); left = left-1.0
    reserve('left-mu', n*8); left_mu = 0.5*left
    reserve('left-weight', n*8); left_weight = 0.5*(split+1.0)*base_weight
    reserve('right-product', n*8); right = (1.0-split)*node
    reserve('right-add', n*8); right = right+split
    reserve('right-add-one', n*8); right = right+1.0
    reserve('right-mu', n*8); right_mu = 0.5*right
    reserve('right-weight', n*8); right_weight = 0.5*(1.0-split)*base_weight
    reserve('mu-concatenate', order*8); mu = np.concatenate((left_mu,right_mu))
    reserve('weight-concatenate', order*8); weight = np.concatenate((left_weight,right_weight))
    # 原 _readonly 只改 flags，不复制；这里也没有返回复制。
    mu.setflags(write=False); weight.setflags(write=False)
    check()
    return mu, weight
