"""Bounded input capabilities for source preparation; no production/native entry.

The explicit reader rejects dat names before any metadata call. This is NOT a
process-wide guard: direct os.stat or foreign loaders bypass this capability.
Consequently native_configuration always refuses, even after component tests.
"""
import ast
import hashlib
import io
import math
import os
from pathlib import PurePosixPath
import re
import stat
import struct
import zipfile

SOURCE_LIMIT = 128 * 1024**2
STAGE_LIMIT = 512 * 1024**2
READ_LIMIT = 256 * 1024**2
OLD = (17159976, '33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455')


def relative(name):
    """纯词法检查；拒绝前不调用 resolve/stat/readlink。"""
    if type(name) is not str or not name or '\\' in name or '\x00' in name:
        raise ValueError('lexical path')
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ValueError('relative canonical path')
    if any(x.lower().endswith('.dat') for x in p.parts):
        raise ValueError('dat metadata/read forbidden')
    return p


def claim(row):
    p = relative(row['path'])
    n, sha = row['size_bytes'], row['sha256']
    if type(n) is not int or not 0 <= n <= 32 * 1024**2:
        raise ValueError('source size')
    if type(sha) is not str or re.fullmatch('[0-9a-f]{64}', sha) is None:
        raise ValueError('source SHA')
    if p.suffix not in ('.json', '.npy', '.npz', '.py'):
        raise ValueError('source suffix')
    if p.suffix == '.npz' and n >= 1024**2 and (n, sha) != OLD:
        raise ValueError('compressed NPZ limit')
    return p


class Budget:
    def __init__(self, limit):
        if type(limit) is not int or limit <= 0:
            raise ValueError('positive integer limit')
        self.limit, self.used = limit, 0

    def charge(self, n):
        if type(n) is not int or n < 0 or self.used + n >= self.limit:
            raise ValueError('strict byte limit')
        self.used += n


class MeteredBytes(io.RawIOBase):
    """Read/seek interface over authenticated bytes, with no fileno/getbuffer bypass.

    Returned bytes count repeated ZIP reads; it is not filesystem/device I/O.
    The budget is checked before returning bytes to the caller.
    """
    def __init__(self, raw, budget, events, path):
        super().__init__()
        if type(raw) is not bytes:
            raise TypeError('immutable bytes required')
        self.__raw, self.__position = raw, 0
        self.__budget, self.__events, self.__path = budget, events, path

    def readable(self): return True
    def seekable(self): return True
    def tell(self):
        self._checkClosed()
        return self.__position

    def seek(self, offset, whence=0):
        self._checkClosed()
        if type(offset) is not int or type(whence) is not int or whence not in (0, 1, 2):
            raise ValueError('seek')
        n = (0, self.__position, len(self.__raw))[whence] + offset
        if n < 0: raise ValueError('negative seek')
        self.__position = n
        return n

    def read(self, size=-1):
        self._checkClosed()
        if type(size) is not int: raise TypeError('read size')
        remaining = max(0, len(self.__raw) - self.__position)
        n = remaining if size < 0 else min(size, remaining)
        self.__budget.charge(n)
        data = self.__raw[self.__position:self.__position+n]
        self.__position += n
        self.__events.append(dict(path=self.__path, returned_bytes=n))
        return data

    def readinto(self, buffer):
        target = memoryview(buffer).cast('B')
        if target.readonly: raise TypeError('readonly buffer')
        data = self.read(len(target)); target[:len(data)] = data
        return len(data)


def signature(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def authenticated_read(root_fd, row, budget):
    """All traversal uses directory descriptors and O_NOFOLLOW, never dat metadata.

    The caller owns a trusted directory descriptor. Reading is capability-scoped,
    not a replacement for the missing process-wide guard.
    """
    parts = claim(row).parts  # 必须在任何系统调用之前拒绝 dat。
    directory = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory); directory = nxt
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size != row['size_bytes']:
                raise ValueError('ordinary source size')
            chunks = []; left = row['size_bytes'] + 1
            while left:
                # 预留尾探测字节；拒绝预算不足，不能先读后补计量。
                requested = min(left, 65536)
                if budget.used + requested >= budget.limit:
                    raise ValueError('authentication read budget')
                data = os.read(fd, requested); budget.charge(len(data))
                if not data: break
                chunks.append(data); left -= len(data)
            after = os.fstat(fd)
            current = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            if signature(before) != signature(after) or signature(before) != signature(current):
                raise ValueError('source changed')
        finally:
            os.close(fd)
    finally:
        os.close(directory)
    raw = b''.join(chunks)
    if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('source bytes')
    return raw


