import json
import tarfile
import pytest
from operations import x20_85889_chord_receipt as r


@pytest.mark.parametrize('state,terminal,successful',[('RUNNING',False,False),('COMPLETED',True,True),('TIMEOUT',True,False),('OUT_OF_MEMORY',True,False)])
def test_scheduler(state,terminal,successful):
    x=r.parse_terminal(12,f'JobId=12 JobState={state} ExitCode=0:0')
    assert x['terminal']==terminal and x['successful']==successful


def test_scheduler_false_success():
    assert not r.parse_terminal(12,'JobId=12 JobState=COMPLETED ExitCode=1:0')['successful']
    with pytest.raises(ValueError):r.parse_terminal(12,'JobId=13 JobState=COMPLETED ExitCode=0:0')
    with pytest.raises(ValueError):r.parse_terminal(12,'Invalid job id specified')


def test_archive(tmp_path):
    run=tmp_path/'run';run.mkdir();(run/'failure.json').write_text('{"failed":true}')
    (run/'unexpected.dat').write_bytes(b'secret-not-archived')
    p=tmp_path/'small.tar.gz';receipt=r.archive(run,p,[])
    with tarfile.open(p) as tar:assert tar.getnames()==['failure.json']
    assert not receipt['scheduler_terminal_verified'] and receipt['dat_files']==0
    with pytest.raises(FileExistsError):r.archive(run,p,[])


@pytest.mark.parametrize('kind',['dat','link','duplicate'])
def test_archive_reject(tmp_path,kind):
    run=tmp_path/'run';run.mkdir();p=run/'result.json';p.write_text('{}')
    q=tmp_path/('x.dat' if kind=='dat' else 'x.json')
    if kind=='link':q.symlink_to(p)
    else:q.write_text('{}')
    with pytest.raises(ValueError):r.archive(run,tmp_path/'bad.tar.gz',[p if kind=='duplicate' else q])


def test_watch_latches_terminal(tmp_path,monkeypatch):
    class P:returncode=0;stdout='JobId=12 JobState=COMPLETED ExitCode=0:0';stderr=''
    calls=[]
    def run(*a,**kw):calls.append(a);return P()
    monkeypatch.setattr(r.subprocess,'run',run)
    out=tmp_path/'watch';x=r.observe('12',out)
    assert x['successful'] and len(calls)==1
    assert json.loads((out/'scheduler-terminal.json').read_text())['terminal']
