"""Environment-only DSYEVD workspace query; never performs an eigensolve.

This reports caller workspace, not backend-private allocation or an RSS bound.
Run only in the externally pinned NumPy environments, in a bounded child.
"""
import ctypes as c
import hashlib
import json
import math
import platform
from pathlib import Path


def probe():
    import numpy as np
    import numpy.linalg._umath_linalg as native
    from numpy.version import git_revision

    if np.__version__ != '2.5.2' or git_revision != '48fecee5453aa1d31e6b79dcb3969dc1a6d1a891':
        raise RuntimeError('unreviewed NumPy source revision')
    system = platform.system()
    if (system, platform.machine()) == ('Darwin', 'arm64'):
        symbol = 'dsyevd$NEWLAPACK$ILP64'
    elif (system, platform.machine()) == ('Linux', 'x86_64'):
        symbol = 'scipy_dsyevd_64_'
    else:
        raise RuntimeError('unreviewed platform/ABI')
    # 两端已从实际动态符号核实 ILP64，不能以 Python 默认整数推断 ABI。
    integer = c.c_int64
    double = c.c_double
    handle = c.CDLL(native.__file__)
    function = getattr(handle, symbol)
    function.argtypes = [c.POINTER(c.c_char), c.POINTER(c.c_char),
                        c.POINTER(integer), c.POINTER(double), c.POINTER(integer),
                        c.POINTER(double), c.POINTER(double), c.POINTER(integer),
                        c.POINTER(integer), c.POINTER(integer), c.POINTER(integer)]
    function.restype = None
    class DlInfo(c.Structure):
        _fields_ = [('fname', c.c_char_p), ('base', c.c_void_p),
                    ('sname', c.c_char_p), ('saddr', c.c_void_p)]
    dladdr = c.CDLL(None).dladdr
    dladdr.argtypes = [c.c_void_p, c.POINTER(DlInfo)]
    dladdr.restype = c.c_int
    identity = DlInfo()
    if dladdr(c.cast(function, c.c_void_p), c.byref(identity)) == 0:
        raise RuntimeError('unresolved backend')
    rows = []
    for degree in range(1, 17):
        n, lda = integer(degree), integer(degree)
        a, w = (double * (degree * degree))(), (double * degree)()
        before = bytes(a), bytes(w)
        work, iwork = double(), integer()
        lwork, liwork, info = integer(-1), integer(-1), integer(-999)
        jobz, uplo = c.c_char(b'N'), c.c_char(b'L')
        # -1/-1 只查询；不分配推荐工作区，不执行特征值求解。
        function(c.byref(jobz), c.byref(uplo), c.byref(n), a, c.byref(lda), w,
                 c.byref(work), c.byref(lwork), c.byref(iwork),
                 c.byref(liwork), c.byref(info))
        if info.value != 0 or before != (bytes(a), bytes(w)):
            raise RuntimeError('workspace query changed input or failed')
        if not math.isfinite(work.value) or not work.value.is_integer():
            raise RuntimeError('invalid workspace query')
        if not 1 <= work.value <= 1048576 or not 1 <= iwork.value <= 1048576:
            raise RuntimeError('query outside fixed audit range')
        lw, liw = int(work.value), iwork.value
        rows.append(dict(degree=degree, lwork=lw, liwork=liw, info=info.value,
                         matrix_and_internal_values_bytes=8*degree*(degree+1),
                         caller_workspace_bytes=8*(lw+liw), input_unchanged=True))
    def pin(path):
        raw = Path(path).read_bytes()
        return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    result = dict(schema='86304-native-workspace-query-v1', platform=system,
                  machine=platform.machine(), numpy_version=np.__version__,
                  numpy_revision=git_revision, native=pin(native.__file__),
                  symbol=symbol, resolved_library=identity.fname.decode(),
                  fortran_integer_bytes=c.sizeof(integer), rows=rows,
                  eigensolves=0, backend_private_workspace_bounded=False,
                  production_metering_integrated=False, rss_bound_verified=False)
    if system == 'Linux':
        result['backend_binary'] = pin(identity.fname.decode())
    return result


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
