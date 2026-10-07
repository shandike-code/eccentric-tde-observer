"""Small NPY grammar over immutable bytes; no BytesIO or AST materialization.

Explicit payload reservations do not measure Python object/native allocator costs.
The scientific functions and production entry are deliberately not invoked here.
"""
import hashlib
import math
from operations.x20_86304_preparation_inflate import (
    PayloadLedger, STAGE_LIMIT, members, decode_member,
)

HEADER_LIMIT = 16384
SOURCE_LIMIT = 128 * 1024**2


class HeaderCursor:
    def __init__(self, raw, start, stop, ledger, check):
        self.raw = raw
        self.pos, self.stop = start, stop
        self.ledger, self.check = ledger, check
        self.tokens = 0

    def whitespace(self):
        while self.pos < self.stop and self.raw[self.pos] in (32, 9, 10, 13):
            if self.pos % 64 == 0:
                self.check()
            self.pos += 1

    def take(self, token):
        self.check()
        self.whitespace()
        self.tokens += 1
        if self.tokens > 64:
            raise ValueError('header token count')
        if self.pos >= self.stop or self.raw[self.pos] != token:
            raise ValueError('header punctuation')
        self.pos += 1

    def peek(self):
        self.whitespace()
        return self.raw[self.pos] if self.pos < self.stop else None

    def string(self):
        quote = self.peek()
        if quote not in (34, 39):
            raise ValueError('quoted header token')
        self.take(quote)
        start = self.pos
        while self.pos < self.stop and self.raw[self.pos] != quote:
            if self.pos - start >= 16 or not 32 <= self.raw[self.pos] < 127 or self.raw[self.pos] == 92:
                raise ValueError('short ASCII token required')
            self.pos += 1
        if self.pos >= self.stop:
            raise ValueError('unterminated token')
        size = self.pos - start
        # Slice bytes and ASCII character payload; object headers are not counted.
        self.ledger.reserve('header-token-bytes-and-characters', 2 * size)
        value = self.raw[start:self.pos].decode('ascii')
        self.take(quote)
        return value

    def boolean(self):
        first = self.peek()
        token = b'True' if first == 84 else b'False'
        for byte in token:
            # Exact adjacency: no whitespace allowed within a boolean token.
            if self.pos >= self.stop or self.raw[self.pos] != byte:
                raise ValueError('header boolean')
            self.pos += 1
        return first == 84

    def dimension(self):
        self.whitespace()
        value = digits = 0
        start = self.pos
        while self.pos < self.stop and 48 <= self.raw[self.pos] <= 57:
            digits += 1
            if digits > 9:
                raise ValueError('dimension digit count')
            value = value * 10 + self.raw[self.pos] - 48
            self.pos += 1
        if not digits or value >= SOURCE_LIMIT or (digits > 1 and self.raw[start] == 48):
            raise ValueError('dimension range')
        return value

    def shape(self):
        self.take(40)
        dims = []
        while self.peek() != 41:
            if len(dims) >= 8:
                raise ValueError('shape rank')
            dims.append(self.dimension())
            if self.peek() == 41 and len(dims) > 1:
                break
            self.take(44)
        self.take(41)
        return dims


