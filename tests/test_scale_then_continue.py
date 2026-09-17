import pytest
from operations.scale_then_continue import select_workers, ORDER


def cases():
    return [dict(workers=w, output_sha256='same', maximum_worker_rss_mib=3500,
                 wall_s=t) for w,t in zip(ORDER, [400,200,190,600,210,410])]


def test_selection_uses_repeated_median_not_fastest_single_case():
    choice, medians = select_workers(cases())
    assert choice == 8
    assert medians == {4:405, 8:205, 16:395}


@pytest.mark.parametrize('kind', ['incomplete', 'hash', 'memory'])
def test_unsafe_or_incomplete_benchmark_cannot_start_science(kind):
    data=cases()
    if kind=='incomplete': data.pop()
    if kind=='hash': data[-1]['output_sha256']='different'
    if kind=='memory': data[-1]['maximum_worker_rss_mib']=6144
    with pytest.raises(RuntimeError): select_workers(data)


def test_copy_preserves_material_and_pins_own_trial(tmp_path, monkeypatch):
    import operations.scale_then_continue as m
    monkeypatch.setattr(m.pipeline, 'ROOT', tmp_path)
    source=tmp_path/'source';source.mkdir()
    (source/'trial_material.npz').write_bytes(b'exact material bytes')
    digest=m.pipeline.sha256(source/'trial_material.npz')
    m.pipeline.write_json(source/'state.json', {'trial_sha256':digest})
    monkeypatch.setattr(m, 'load_arrays', lambda p: {})
    monkeypatch.setattr(m, 'audit_native_trial', lambda cfg,data: {'verified':True})
    template={'sources':[], 'candidate_relaxation':.03125}
    run=tmp_path/'new'
    m.prepare_copy(template, source, {'path':'seed','sha256':'seedhash'}, run, 8, 32, [])
    assert (run/'trial_material.npz').read_bytes()==b'exact material bytes'
    config=m.pipeline.read(run/'config.json')
    assert config['sources'][-1]['sha256']==digest
    assert config['workers']==8 and config['maximum_maps']==32
    assert template=={'sources':[], 'candidate_relaxation':.03125}
    with pytest.raises(FileExistsError):
        m.prepare_copy(template, source, {}, run, 8, 32, [])
