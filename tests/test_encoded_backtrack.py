from copy import deepcopy
import numpy as np
import pytest

from operations.prepare_encoded_backtrack import candidate_arrays
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def example():
    codec = GroundStateLogSimplexCodec(2)
    base = codec.encode(np.array([15000., 40000.]), np.array([[.8,.2],[.3,.7]]),
                        np.array([[.7,.2,.1],[.2,.5,.3]]))
    direction = np.linspace(.001, .02, len(base))
    encoded = base + .0625 * direction
    decoded = codec.decode(encoded)
    source = {"base_encoded_state": base, "finite_direction": direction, "encoded_state": encoded,
              "base_residual": np.ones_like(base), "relaxation": np.array(.0625),
              "phase_index": np.array(0), "step_duration_s": np.array(3.),
              "density_g_cm3": np.array([1e-10,2e-10])}
    for field in ("temperature_k", "hydrogen_fraction", "helium_fraction", "specific_material_energy_erg_g"):
        source[field] = np.array(getattr(decoded, field))
    old = {"density_g_cm3": source["density_g_cm3"][None,:], "step_duration_s": np.array([3.])}
    return source, old


def test_backtrack_preserves_original_base_direction_and_physical_time():
    source, old = example();before = deepcopy(source)
    new, gates = candidate_arrays(source, old, source["base_residual"], .03125)
    assert all(gates.values())
    np.testing.assert_array_equal(new["encoded_state"], source["base_encoded_state"] + .03125*source["finite_direction"])
    for key in ("base_encoded_state", "finite_direction", "step_duration_s", "density_g_cm3", "base_residual"):
        np.testing.assert_array_equal(new[key], source[key])
    for key in source:
        np.testing.assert_array_equal(source[key], before[key])
    assert not np.array_equal(new["temperature_k"], source["temperature_k"])


@pytest.mark.parametrize("fraction", [0., -.1, .0625, .125, np.nan])
def test_only_smaller_positive_steps(fraction):
    source, old = example()
    with pytest.raises(ValueError): candidate_arrays(source, old, source["base_residual"], fraction)


@pytest.mark.parametrize("field", ["finite_direction", "encoded_state", "temperature_k", "step_duration_s", "base_residual"])
def test_refuses_lineage_decode_dt_and_baseline_tampering(field):
    source, old = example();baseline = source["base_residual"].copy()
    source[field] = source[field] + .001
    with pytest.raises(RuntimeError): candidate_arrays(source, old, baseline, .03125)


def test_legacy_state_trial_identity_is_anchored_to_completed_formal_protocol(tmp_path, monkeypatch):
    import operations.prepare_encoded_backtrack as module
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.pipeline, "ROOT", tmp_path)
    run = tmp_path / "run";folder = run / "feedback-round1"
    folder.mkdir(parents=True)
    trial = run / "trial_material.npz";trial.write_bytes(b"frozen material")
    frozen = folder / "trial_material.npz";frozen.write_bytes(trial.read_bytes())
    protocol = folder / "feedback_protocol.json"
    module.pipeline.write_json(protocol, {"sources":{"trial_material":module.pipeline.claim(frozen)}})
    state = {"diagnostic":{"rounds":[{"ledger":"run/feedback-round1/ledger.json",
                                      "protocol_sha256":module.pipeline.sha256(protocol)}]}}
    assert module.verified_source_trial(run,state)[1]["sha256"] == module.pipeline.sha256(trial)
    trial.write_bytes(b"tampered")
    with pytest.raises(RuntimeError,match="differs"):
        module.verified_source_trial(run,state)


def test_initialization_uses_zero_map_api_without_legacy_trial_fallback(tmp_path, monkeypatch):
    import operations.prepare_encoded_backtrack as module
    module.pipeline.write_json(tmp_path / "config.json", {"candidate_relaxation": .03125})
    called = []
    monkeypatch.setattr(module.pipeline, "run_pipeline", lambda run, **kwargs: called.append((run,kwargs)))
    with pytest.raises(RuntimeError,match="no legacy fallback"):
        module.initialize_declared_trial(tmp_path)
    assert not called
    (tmp_path / "trial_material.npz").write_bytes(b"owned trial")
    module.initialize_declared_trial(tmp_path)
    assert called == [(tmp_path, {"maps_per_job":0,"do_feedback":False})]