def header_from_bytes(raw, ledger, check):
    """Parse the admitted NPY header grammar without copying member payload."""
    check()
    if type(raw) is not bytes or not 10 <= len(raw) < SOURCE_LIMIT:
        raise ValueError('NPY member range')
    if not raw.startswith(b'\x93NUMPY') or raw[6] not in (1, 2, 3) or raw[7] != 0:
        raise ValueError('NPY magic/version')
    width = 2 if raw[6] == 1 else 4
    if len(raw) < 8 + width:
        raise ValueError('NPY length truncated')
    size = sum(raw[8 + i] << (8 * i) for i in range(width))
    start, stop = 8 + width, 8 + width + size
    if not 0 < size <= HEADER_LIMIT or stop > len(raw) or raw[stop - 1] != 10:
        raise ValueError('NPY header range/newline')
    cursor = HeaderCursor(raw, start, stop, ledger, check)
    cursor.take(123)
    values = {}
    for index in range(3):
        key = cursor.string()
        if key not in ('descr', 'fortran_order', 'shape') or key in values:
            raise ValueError('NPY keys')
        cursor.take(58)
        if key == 'descr':
            value = cursor.string()
        elif key == 'fortran_order':
            value = cursor.boolean()
        else:
            value = cursor.shape()
        values[key] = value
        if index < 2:
            cursor.take(44)
    if cursor.peek() == 44:
        cursor.take(44)
    cursor.take(125)
    cursor.whitespace()
    if cursor.pos != stop:
        raise ValueError('trailing header syntax')
    dtype = values['descr']
    if (not 3 <= len(dtype) <= 8 or dtype[0] not in '<>=|' or dtype[1] not in 'biufcSU'
            or dtype[2] not in '123456789' or any(dtype[i] not in '0123456789' for i in range(2, len(dtype)))):
        raise ValueError('NPY dtype')
    kind, itemsize = dtype[1], 0
    for i in range(2, len(dtype)):
        itemsize = itemsize * 10 + ord(dtype[i]) - 48
    allowed = dict(b=(1,), i=(1, 2, 4, 8), u=(1, 2, 4, 8), f=(4, 8), c=(8, 16))
    if kind in allowed and itemsize not in allowed[kind]:
        raise ValueError('dtype item size')
    if kind == 'U':
        itemsize *= 4
    payload = math.prod(values['shape']) * itemsize
    if payload >= SOURCE_LIMIT or stop + payload != len(raw):
        raise ValueError('NPY payload size')
    check()
    return dict(dtype=dtype, shape=values['shape'], fortran_order=values['fortran_order'],
                payload_bytes=payload, offset=stop)


class HeaderArrayLoader:
    """Explicit new wiring of frozen chunk decoder and bounded header parser."""
    def __init__(self, check, stage_limit=STAGE_LIMIT):
        self.check = check
        self.ledger = PayloadLedger(stage_limit)
        self.reservations = self.ledger.budget
        self.loaded = set()
        self.events = []

    def npz(self, raw, sha, label):
        self.check()
        if type(raw) is not bytes or not 22 <= len(raw) < 32 * 1024**2:
            raise ValueError('compressed input range')
        if hashlib.sha256(raw).hexdigest() != sha or label in self.loaded:
            raise ValueError('source SHA/duplicate label')
        self.loaded.add(label)
        rows = members(raw, self.check)
        decoded = {}
        for row in rows:
            value, event = decode_member(raw, row, self.ledger, self.check)
            header = header_from_bytes(value, self.ledger, self.check)
            if header['fortran_order']:
                raise ValueError('Fortran order')
            decoded[row[0]] = (value, header)
            self.events.append(dict(label=label, member=row[0], **event))
        return {name: self.array(value, header) for name, (value, header) in decoded.items()}

    def array(self, raw, header):
        import numpy as np
        self.check()
        a = np.frombuffer(raw, dtype=header['dtype'], offset=header['offset']).reshape(header['shape'])
        if a.dtype.kind in 'fc':
            self.ledger.reserve('array-finite-mask', a.size)
            if not np.all(np.isfinite(a)):
                raise ValueError('nonfinite array')
        if a.dtype.kind == 'b':
            for index in range(header['offset'], len(raw)):
                if (index - header['offset']) % 65536 == 0:
                    self.check()
                if raw[index] not in (0, 1):
                    raise ValueError('boolean storage')
        self.check()
        return a

    def npy(self, raw, sha):
        self.check()
        if type(raw) is not bytes or not 10 <= len(raw) < SOURCE_LIMIT or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('NPY source identity')
        header = header_from_bytes(raw, self.ledger, self.check)
        if header['fortran_order']:
            raise ValueError('Fortran order')
        return self.array(raw, header)

    def copy(self, array):
        import numpy as np
        self.check()
        self.ledger.reserve('array-copy', array.nbytes)
        return np.array(array, copy=True)

    def mirror(self, array):
        import numpy as np
        self.check()
        self.ledger.reserve('array-mirror', 2 * array.nbytes)
        return np.concatenate((array, array[::-1]), axis=0)

    def facts(self):
        return dict(explicit_payload_capacity_reserved_bytes=self.ledger.budget.used,
                    header_payload_copy_bytes=0, header_ast_created=False,
                    entries=list(self.ledger.entries), events=list(self.events),
                    python_object_overhead_metered=False, all_scientific_temporaries_metered=False,
                    whole_lifecycle_guard_verified=False, production_authorized=False)


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: scientific temporary and startup acceptance pending')
