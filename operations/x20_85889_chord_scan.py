"""Bounded six-field streaming statistics; no production launch entry point.

所有场只读；此模块不调用转移核、反馈核或旧collect_scan。
"""
from contextlib import ExitStack
import ctypes
import hashlib
import math
import os
from pathlib import Path
import resource
import sys
import time
import numpy as np

LABELS = ("AP", "AF", "AM", "HP", "HF", "HM")
COMBINATIONS = ((0, 3), (0, 4), (1, 3), (1, 4))
COEFFICIENTS = (
 ((1,1,0,-1,0),(0,-1,0,1,0),(1,0,0,0,0),(0,1,0,0,0),(0,0,0,1,0)),
 ((1,1,0,0,0),(0,-1,0,0,1),(1,0,0,0,1),(0,1,0,0,0),(0,0,0,0,1)),
 ((1,0,0,-1,0),(0,0,-1,1,0),(1,0,-1,0,0),(0,0,1,0,0),(0,0,0,1,0)),
 ((1,0,0,0,0),(0,0,-1,0,1),(1,0,-1,0,1),(0,0,1,0,0),(0,0,0,0,1)),
)


def rounding_mode():
    # 本实现限定已测试的Darwin/Linux C环境；两平台FE_TONEAREST代码均为0。
    if sys.platform not in ('darwin','linux'):
        raise RuntimeError('untested floating-point environment')
    code=int(ctypes.CDLL(None).fegetround())
    if code!=0:raise ArithmeticError('round-to-nearest required')
    return code


def decimal_text(x):
    if not np.isfinite(x):
        raise ValueError("nonfinite statistic")
    return np.format_float_scientific(np.longdouble(x), unique=False, precision=36)


def dot(x, y):
    # 先提升再乘；极小非零乘积不能静默成为零。Mac的longdouble可能仅binary64。
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        product = x * y
    if np.any((x != 0) & (y != 0) & (product == 0)):
        raise ArithmeticError("nonzero product underflow; platform range insufficient")
    return np.sum(product, dtype=np.longdouble), np.sum(abs(product), dtype=np.longdouble)


def gram(vectors, check=lambda:None):
    n = len(vectors)
    values = [[None] * n for _ in range(n)]
    absolute = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            check()
            a, b = dot(vectors[i], vectors[j])
            values[i][j] = values[j][i] = decimal_text(a)
            absolute[i][j] = absolute[j][i] = decimal_text(b)
    return dict(value=values, absolute=absolute)


def slab_statistics(fields, check=lambda:None):
    if len(fields) != 6 or not fields[0].size:
        raise ValueError("six nonempty fields required")
    if any(x.dtype != np.dtype("<f8") or x.shape != fields[0].shape or
           not np.isfinite(x).all() or np.any(x < 0) for x in fields):
        raise ValueError("wrong shape/dtype or nonphysical original intensity")
    ap, af, am, hp, hf, hm = fields
    # 协议固定binary64做差，再提升longdouble；禁止重结合以改变极小值。
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        basis = [x.astype(np.longdouble) for x in
                 (hf-af, af-ap, am-af, hf-hp, hm-hf)]
    out = dict(gram=gram(basis,check), count=int(ap.size),
               minima=[decimal_text(x.min()) for x in fields],
               maxima=[decimal_text(x.max()) for x in fields], pairs=[])
    source_scale = sum(x.astype(np.longdouble) for x in fields)
    for index, (a, h) in enumerate(COMBINATIONS):
        with np.errstate(over="raise", invalid="raise", under="ignore"):
            d = fields[h] - fields[a]
            ra = fields[a+1] - fields[a]
            rh = fields[h+1] - fields[h]
            e = rh - ra
            mapped = fields[h+1] - fields[a+1]
        direct = [v.astype(np.longdouble) for v in (d,e,mapped,ra,rh)]
        identity = direct[2] - (direct[0] + direct[1])
        # 这是数值一致性门，分母是六源强度尺度，不是相对微小差或严格误差界。
        bound = (32*np.longdouble(np.finfo(np.float64).eps)*source_scale +
                 8*np.longdouble(np.nextafter(0.,1.)))
        if np.any(abs(identity) > bound):
            raise ArithmeticError("formation identity inconsistent")
        errors = [];error_linf=[]
        for v, coefficients in zip(direct, COEFFICIENTS[index]):
            formed = np.zeros_like(v)
            for c, b in zip(coefficients, basis):
                if c:
                    formed += c*b
            delta = v-formed
            if np.any(abs(delta)>bound):
                raise ArithmeticError('basis reconstruction inconsistent')
            error_linf.append(decimal_text(abs(delta).max()))
            errors.append(decimal_text(dot(delta,delta)[0]))
        out['pairs'].append(dict(label=LABELS[a]+"_"+LABELS[h],
            moments=gram(direct,check), reconstruction_error_square=errors,
            reconstruction_error_linf=error_linf,
            linf=[decimal_text(abs(v).max()) for v in direct],
            identity_linf=decimal_text(abs(identity).max()),
            identity_bound_max=decimal_text(bound.max())))
    return out


