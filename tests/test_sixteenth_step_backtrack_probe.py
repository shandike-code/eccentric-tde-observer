import json
import numpy as np
import pytest
from operations import sixteenth_step_backtrack_probe as probe


def test_amplitudes_are_scoped_and_restored_on_failure():
    old = probe.batch.ALPHAS, probe.batch.LIMITS
    with pytest.raises(RuntimeError):
        with probe.amplitude_contract():
            assert probe.batch.ALPHAS == {'full': 1/64, 'half': 1/128}
            assert probe.batch.LIMITS == {'control': 2, 'full': 8, 'half': 8}
            raise RuntimeError('injected')
    assert probe.batch.ALPHAS is old[0] and probe.batch.LIMITS is old[1]


def test_unconfirmed_source_does_not_start_maps(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(probe.stage,'configure',lambda *a:None)
    monkeypatch.setattr(probe.stage,'confirmation_passed',lambda *a:False)
    monkeypatch.setattr(probe.stage,'run_next',lambda *a:calls.append('map'))
    with pytest.raises(RuntimeError,match='confirmation'):probe.execute(tmp_path)
    assert not calls


def test_sixteenth_protocol_adapter_retains_all_gates_and_physical_claims(monkeypatch):
    # Existing rebase_payload validation must accept only the newly declared alphas.
    from operations.second_outer_step import validate_trial
    from operations.response_direction_batch import GroundStateLogSimplexCodec,make_trial
    codec=GroundStateLogSimplexCodec(2)
    x=codec.encode(np.array([1e4,2e4]),np.array([[.5,.5],[.6,.4]]),np.array([[.4,.3,.3],[.5,.3,.2]]))
    decoded=codec.decode(x);r=np.full_like(x,.01)
    base={k:np.array(getattr(decoded,k)) for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    base.update(encoded_state=x,base_encoded_state=x.copy(),base_residual=r,finite_direction=r,
        relaxation=np.array(0.),density_g_cm3=np.ones(2),phase_index=np.array(1367),step_duration_s=np.array(889.419892762322))
    with probe.amplitude_contract():
        t=make_trial(base,r,1/64);validate_trial(t,base,r)
        assert np.array_equal(t['encoded_state'],x+r/64)
        for k in ('density_g_cm3','phase_index','step_duration_s'):assert np.array_equal(t[k],base[k])
        with pytest.raises(ValueError,match='undeclared'):make_trial(base,r,1/32)
        t['base_residual']=r*2
        with pytest.raises(ValueError,match='mismatch'):validate_trial(t,base,r)


def test_no_acceptance_cannot_claim_next_stage(monkeypatch,tmp_path):
    monkeypatch.setattr(probe,'require_source',lambda:None)
    monkeypatch.setattr(probe.stage,'run_next',lambda p,s:(p/'status.json').write_text('{"status":"complete"}'))
    monkeypatch.setattr(probe.reused,'archive',lambda *a:None)
    probe.execute(tmp_path)
    d=json.loads((tmp_path/'amplitude-probe-decision.json').read_text())
    assert not d['formal_finite_step_accepted'] and not d['fresh_control_corroborated']
    assert d['requires_review_before_confirmation_or_step17'] and not d['coupled_column_accepted']


def test_prior_program_failure_blocks_retry_before_source_or_maps(monkeypatch,tmp_path):
    (tmp_path/'amplitude-probe-error.json').write_text('{"ledger_only_recoverable":false}')
    calls=[];monkeypatch.setattr(probe,'require_source',lambda:calls.append('source'))
    with pytest.raises(RuntimeError,match='blind retry'):probe.execute(tmp_path)
    assert not calls


def test_native_preflight_requests_one_actual_process_not_four_workers(monkeypatch):
    from operations import step16_backtrack_preflight as native
    calls=[]
    monkeypatch.setattr(native.pipeline,'require_allocation',lambda n:calls.append(n))
    def stop(p):raise RuntimeError('stop before data work')
    monkeypatch.setattr(native.pipeline,'read',stop)
    with pytest.raises(RuntimeError,match='before data'):native.main()
    assert calls==[1]


def test_formal_acceptance_with_failed_fresh_control_does_not_corroborate(monkeypatch,tmp_path):
    monkeypatch.setattr(probe,'require_source',lambda:None)
    monkeypatch.setattr(probe,'ROOT',tmp_path)
    def run(p,s):
        (p/'status.json').write_text('{"status":"formal_acceptance_requires_review","candidate":"full"}')
        (p/'full').mkdir();(p/'full/state.json').write_text('{"diagnostic":{"rounds":[{"ledger":"round/material_energy_ledger.json"}]}}')
        (p/'round').mkdir();(p/'round/fresh_control_comparison.json').write_text('{"comparisons":{}}')
    monkeypatch.setattr(probe.stage,'run_next',run)
    monkeypatch.setattr(probe.batch,'check_budget',lambda s:None)
    monkeypatch.setattr(probe.reused,'archive',lambda *a:None)
    probe.execute(tmp_path)
    d=json.loads((tmp_path/'amplitude-probe-decision.json').read_text())
    assert d['formal_finite_step_accepted'] and not d['fresh_control_corroborated']
    assert d['requires_review_before_confirmation_or_step17']


def test_source_is_the_reviewed_fifteenth_step_and_preflight_checks_claims(monkeypatch):
    calls=[]
    monkeypatch.setattr(probe.stage,'configure',lambda source,index:calls.append((source,index)))
    monkeypatch.setattr(probe.stage,'confirmation_passed',lambda p:True)
    monkeypatch.setattr(probe.pipeline,'read',lambda p:{'native_exact_rebase':True,'alphas':probe.ALPHAS,'sources':['claim']})
    monkeypatch.setattr(probe.reused,'verify',lambda claims:calls.append(claims))
    probe.require_source()
    assert calls==[('outputs/hpc/outer-steps13to15-20260922/step15/next-step',15),['claim']]


def test_wrong_preflight_amplitude_stops_before_maps(monkeypatch,tmp_path):
    monkeypatch.setattr(probe.stage,'configure',lambda *a:None)
    monkeypatch.setattr(probe.stage,'confirmation_passed',lambda p:True)
    monkeypatch.setattr(probe.pipeline,'read',lambda p:{'native_exact_rebase':True,'alphas':{'full':1/128,'half':1/256}})
    with pytest.raises(RuntimeError,match='preflight'):probe.execute(tmp_path)
