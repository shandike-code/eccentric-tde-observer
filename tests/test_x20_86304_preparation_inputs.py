import copy
import hashlib
import io
import os
from pathlib import Path
import struct
import zipfile
from unittest.mock import patch

import numpy as np
import pytest
from operations import x20_86304_preparation_inputs as p
from handoff.audit_tools import review_x20_86304_preparation_inputs as oracle


def fixture(**changes):
    arrays = dict(encoded_state=np.arange(12, dtype='<f8'), base_encoded_state=np.arange(12, dtype='<f8'),
                  finite_direction=np.zeros(12), base_residual=np.zeros(12), relaxation=np.array(0.),
                  density_g_cm3=np.array([1., 2., 3.]), temperature_k=np.array([4., 5., 6.]),
                  hydrogen_fraction=np.array([[.25, .75]]*3),
                  helium_fraction=np.array([[.25, .25, .5]]*3),
                  specific_material_energy_erg_g=np.array([8., 9., 10.]))
    arrays.update(changes)
    f = io.BytesIO(); np.savez_compressed(f, **arrays)
    return f.getvalue()


def row(path, raw):
    return dict(path=path, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def expected(raw):
    return p.expected_fingerprints(raw, raw, p.Budget(p.STAGE_LIMIT), p.Budget(p.READ_LIMIT))


def test_oracle_and_input_unchanged():
    raw = fixture(); before = bytes(raw)
    result = expected(raw)
    assert oracle.review_synthetic(raw, result)['mirrors_verified'] == 4
    assert raw == before
    assert result['loader_returned_bytes'] > 2*len(raw)  # ZIP seeks/repeated reads count.
    with pytest.raises(ValueError, match='mirror fingerprint'):
        result['mirrors']['hydrogen_parent']['sha256'] = '0'*64
        oracle.review_synthetic(raw, result)


@pytest.mark.parametrize('flag', ['exact_trial_decode_verified', 'physical_old_r20_verified', 'process_guard_verified', 'live_native_recomputed'])
def test_oracle_no_upgrades(flag):
    raw = fixture(); result = expected(raw); result[flag] = True
    with pytest.raises(ValueError, match='qualification'): oracle.review_synthetic(raw, result)


@pytest.mark.parametrize('name', ['a.dat', 'a.DAT', 'a.dat/child.json', '../x.json', '/x.json', 'a//x.json', './x.json', 'a\\x.json'])
def test_lexical_refusal_before_any_metadata(name):
    with patch.object(os, 'dup', side_effect=AssertionError('metadata reached')):
        with pytest.raises(ValueError): p.authenticated_read(-1, row(name, b'{}'), p.Budget(100))


@pytest.mark.parametrize('operation', ['read', 'readinto', 'readline', 'readall'])
def test_meter_methods_and_seek(operation):
    budget = p.Budget(20); events = []; f = p.MeteredBytes(b'ab\ncd', budget, events, 's')
    if operation == 'readinto':
        buffer = bytearray(3); assert f.readinto(buffer) == 3; assert buffer == b'ab\n'
    else: getattr(f, operation)()
    used = budget.used
    f.seek(0); assert f.read(2) == b'ab'; assert budget.used == used+2
    assert sum(x['returned_bytes'] for x in events) == budget.used
    f.seek(100); assert f.read() == b''
    with pytest.raises(io.UnsupportedOperation): f.fileno()
    f.close()
    with pytest.raises(ValueError): f.read()


def test_meter_strict_cap_before_return():
    f = p.MeteredBytes(b'abc', p.Budget(3), [], 's')
    with pytest.raises(ValueError, match='strict byte'): f.read()
    assert f.tell() == 0


@pytest.mark.parametrize('kwargs', [{'limit': True}, {'limit': 0}, {'limit': -1}])
def test_budget_bad(kwargs):
    with pytest.raises(ValueError): p.Budget(**kwargs)


@pytest.mark.parametrize('change', [dict(temperature_k=np.array([np.nan])), dict(temperature_k=np.array([np.inf])),
                                   dict(encoded_state=np.array([object()], dtype=object)),
                                   dict(hydrogen_fraction=np.asfortranarray(np.arange(6.).reshape(3, 2)))])
def test_bad_arrays(change):
    with pytest.raises(ValueError): expected(fixture(**change))


def test_trial_disagreement():
    with pytest.raises(ValueError, match='trial/base'):
        p.expected_fingerprints(fixture(), fixture(relaxation=np.array(.5)), p.Budget(p.STAGE_LIMIT), p.Budget(p.READ_LIMIT))


def npy(descr='<f8', shape=(2,), extra='', payload=b'\0'*16):
    header = ("{'descr': %r, 'fortran_order': False, 'shape': %r%s}\n" % (descr, shape, extra)).encode()
    return b'\x93NUMPY\x01\x00'+struct.pack('<H', len(header))+header+payload


@pytest.mark.parametrize('raw', [npy(shape=(True,)), npy(shape=(-1,)), npy(shape=(2**40,)),
                               npy(descr='|O8'), npy(extra=", 'shape': (2,)"), npy(payload=b'\0'),
                               b'\x93NUMPY\x01\x00\xff\xff'])
def test_malicious_npy_headers(raw):
    with pytest.raises(ValueError): p.npy_header(io.BytesIO(raw), len(raw))


@pytest.mark.parametrize('name', ['../x.npy', 'a/x.npy', 'x.json', 'x\\y.npy', '.npy'])
def test_archive_member_names(name):
    f = io.BytesIO()
    with zipfile.ZipFile(f, 'w') as z: z.writestr(name, npy())
    with pytest.raises(ValueError): p.inspect_npz(f.getvalue(), p.Budget(p.STAGE_LIMIT))


def test_archive_duplicate_and_link():
    for link in (False, True):
        f = io.BytesIO()
        with zipfile.ZipFile(f, 'w') as z:
            info = zipfile.ZipInfo('x.npy'); info.external_attr = (0o120777 if link else 0o100600) << 16
            z.writestr(info, npy())
            if not link:
                with pytest.warns(UserWarning): z.writestr('x.npy', npy())
        with pytest.raises(ValueError): p.inspect_npz(f.getvalue(), p.Budget(p.STAGE_LIMIT))


def test_decoded_stage_cap():
    with pytest.raises(ValueError, match='strict byte'): p.inspect_npz(fixture(), p.Budget(16))


def test_corrupt_payload_crc():
    f = io.BytesIO()
    with zipfile.ZipFile(f, 'w', compression=zipfile.ZIP_STORED) as z: z.writestr('x.npy', npy(payload=b'1'*16))
    raw = f.getvalue().replace(b'1'*16, b'2'*16)
    with pytest.raises(zipfile.BadZipFile): p.fingerprints(raw, p.Budget(p.STAGE_LIMIT), p.Budget(p.READ_LIMIT))


def test_staging_exclusive_and_verified(tmp_path):
    (tmp_path/'source.json').write_bytes(b'{"a":1}')
    source = row('source.json', b'{"a":1}'); dest = dict(source, path='receipt/a.json')
    plan = p.staging_plan([dest], {dest['path']: source})
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        result = p.stage_small_sources(fd, fd, 'stage', plan, p.Budget(10000))
        assert (tmp_path/'stage/receipt/a.json').read_bytes() == b'{"a":1}'
        assert result['authentication_returned_bytes'] == 14
        assert result['actual_source_manifest_prepared'] is False
        with pytest.raises(FileExistsError): p.stage_small_sources(fd, fd, 'stage', plan, p.Budget(10000))
    finally: os.close(fd)


@pytest.mark.parametrize('kind', ['file', 'ancestor', 'sha', 'size'])
def test_authenticated_read_rejects(tmp_path, kind):
    (tmp_path/'a.json').write_bytes(b'{}'); (tmp_path/'alias.json').symlink_to('a.json')
    (tmp_path/'directory').symlink_to(tmp_path, target_is_directory=True)
    r = row({'file': 'alias.json', 'ancestor': 'directory/a.json'}.get(kind, 'a.json'), b'{}')
    if kind == 'sha': r['sha256'] = '0'*64
    if kind == 'size': r['size_bytes'] = 3
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises((ValueError, OSError)): p.authenticated_read(fd, r, p.Budget(1000))
    finally: os.close(fd)


def test_staging_complete_map_and_partial_retained(tmp_path):
    a = row('a.json', b'{}'); b = row('b.json', b'{}')
    with pytest.raises(ValueError): p.staging_plan([a, b], {'a.json': a})
    with pytest.raises(ValueError): p.staging_plan([a, a], {'a.json': a})
    (tmp_path/'a.json').write_bytes(b'{}')
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(FileNotFoundError):
            p.stage_small_sources(fd, fd, 'partial', p.staging_plan([a, b], {'a.json': a, 'b.json': b}), p.Budget(1000))
        assert (tmp_path/'partial/a.json').read_bytes() == b'{}'
    finally: os.close(fd)


@pytest.mark.parametrize('kwargs', [{}, {'process_guard_verified': True}, {'synthetic': True}])
def test_native_always_closed(kwargs):
    with pytest.raises(RuntimeError, match='DO NOT RUN'): p.native_configuration(**kwargs)
