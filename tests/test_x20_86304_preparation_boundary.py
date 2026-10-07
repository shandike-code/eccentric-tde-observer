import hashlib
import time
import pytest
from operations import x20_86304_preparation_boundary as boundary


@pytest.mark.parametrize('seconds', [True, 0, -1, 121, float('nan'), float('inf')])
def test_bad_wall_limit(seconds):
    with pytest.raises(ValueError):
        boundary.StopGuard(time.monotonic(), seconds=seconds)


@pytest.mark.parametrize('rss', [True, 0, -1, 1024**3+1, 1.5])
def test_bad_rss_limit(rss):
    with pytest.raises(ValueError):
        boundary.StopGuard(time.monotonic(), rss_bytes=rss)


def test_elapsed_failure_sticky():
    guard = boundary.StopGuard(time.monotonic()-2, seconds=1)
    with pytest.raises(RuntimeError, match='wall limit'):
        guard.check()
    guard.started = time.monotonic()
    with pytest.raises(RuntimeError, match='wall limit'):
        guard.check()


def test_frozen_hash_refusal():
    with pytest.raises(ValueError):
        boundary.FrozenModules({'tiny': (b'x=1', '0'*64, '/tiny.py', False)})


def test_preimport_refusal():
    source = b'x=1'
    with pytest.raises(ValueError, match='already imported'):
        boundary.FrozenModules({'sys': (source, hashlib.sha256(source).hexdigest(), '/sys.py', False)})


def test_native_stays_closed():
    with pytest.raises(RuntimeError, match='DO NOT RUN'):
        boundary.native_configuration(synthetic=True)
