"""86304 preparation: irreversible filesystem seal for a disposable worker.

This module is not a production launcher. Environment imports and source-byte
acquisition must finish before seal(); project execution follows it. No Python
filesystem function is replaced. Real source preparation remains unauthorized.
"""
import ctypes
import errno
import importlib.abc
import importlib.util
import hashlib
import math
import os
import platform
import resource
import signal
import sys
import time


class FrozenModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Execute externally authenticated module bytes without filesystem imports."""

    def __init__(self, entries):
        self.entries = {}
        self.executed = []
        for name, row in entries.items():
            source, digest, filename, package = row
            if (not isinstance(name, str) or not name or
                    type(source) is not bytes or type(package) is not bool or
                    not isinstance(filename, str) or not filename.startswith('/') or
                    hashlib.sha256(source).hexdigest() != digest):
                raise ValueError('invalid frozen module')
            if name in sys.modules:
                raise ValueError('project module already imported: ' + name)
            self.entries[name] = (compile(source, filename, 'exec'), filename, package)

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.entries:
            # Never fall back to PathFinder after the seal.
            raise ModuleNotFoundError('module absent from frozen memory: ' + fullname)
        code, filename, package = self.entries[fullname]
        return importlib.util.spec_from_loader(fullname, self, origin=filename,
                                               is_package=package)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        code, filename, package = self.entries[module.__name__]
        module.__file__ = filename
        if package:
            module.__path__ = []
        exec(code, module.__dict__)
        self.executed.append(module.__name__)

    def install(self):
        sys.meta_path.insert(0, self)


def peak_rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == 'darwin' else value * 1024)


class StopGuard:
    """Sticky acceptance gates; external parent must enforce the hard deadline.

    ru_maxrss detects historical peaks at checkpoints, not an instantaneous
    kernel RSS allocation cap. A signal or exceeded gate cannot become success.
    """
    def __init__(self, started, seconds=120.0, rss_bytes=1024**3):
        if (type(started) not in (int, float) or not math.isfinite(started) or
                type(seconds) not in (int, float) or not 0 < seconds <= 120 or
                type(rss_bytes) is not int or not 0 < rss_bytes <= 1024**3):
            raise ValueError('invalid resource limit')
        self.started, self.seconds, self.rss_bytes = started, seconds, rss_bytes
        self.reason = None

    def stop(self, signum, frame):
        self.reason = 'signal:' + str(signum)
        raise RuntimeError(self.reason)

    def install(self):
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1, signal.SIGALRM):
            signal.signal(signum, self.stop)
        signal.setitimer(signal.ITIMER_REAL, max(1e-6, self.seconds -
                                               (time.monotonic() - self.started)))
        self.check()

    def check(self):
        if self.reason is None and time.monotonic() - self.started >= self.seconds:
            self.reason = 'wall limit'
        if self.reason is None and peak_rss_bytes() >= self.rss_bytes:
            self.reason = 'RSS limit'
        if self.reason is not None:
            raise RuntimeError(self.reason)
        return {'elapsed_s': time.monotonic() - self.started,
                'peak_rss_bytes': peak_rss_bytes()}


def _linux_seal(libc):
    # 正向白名单：所有未列出的 syscall（包括新的路径接口）在内核执行前拒绝。
    # 仅支持现场验证的 x86_64 ABI；拒绝 x32、其他架构及 fork/clone/exec。
    if platform.machine() != 'x86_64':
        raise RuntimeError('unverified Linux ABI')
    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                    ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint32)]
    class Program(ctypes.Structure):
        _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(Filter))]
    # write/close, anonymous memory, signals, time, identity, resource observations.
    allowed = (1, 3, 9, 10, 11, 12, 13, 14, 15, 24, 25, 28, 35, 39,
               60, 96, 98, 102, 104, 107, 108, 131, 158, 186, 202, 204,
               218, 219, 228, 229, 230, 231, 234, 273, 302, 318, 334)
    # prlimit64 (302) can inspect/change own limits, but cannot create an FD.
    rows = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xc000003e),
            (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    for number in allowed:
        rows.extend([(0x15, 0, 1, number), (0x06, 0, 0, 0x7fff0000)])
    rows.append((0x06, 0, 0, 0x00050000 | errno.EPERM))
    filters = (Filter * len(rows))(*(Filter(*row) for row in rows))
    program = Program(len(rows), filters)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'no_new_privs failed')
    # TSYNC applies to all existing threads; any nonzero return fails closed.
    result = libc.syscall(317, 1, 1, ctypes.byref(program))
    if result != 0:
        raise OSError(ctypes.get_errno(), 'seccomp TSYNC failed: ' + str(result))
    return 'linux-seccomp-tsync-allowlist-v1'


def _darwin_seal(libc):
    initialize = libc.sandbox_init
    initialize.argtypes = [ctypes.c_char_p, ctypes.c_uint64,
                           ctypes.POINTER(ctypes.c_char_p)]
    initialize.restype = ctypes.c_int
    error = ctypes.c_char_p()
    profile = b'''(version 1)(allow default)
(deny file-read*)(deny file-write*)(deny process-fork)(deny process-exec)
(deny network*)(deny mach-lookup)(deny file-map-executable)'''
    if initialize(profile, 0, ctypes.byref(error)) != 0:
        raise RuntimeError('sandbox_init failed: ' + repr(error.value))
    return 'darwin-seatbelt-deny-files-v1'


def seal():
    """Close inherited data descriptors, then deny filesystem use irreversibly.

    Must run in a fresh disposable child with stdout/stderr pipes. No existing
    mappings or environment reads are retrospectively protected by this seal.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    # These streams must not be inherited regular scientific files or sockets.
    import stat
    for fd in (1, 2):
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):
            raise RuntimeError('stdout/stderr must be pipes')
    fd_directory = '/proc/self/fd' if sys.platform == 'linux' else '/dev/fd'
    descriptors = [int(name) for name in os.listdir(fd_directory)]
    for fd in descriptors:
        if fd >= 3:
            try:
                os.close(fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise
    os.close(0)
    if sys.platform == 'linux':
        return _linux_seal(libc)
    if sys.platform == 'darwin':
        return _darwin_seal(libc)
    raise RuntimeError('unsupported operating system')


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: authenticated environment/native adapter not integrated')
