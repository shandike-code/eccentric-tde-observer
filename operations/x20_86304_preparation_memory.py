"""Authenticated in-memory native components; no real-source/production entry.

Project modules execute only after the caller seals its disposable process.
Environment preload and interpreter startup are a separate trusted boundary.
"""
import hashlib
import importlib
import io
from pathlib import PurePosixPath
import sys
import zipfile

from operations.x20_86304_preparation_boundary import FrozenModules
from operations.x20_86304_preparation_inputs import Budget, MeteredBytes, npy_header


def frozen_project(rows, root):
    """Bind every source and legacy alias to externally frozen bytes and origin."""
    if type(root) is not str or not root.startswith('/') or '..' in root.split('/'):
        raise ValueError('absolute lexical root required')
    entries = {}
    for name, row in rows.items():
        path = row['path']
        if (type(path) is not str or not path or path.startswith('/') or
                any(x in ('', '.', '..') for x in path.split('/')) or
                '\\' in path or not path.endswith('.py')):
            raise ValueError('source path')
        raw = row['source'].encode('utf-8')
        if len(raw) != row['size_bytes'] or type(row['size_bytes']) is not int:
            raise ValueError('source size')
        if type(row['namespace']) is not bool:
            raise ValueError('namespace flag')
        if row['namespace']:
            if raw != b'' or row['package'] is not True:
                raise ValueError('namespace must be empty')
        entries[name] = (raw, row['sha256'], root + '/' + path, row['package'])
    return FrozenModules(entries)


def origins(loader):
    """Check actual executed modules without reopening source paths after seal."""
    facts = {}
    for name in loader.executed:
        module = sys.modules[name]
        code, filename, package = loader.entries[name]
        spec = module.__spec__
        if (module.__file__ != filename or spec.origin != filename or
                spec.loader is not loader or module.__loader__ is not loader or
                code.co_filename != filename or
                (package and module.__path__ != [])):
            raise ValueError('frozen module origin changed: ' + name)
        facts[name] = {'file': filename, 'spec_origin': spec.origin}
    # A project entry cannot silently appear through another importer.
    for name in loader.entries:
        if name in sys.modules and name not in facts:
            raise ValueError('project module bypassed loader: ' + name)
    return facts


class ArrayLoader:
    """ZIP returned bytes, decompressed member bytes and explicit copies separately.

    Reservations bound this adapter's explicit materializations, not Python/zlib
    allocator overhead or all temporaries inside original scientific functions.
    Each source is opened once by this loader; scientific arrays remain read-only.
    """
    def __init__(self, read_limit=256*1024**2, stage_limit=512*1024**2):
        if (type(read_limit) is not int or not 0 < read_limit <= 256*1024**2 or
                type(stage_limit) is not int or not 0 < stage_limit <= 512*1024**2):
            raise ValueError('fixed maximum budgets')
        self.read = Budget(read_limit)
        self.decompressed = Budget(stage_limit)
        self.reservations = Budget(stage_limit)
        self.events = []
        self.loaded = set()

    def npz(self, raw, expected_sha, label):
        import numpy as np
        if (type(raw) is not bytes or not 0 < len(raw) < 32*1024**2 or
                hashlib.sha256(raw).hexdigest() != expected_sha):
            raise ValueError('authenticated NPZ bytes required')
        if label in self.loaded:
            raise ValueError('duplicate load')
        self.loaded.add(label)
        stream = MeteredBytes(raw, self.read, self.events, label)
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            if not 0 < len(infos) <= 128:
                raise ValueError('member count')
            names = [x.filename for x in infos]
            if len(set(names)) != len(names):
                raise ValueError('duplicate members')
            total = 0
            for entry in infos:
                name = entry.filename
                if (PurePosixPath(name).name != name or not name.endswith('.npy') or
                        name == '.npy' or '\\' in name or entry.flag_bits & 1 or
                        entry.compress_type not in (0, 8) or
                        ((entry.external_attr >> 16) & 0o170000) not in (0, 0o100000)):
                    raise ValueError('unsafe ZIP member')
                total += entry.file_size
            if total >= 128*1024**2:
                raise ValueError('source decompression limit')
            # Reserve before reading: bytearray + immutable bytes, plus bounded
            # ZIP return chunk. This is deliberately cumulative, never released.
            self.reservations.charge(2*total + 65536)
            members = {}
            for entry in infos:
                buffer = bytearray()
                with archive.open(entry) as member:
                    while True:
                        chunk = member.read(min(65536, entry.file_size-len(buffer)+1))
                        self.decompressed.charge(len(chunk))
                        if not chunk:
                            break
                        buffer.extend(chunk)
                        if len(buffer) > entry.file_size:
                            raise ValueError('member overflow')
                if len(buffer) != entry.file_size:
                    raise ValueError('truncated member')
                value = bytes(buffer)
                header_stream = io.BytesIO(value)
                header = npy_header(header_stream, len(value))
                if header['fortran_order']:
                    raise ValueError('Fortran order not admitted')
                members[entry.filename[:-4]] = (value, header)
            arrays = {}
            for name, (value, header) in members.items():
                array = np.frombuffer(value, dtype=header['dtype'],
                                      offset=header['offset']).reshape(header['shape'])
                self.reservations.charge(array.size)
                if array.dtype.kind in 'fc' and not np.all(np.isfinite(array)):
                    raise ValueError('nonfinite array')
                if array.dtype.kind == 'b' and any(v not in (0, 1) for v in memoryview(value)[header['offset']:]):
                    raise ValueError('noncanonical boolean')
                arrays[name] = array
            return arrays

    def copy(self, array):
        import numpy as np
        self.reservations.charge(array.nbytes)
        return np.array(array, copy=True)

    def mirror(self, array):
        import numpy as np
        self.reservations.charge(2*array.nbytes)
        return np.concatenate((array, array[::-1]), axis=0)

    def facts(self):
        return {'compressed_interface_returned_bytes': self.read.used,
                'decompressed_member_returned_bytes': self.decompressed.used,
                'explicit_materialization_reserved_bytes': self.reservations.used,
                'device_io_measured': False,
                'all_native_temporaries_bounded': False}


def trial_and_mirrors(trial, base, residual, old, meter):
    """Invoke the original exact_trial, then preserve original copy/mirror order."""
    original = importlib.import_module('operations.common_step21_directions')
    original.exact_trial(trial, base, residual, old, 'control')
    density_half = meter.copy(trial['density_g_cm3'])
    temperature_half = meter.copy(trial['temperature_k'])
    hydrogen_half = meter.copy(trial['hydrogen_fraction'])
    helium_half = meter.copy(trial['helium_fraction'])
    return {'density_parent': meter.mirror(density_half),
            'temperature_parent': meter.mirror(temperature_half),
            'hydrogen_parent': meter.mirror(hydrogen_half),
            'helium_parent': meter.mirror(helium_half)}


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: complete native context and lifecycle acceptance pending')