def npy_header(stream, member_size):
    """Restrictive NPY header preflight before any NumPy allocation.

    Plain numeric/string scalar dtypes only; structured/object/subarray unsupported.
    No physical-domain inference is made from these header checks.
    """
    if stream.read(6) != b'\x93NUMPY': raise ValueError('NPY magic')
    version = stream.read(2)
    if version not in (b'\x01\x00', b'\x02\x00', b'\x03\x00'): raise ValueError('NPY version')
    width = 2 if version == b'\x01\x00' else 4
    length_raw = stream.read(width)
    if len(length_raw) != width: raise ValueError('NPY header length')
    length = int.from_bytes(length_raw, 'little')
    if not 0 < length <= 16384: raise ValueError('NPY header cap')
    raw = stream.read(length)
    if len(raw) != length or not raw.endswith(b'\n'): raise ValueError('NPY header truncated')
    tree = ast.parse(raw.decode('utf-8' if version == b'\x03\x00' else 'latin1').strip(), mode='eval')
    if not isinstance(tree.body, ast.Dict): raise ValueError('NPY dictionary')
    keys = [ast.literal_eval(k) for k in tree.body.keys]
    if len(keys) != 3 or set(keys) != {'descr', 'fortran_order', 'shape'}: raise ValueError('NPY keys')
    h = ast.literal_eval(tree)
    if type(h['fortran_order']) is not bool or type(h['shape']) is not tuple or len(h['shape']) > 8:
        raise ValueError('NPY layout')
    shape = h['shape']
    if any(type(n) is not int or n < 0 or n >= SOURCE_LIMIT for n in shape): raise ValueError('NPY shape')
    d = h['descr']
    if type(d) is not str or re.fullmatch(r'[<>=|][biufcSU][1-9][0-9]{0,5}', d) is None:
        raise ValueError('NPY dtype')
    kind, itemsize = d[1], int(d[2:])
    if kind in 'b' and itemsize != 1: raise ValueError('bool dtype')
    if kind in 'iu' and itemsize not in (1, 2, 4, 8): raise ValueError('integer dtype')
    if kind == 'f' and itemsize not in (4, 8): raise ValueError('float dtype')
    if kind == 'c' and itemsize not in (8, 16): raise ValueError('complex dtype')
    if kind == 'U': itemsize *= 4
    nbytes = math.prod(shape) * itemsize
    offset = 8 + width + length
    if nbytes >= SOURCE_LIMIT or member_size != offset + nbytes: raise ValueError('NPY payload size')
    return dict(dtype=d, shape=list(shape), fortran_order=h['fortran_order'], payload_bytes=nbytes, offset=offset)


