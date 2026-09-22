import pytest
from types import SimpleNamespace
from operations import bounded_steps9_to11 as task


def test_configuration_tracks_actual_source_index_and_restores_on_error(monkeypatch):
    stage=task.stage;seq=task.sequence;c=task.confirmation
    def configure(source,index):
        stage.SOURCE=source;stage.ACCEPTED_INDEX=index;stage.FORMAL_SOURCE='actual-protocol-base'
    monkeypatch.setattr(stage,'configure',configure)
    previous=(seq.SOURCE,seq.FIRST_INDEX,stage.prepare_confirmation,stage.batch.ALPHAS,
              stage.SOURCE,stage.ACCEPTED_INDEX,stage.FORMAL_SOURCE,c.SOURCE,c.ACCEPTED_INDEX,c.FORMAL_SOURCE)
    with pytest.raises(RuntimeError,match='injected'):
        with task.sequence_contract():
            assert seq.FIRST_INDEX==9 and seq.SOURCE==task.SOURCE
            assert stage.batch.ALPHAS=={'full':1/128,'half':1/256}
            for index in range(8,12):
                stage.configure(f'actual-source-{index}',index)
                assert c.SOURCE==f'actual-source-{index}' and c.ACCEPTED_INDEX==index
                assert c.FORMAL_SOURCE=='actual-protocol-base'
                assert stage.prepare_confirmation is c.prepare_confirmation
            with pytest.raises(ValueError):stage.configure('invalid',12)
            raise RuntimeError('injected')
    assert stage.configure is configure
    assert previous==(seq.SOURCE,seq.FIRST_INDEX,stage.prepare_confirmation,stage.batch.ALPHAS,
                      stage.SOURCE,stage.ACCEPTED_INDEX,stage.FORMAL_SOURCE,c.SOURCE,c.ACCEPTED_INDEX,c.FORMAL_SOURCE)


@pytest.mark.parametrize('failed_cycle',[None,9,10,11])
def test_conditional_three_cycles_and_final_confirmation(monkeypatch,tmp_path,failed_cycle):
    seq=task.sequence;stage=task.stage;events=[]
    monkeypatch.setattr(seq,'ROOT',tmp_path)
    monkeypatch.setattr(seq,'declare',lambda p:None)
    monkeypatch.setattr(seq,'budget',lambda p:{})
    monkeypatch.setattr(seq.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(seq.reused,'archive',lambda *a:None)
    monkeypatch.setattr(__import__('shutil'),'disk_usage',lambda p:SimpleNamespace(free=10**15))
    def configure(source,index):
        stage.SOURCE=source;stage.ACCEPTED_INDEX=index;stage.FORMAL_SOURCE='actual-base'
        events.append(('source',index))
    monkeypatch.setattr(stage,'configure',configure)
    monkeypatch.setattr(seq,'transition',lambda *a:None)
    def execute(folder):
        i=int(folder.name[4:]);events.append(('step',i))
        assert task.confirmation.ACCEPTED_INDEX==i-1
        seq.pipeline.write_json(folder/'status.json',{'status':'confirmation_not_passed' if failed_cycle==i else 'formal_acceptance_requires_review','fresh_control_corroborated':True})
    monkeypatch.setattr(stage,'execute',execute)
    monkeypatch.setattr(seq,'continuation_ready',lambda p:True)
    monkeypatch.setattr(stage,'run_confirmation',lambda p:events.append(('tail',task.confirmation.ACCEPTED_INDEX)))
    monkeypatch.setattr(stage,'confirmation_passed',lambda p:True)
    with task.sequence_contract():seq.execute(tmp_path)
    expected=list(range(9,12 if failed_cycle is None else failed_cycle+1))
    assert [i for name,i in events if name=='step']==expected
    status=seq.pipeline.read(tmp_path/'status.json')['status']
    if failed_cycle is None:
        assert events[-1]==('tail',11) and status=='complete_requires_review'
    else:
        assert all(name!='tail' for name,_ in events) and status=='science_stopped'


def test_contract_rejects_changed_global_budget_and_restores(monkeypatch):
    monkeypatch.setattr(task.sequence,'MAXIMUM_MAPS',79)
    previous=task.stage.batch.ALPHAS
    with pytest.raises(RuntimeError,match='contract changed'):
        with task.sequence_contract():pass
    assert task.stage.batch.ALPHAS is previous
