"""Tiny real subprocesses; no numerical/native inputs or historical tests."""
import json
import signal
import sys
from pathlib import Path

import pytest

from operations.x20_86304_preparation_supervisor import supervise, native_configuration


def launch(tmp_path, code, **kwargs):
    return supervise([sys.executable, '-I', '-S', '-c', code], tmp_path/'run', **kwargs)


def test_normal_prefix_receipt(tmp_path):
    result = launch(tmp_path, "print('tiny synthetic success')")
    assert result['success'] and result['returncode'] == 0
    assert (tmp_path/'run/stdout.log').read_text() == 'tiny synthetic success\n'
    assert json.loads((tmp_path/'run/outcome.json').read_text()) == result
    assert result['outer_limit_s'] == 150
    assert not result['production_authorized']


def test_partial_failure(tmp_path):
    result = launch(tmp_path, "import sys; print('partial',flush=True); sys.exit(7)")
    assert result['reason'] == 'child_exit' and result['returncode'] == 7
    assert not result['success']
    assert (tmp_path/'run/stdout.log').read_text() == 'partial\n'


def test_ignore_signal_hard_kill(tmp_path):
    result = launch(tmp_path, 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); signal.signal(signal.SIGALRM,signal.SIG_IGN); print("ready",flush=True); time.sleep(30)', outer_seconds=.4)
    assert result['reason'] == 'outer_deadline'
    assert result['kill_sent'] and result['returncode'] == -signal.SIGKILL
    assert not result['success']


def test_output_flood_bounded(tmp_path):
    result = launch(tmp_path, "import os; os.write(1,b'x'*65536)", output_limit=257)
    assert result['reason'] == 'output_limit' and not result['success']
    assert sum(x['size_bytes'] for x in result['outputs'].values()) == 257
    assert (tmp_path/'run/stdout.log').stat().st_size == 257


@pytest.mark.parametrize('field,value', [('outer_seconds',True),('outer_seconds',0),
    ('outer_seconds',151),('outer_seconds',float('nan')),('outer_seconds',float('inf')),
    ('output_limit',True),('output_limit',0),('output_limit',8*1024**2+1)])
def test_limits_cannot_expand(tmp_path, field, value):
    with pytest.raises(ValueError):
        launch(tmp_path, 'pass', **{field:value})
    assert not (tmp_path/'run').exists()


def test_refuses_existing_directory(tmp_path):
    launch(tmp_path, 'pass')
    with pytest.raises(FileExistsError): launch(tmp_path, 'pass')


def test_failed_spawn_retains_intent_and_outcome(tmp_path):
    with pytest.raises(FileNotFoundError):
        supervise(['/not-a-real-executable-86304'], tmp_path/'run')
    outcome=json.loads((tmp_path/'run/outcome.json').read_text())
    assert outcome['reason']=='parent_exception:FileNotFoundError'
    assert outcome['returncode'] is None and not outcome['success']


@pytest.mark.parametrize('mode', ['rss','time','signal'])
def test_original_internal_guard(tmp_path, mode):
    boundary=Path(__file__).resolve().parents[1]/'operations/x20_86304_preparation_boundary.py'
    # Authenticated source identity is checked externally by the exercise freeze.
    code=f'''import time
started=time.monotonic()
import runpy,signal,os
b=runpy.run_path({str(boundary)!r})
g=b['StopGuard'](started, seconds=0.05 if {mode!r}=='time' else 120, rss_bytes=1 if {mode!r}=='rss' else 1024**3)
g.install()
if {mode!r}=='signal': os.kill(os.getpid(),signal.SIGUSR1)
time.sleep(.1)
g.check()
'''
    result=launch(tmp_path,code,outer_seconds=3)
    assert result['reason']=='child_exit' and result['returncode']!=0
    error=(tmp_path/'run/stderr.log').read_text()
    assert ('RSS limit' if mode=='rss' else 'signal:') in error


def test_production_closed():
    with pytest.raises(RuntimeError,match='DO NOT RUN'): native_configuration(synthetic=True)