def peak_rss_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)


class Guard:
    def __init__(self, seconds=3300, rss_bytes=6*1024**3, stop=lambda:False,
                 clock=time.monotonic, rss=peak_rss_bytes):
        self.clock,self.rss,self.stop=clock,rss,stop
        self.started=clock();self.seconds=seconds;self.rss_bytes=rss_bytes
    def check(self):
        if self.stop():
            raise InterruptedError('stop requested')
        if self.clock()-self.started >= self.seconds:
            raise TimeoutError('wall budget exhausted')
        if self.rss() >= self.rss_bytes:
            raise MemoryError('RSS budget exhausted')


def signature(s):
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def checked_stat(claim):
    p=Path(claim['path'])
    if p.is_symlink() or not p.is_file():
        raise ValueError('regular nonlink source required')
    s=p.stat()
    if s.st_size != claim['size_bytes']:
        raise ValueError('field size mismatch')
    return signature(s)


def hash_pass(claims, initial, guard):
    result=[]
    for c, old in zip(claims,initial):
        guard.check()
        if checked_stat(c)!=old:
            raise ValueError('field changed before hash')
        sha=hashlib.sha256()
        with Path(c['path']).open('rb') as f:
            if signature(os.fstat(f.fileno()))!=old:
                raise ValueError('opened different source')
            remaining=c['size_bytes']
            while remaining:
                guard.check();raw=f.read(min(8*1024**2,remaining))
                if not raw:raise ValueError('short hash read')
                sha.update(raw);remaining-=len(raw)
            if f.read(1):raise ValueError('trailing hash data')
            if signature(os.fstat(f.fileno()))!=old:
                raise ValueError('field changed in hash')
        if checked_stat(c)!=old or sha.hexdigest()!=c['sha256']:
            raise ValueError('field stat/SHA mismatch')
        result.append(sha.hexdigest())
    return result


def scan(claims, shape, progress, guard=None):
    """一次统计扫描加前后hash；progress接收每片，用于保存未完成状态。"""
    mode=rounding_mode()
    guard=Guard() if guard is None else guard
    if len(claims)!=6 or len(shape)!=3 or any(type(x)!=int or x<=0 for x in shape):
        raise ValueError('invalid inputs')
    if len({str(Path(c['path']).resolve()) for c in claims})!=6:
        raise ValueError('duplicate source paths')
    size=math.prod(shape)*8
    if any(c['size_bytes']!=size for c in claims):
        raise ValueError('shape/size mismatch')
    initial=[checked_stat(c) for c in claims]
    before=hash_pass(claims,initial,guard)
    rows=[];hashes=[hashlib.sha256() for _ in claims]
    with ExitStack() as stack:
        files=[stack.enter_context(Path(c['path']).open('rb')) for c in claims]
        if [signature(os.fstat(f.fileno())) for f in files]!=initial:
            raise ValueError('source replaced before statistics')
        for start in range(0,shape[0],32):
            guard.check();n=min(32,shape[0]-start);nbytes=n*math.prod(shape[1:])*8;fields=[]
            for f,sha in zip(files,hashes):
                raw=f.read(nbytes)
                if len(raw)!=nbytes:raise ValueError('short field read')
                sha.update(raw);fields.append(np.frombuffer(raw,dtype='<f8').reshape(n,*shape[1:]))
            row=slab_statistics(fields,guard.check)
            row.update(first_group=start,group_count=n,block=start//128)
            guard.check();progress(row);rows.append(row)
        if any(f.read(1) for f in files):raise ValueError('trailing field data')
        if [signature(os.fstat(f.fileno())) for f in files]!=initial:
            raise ValueError('field changed during statistics')
    if [h.hexdigest() for h in hashes]!=before:
        raise ValueError('statistics SHA mismatch')
    after=hash_pass(claims,initial,guard);guard.check()
    return dict(status='statistics_complete_requires_independent_review',shape=list(shape),
        labels=list(LABELS),source_claims=claims,source_stats_before=initial,
        source_stats_after=[checked_stat(c) for c in claims],hashes_before=before,
        hashes_scan=[h.hexdigest() for h in hashes],hashes_after=after,
        field_bytes_read=3*6*size,slabs=rows,
        arithmetic=dict(rounding_mode_code=mode,rounding_mode='FE_TONEAREST',subtractions='binary64 fixed expression order',accumulation='numpy longdouble',
          nmant=np.finfo(np.longdouble).nmant,eps=decimal_text(np.finfo(np.longdouble).eps),
          maxexp=np.finfo(np.longdouble).maxexp,serialization_significant_digits=37,
          numpy=np.__version__),peak_rss_bytes=peak_rss_bytes(),new_maps=0,new_feedback=0,new_material=0,
        strict_error_bound=False)
