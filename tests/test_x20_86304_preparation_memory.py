"""Small adversarial controls for the new memory loader; no source fixtures."""
import hashlib
import io
import json
import zipfile
import numpy as np
import pytest
from operations.x20_86304_preparation_memory import ArrayLoader, frozen_project, native_configuration


def blob(value):
    stream = io.BytesIO(); np.savez_compressed(stream, a=value)
    return stream.getvalue()


def load(raw, **limits):
    return ArrayLoader(**limits).npz(raw, hashlib.sha256(raw).hexdigest(), 'tiny')


@pytest.mark.parametrize('value', [np.array([np.nan]), np.array([np.inf]),
    np.array([object()]), np.asfortranarray(np.ones((2, 3)))])
def test_invalid_arrays(value):
    with pytest.raises(ValueError): load(blob(value))


@pytest.mark.parametrize('limits', [dict(read_limit=1),dict(stage_limit=1),dict(read_limit=True),dict(stage_limit=True),dict(read_limit=256*1024**2+1),dict(stage_limit=512*1024**2+1)])
def test_limits(limits):
    with pytest.raises(ValueError): load(blob(np.ones(3)), **limits)


def test_returned_byte_accounting_and_immutable():
    raw=blob(np.arange(12.).reshape(4,3)); meter=ArrayLoader()
    arrays=meter.npz(raw,hashlib.sha256(raw).hexdigest(),'tiny')
    with zipfile.ZipFile(io.BytesIO(raw)) as z: size=sum(x.file_size for x in z.infolist())
    assert meter.decompressed.used == size
    assert meter.read.used == sum(e['returned_bytes'] for e in meter.events)
    assert arrays['a'].flags.writeable is False
    with pytest.raises(ValueError): meter.npz(raw,hashlib.sha256(raw).hexdigest(),'tiny')
    with pytest.raises(ValueError): arrays['a'][0,0]=2


@pytest.mark.parametrize('name', ['../a.npy','sub/a.npy','a.txt'])
def test_member_names(name):
    value=io.BytesIO();np.save(value,np.ones(2))
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,value.getvalue())
    with pytest.raises(ValueError):load(archive.getvalue())


def test_corruption_and_wrong_sha():
    raw=blob(np.ones(2))
    with pytest.raises(ValueError):ArrayLoader().npz(raw,'0'*64,'tiny')
    with pytest.raises(zipfile.BadZipFile):load(raw[:-20])


@pytest.mark.parametrize('change', [dict(sha256='0'*64),dict(path='../bad.py'),dict(size_bytes=True),dict(package=1),dict(namespace=1)])
def test_source_rejected(change):
    raw=b'x=1\n';row=dict(path='tiny.py',source=raw.decode(),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw),package=False,namespace=False)
    row.update(change)
    with pytest.raises(ValueError):frozen_project({'not_imported_tiny':row},'/synthetic')


def test_production_closed():
    with pytest.raises(RuntimeError,match='DO NOT RUN'):native_configuration(synthetic=True)