def inspect_npz(raw, decoded_budget, read_budget=None):
    """Scan all headers before decoding any array; no extraction or filesystem path.

    Logical decoded-byte reservation includes every member, including metadata.
    ZIP CRC of payload is checked later by a full bounded decode, not by this scan.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= 32*1024**2: raise ValueError('bounded NPZ bytes')
    events = []; reader = MeteredBytes(raw, read_budget or Budget(READ_LIMIT), events, '<npz>')
    rows = {}; total = 0
    with zipfile.ZipFile(reader) as archive:
        members = archive.infolist()
        if not 0 < len(members) <= 128: raise ValueError('NPZ member count')
        for info in members:
            name = info.filename
            if '/' in name or '\\' in name or not name.endswith('.npy') or name[:-4] in rows or not name[:-4]:
                raise ValueError('NPZ member name')
            if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError('NPZ encoding')
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG): raise ValueError('NPZ member type')
            if not 0 < info.file_size < SOURCE_LIMIT or not 0 <= info.compress_size <= len(raw):
                raise ValueError('NPZ member size')
            with archive.open(info) as member:
                row = npy_header(member, info.file_size)
            total += row['payload_bytes']
            if total >= SOURCE_LIMIT: raise ValueError('NPZ decoded source cap')
            rows[name[:-4]] = row
    decoded_budget.charge(total)
    return dict(arrays=rows, reserved_decoded_bytes=total, read_events=events,
                payload_crc_verified=False, scope='header-only-not-native')


def staging_plan(files, locations):
    """Validate every logical-to-school mapping without probing any actual source."""
    names = [x['path'] for x in files]
    if not names or len(names) != len(set(names)) or set(names) != set(locations):
        raise ValueError('complete unique staging map')
    result = []
    for row in files:
        claim(row); origin = locations[row['path']]; claim(origin)
        if (row['size_bytes'], row['sha256']) != (origin['size_bytes'], origin['sha256']):
            raise ValueError('staging source identity')
        result.append(dict(destination=dict(row), source=dict(origin)))
    return result


def stage_small_sources(source_fd, output_parent_fd, name, plan, budget):
    """Exclusive destination with descriptor-relative traversal; partials are kept."""
    if len(relative(name).parts) != 1: raise ValueError('exclusive stage name')
    # 在创建目标之前核完整映射，失败不会留下看似完整的来源清单。
    checked = staging_plan([x['destination'] for x in plan],
                           {x['destination']['path']: x['source'] for x in plan})
    os.mkdir(name, mode=0o700, dir_fd=output_parent_fd)
    root = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=output_parent_fd)
    written = []
    try:
        for item in checked:
            raw = authenticated_read(source_fd, item['source'], budget)
            parts = relative(item['destination']['path']).parts
            directory = os.dup(root)
            try:
                for part in parts[:-1]:
                    try: os.mkdir(part, mode=0o700, dir_fd=directory)
                    except FileExistsError: pass
                    nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                    os.close(directory); directory = nxt
                fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
                try:
                    view = memoryview(raw)
                    while view:
                        n = os.write(fd, view)
                        if n <= 0: raise OSError('short staging write')
                        view = view[n:]
                    os.fsync(fd)
                finally: os.close(fd)
            finally: os.close(directory)
            # 独立重读落盘字节；其返回字节也进入认证读取计量。
            authenticated_read(root, item['destination'], budget)
            written.append(dict(item['destination']))
        os.fsync(root)
    finally: os.close(root)
    return dict(files=written, authentication_returned_bytes=budget.used,
                actual_source_manifest_prepared=False, process_guard_verified=False)


def fingerprints(raw, decoded_budget, read_budget):
    """Standard-library fingerprints, independent of NumPy/live.native_facts.

    C-order plain NPY only in this first interface. Unsupported formats fail;
    native decode/energy consistency remains a separate, currently closed gate.
    """
    headers = inspect_npz(raw, decoded_budget, read_budget)['arrays']
    output, payloads, events = {}, {}, []
    with zipfile.ZipFile(MeteredBytes(raw, read_budget, events, '<npz-full>')) as archive:
        for key, row in headers.items():
            if row['fortran_order']: raise ValueError('C-order fingerprint required')
            with archive.open(key+'.npy') as stream:
                data = stream.read(row['offset']+row['payload_bytes']+1)
            if len(data) != row['offset']+row['payload_bytes']: raise ValueError('NPY full length')
            payload = data[row['offset']:]
            dtype = row['dtype']; kind = dtype[1]
            if kind in 'fc':
                width = int(dtype[2:]) // (2 if kind == 'c' else 1)
                endian = dtype[0] if dtype[0] in '<>' else '='
                code = 'f' if width == 4 else 'd'
                if any(not math.isfinite(x[0]) for x in struct.iter_unpack(endian+code, payload)):
                    raise ValueError('nonfinite physical array')
            if kind == 'b' and any(x not in (0, 1) for x in payload): raise ValueError('noncanonical bool')
            output[key] = dict(dtype=dtype, shape=row['shape'], sha256=hashlib.sha256(payload).hexdigest())
            payloads[key] = payload
    return output, payloads


def expected_fingerprints(base_raw, trial_raw, decoded_budget, read_budget):
    """Mirror bytes directly, not by importing or calling the live implementation."""
    base, _ = fingerprints(base_raw, decoded_budget, read_budget)
    trial, payloads = fingerprints(trial_raw, decoded_budget, read_budget)
    if base != trial: raise ValueError('full trial/base array identity')
    required = {'encoded_state', 'base_encoded_state', 'finite_direction', 'base_residual', 'relaxation',
                'density_g_cm3', 'temperature_k', 'hydrogen_fraction', 'helium_fraction',
                'specific_material_energy_erg_g'}
    if not required <= trial.keys(): raise ValueError('full trial arrays missing')
    mirrors = {}
    for field, parent in [('density_g_cm3', 'density_parent'), ('temperature_k', 'temperature_parent'),
                          ('hydrogen_fraction', 'hydrogen_parent'), ('helium_fraction', 'helium_parent')]:
        row = trial[field]; shape = row['shape']
        if not shape or shape[0] <= 0: raise ValueError('mirror row shape')
        payload = payloads[field]; width = len(payload)//shape[0]
        decoded_budget.charge(2*len(payload))
        # 按第一轴整行镜像；分量轴字节顺序保持，不能反转每个标量的字节。
        mirrored = payload + b''.join(payload[i*width:(i+1)*width] for i in range(shape[0]-1, -1, -1))
        mirrors[parent] = dict(dtype=row['dtype'], shape=[2*shape[0], *shape[1:]],
                               sha256=hashlib.sha256(mirrored).hexdigest())
    mirrors['specific_material_energy_erg_g'] = trial['specific_material_energy_erg_g']
    return dict(schema='86304-independent-array-fingerprints-component-v1', arrays=trial, mirrors=mirrors,
                decoded_reserved_bytes=decoded_budget.used, loader_returned_bytes=read_budget.used,
                exact_trial_decode_verified=False, physical_old_r20_verified=False,
                process_guard_verified=False, live_native_recomputed=False)


def native_configuration(*args, **kwargs):
    """No token, boolean or synthetic evidence can enable the unfinished native path."""
    raise RuntimeError('DO NOT RUN: process-wide import/metadata guard and native adapter unimplemented')
