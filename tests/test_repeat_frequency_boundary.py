from pathlib import Path
import pytest
from operations import repeat_frequency_boundary as repeat


@pytest.mark.parametrize('endpoint',['previous','final'])
def test_worker_selects_declared_endpoint_before_loading_large_state(monkeypatch,endpoint):
    plan={'claims':[],'source':'synthetic/round2','endpoint':endpoint}
    protocol={'token':'distinct source'};seen=[]
    monkeypatch.setattr(repeat.pipeline,'read',lambda p: plan if str(p)=='plan.json' else protocol)
    monkeypatch.setattr(repeat.reused,'verify',lambda claims:None)
    monkeypatch.setattr(repeat.pair,'_validate_worker_template_sources',lambda p:{'template':True})
    class ReachedAdapter(Exception):pass
    def adapt(p,t,label):
        seen.append((p,t,label));raise ReachedAdapter
    monkeypatch.setattr(repeat.pair,'adapt_phase7b7j_worker_protocol',adapt)
    with pytest.raises(ReachedAdapter):repeat.worker(Path('plan.json'),0,Path('unused'))
    assert seen==[(protocol,{'template':True},endpoint)]
