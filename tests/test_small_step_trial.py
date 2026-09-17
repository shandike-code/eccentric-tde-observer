import numpy as np
import pytest

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)
from operations.prepare_small_step_trial import build_trial, claim


def _source_trial(alpha=0.0625, cells=3, seed=7):
    codec = GroundStateLogSimplexCodec(cells)
    rng = np.random.default_rng(seed)
    base = np.concatenate([
        rng.normal(28.0, 0.5, cells),
        rng.normal(0.5, 0.2, cells),
        rng.normal(0.5, 0.2, cells),
        rng.normal(0.5, 0.2, cells)])
    direction = rng.normal(0.0, 0.05, 4 * cells)
    # 生产 trial 的不变量：物理量是 decode(base + alpha*direction)。
    decoded = codec.decode(base + alpha * direction)
    trial = {
        "phase_index": np.array(3),
        "step_duration_s": np.array(889.419892762322),
        "density_g_cm3": np.full(cells, 1e-9),
        "temperature_k": decoded.temperature_k,
        "hydrogen_fraction": decoded.hydrogen_fraction,
        "helium_fraction": decoded.helium_fraction,
        "specific_material_energy_erg_g": decoded.specific_material_energy_erg_g,
        "base_encoded_state": base,
        "finite_direction": direction,
        "encoded_state": base + alpha * direction,
        "base_residual": np.zeros(4 * cells),
        "relaxation": np.array(alpha),
    }
    old = {"step_duration_s": np.full(8, 889.419892762322),
           "density_g_cm3": np.full((8, cells), 1e-9)}
    return codec, trial, old


def test_smaller_step_keeps_base_and_direction_and_scales():
    codec, source, old = _source_trial()
    trial, gates = build_trial(source, old, np.zeros(12), 0.015625)
    assert np.array_equal(trial["base_encoded_state"], source["base_encoded_state"])
    assert np.array_equal(trial["finite_direction"], source["finite_direction"])
    expected = np.asarray(source["base_encoded_state"]) + 0.015625 * np.asarray(
        source["finite_direction"])
    assert np.array_equal(np.asarray(trial["encoded_state"]), expected)
    assert float(trial["relaxation"]) == 0.015625
    assert all(gates["trust_region_and_provenance"].values())
    assert gates["ratio_to_source"] == pytest.approx(0.25)
    decoded = codec.decode(trial["encoded_state"])
    assert np.array_equal(np.asarray(trial["temperature_k"]), np.asarray(decoded.temperature_k))


@pytest.mark.parametrize("alpha", [0.0625, 0.2, 0.0, -0.01, float("nan"), float("inf")])
def test_step_must_be_strictly_smaller_and_positive(alpha):
    _codec, source, old = _source_trial()
    with pytest.raises(SystemExit):
        build_trial(source, old, np.zeros(12), alpha)


def test_changed_base_residual_is_rejected():
    _codec, source, old = _source_trial()
    with pytest.raises(RuntimeError):
        build_trial(source, old, np.full(12, 0.1), 0.015625)


def test_off_direction_source_is_rejected():
    _codec, source, old = _source_trial()
    source["encoded_state"] = np.asarray(source["encoded_state"]) + 0.01
    with pytest.raises(RuntimeError):
        build_trial(source, old, np.zeros(12), 0.015625)


def test_changed_physical_time_level_is_rejected():
    _codec, source, old = _source_trial()
    old["step_duration_s"] = np.full(8, 700.0)
    with pytest.raises(RuntimeError):
        build_trial(source, old, np.zeros(12), 0.015625)


def test_malformed_trial_is_rejected_before_writing():
    _codec, source, old = _source_trial()
    trial, _gates = build_trial(source, old, np.zeros(12), 0.015625)
    claim(trial)
    missing = dict(trial)
    missing.pop("finite_direction")
    with pytest.raises(SystemExit):
        claim(missing)
    broken = dict(trial)
    broken["temperature_k"] = np.full(3, -1.0)
    with pytest.raises(SystemExit):
        claim(broken)
    nonfinite = dict(trial)
    nonfinite["encoded_state"] = np.full(12, np.nan)
    with pytest.raises(SystemExit):
        claim(nonfinite)
