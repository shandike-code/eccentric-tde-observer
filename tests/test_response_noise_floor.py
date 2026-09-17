import numpy as np
import pytest

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)
from operations.response_noise_floor import codec_identity_report, solve


def _decoded_trial(codec, encoded):
    """Rebuild a trial the way `pipeline.migrate_trial` does."""
    decoded = codec.decode(encoded)
    return {"temperature_k": np.asarray(decoded.temperature_k),
            "hydrogen_fraction": np.asarray(decoded.hydrogen_fraction),
            "helium_fraction": np.asarray(decoded.helium_fraction)}


def test_extreme_ionization_roundtrip_gate_uses_decode_direction():
    # log-ratio 19 对应 1-h+ ~ 5e-9，encode 方向必然损失约 8 位；
    # decode 方向必须逐位一致，否则文件与编码向量不自洽。
    codec = GroundStateLogSimplexCodec(2)
    encoded = np.array([30.0, 19.02, 16.8, 27.8,
                        28.0, -3.0, 2.0, -1.0])
    trial = _decoded_trial(codec, encoded)
    report = codec_identity_report(codec, encoded, trial)
    assert report["decode_identity_passed"] is True
    assert report["decode_versus_stored_maximum_absolute_difference"] == 0.0
    assert report["encode_roundtrip_maximum_absolute_difference"] > 1e-10
    assert report["encode_roundtrip_per_component"][0] == 0.0      # 热能不损失
    assert report["encode_roundtrip_per_component"][1] > 1e-10     # 只在氢分量


def test_inconsistent_trial_is_rejected():
    codec = GroundStateLogSimplexCodec(2)
    encoded = np.array([30.0, 19.02, 16.8, 27.8, 28.0, -3.0, 2.0, -1.0])
    trial = _decoded_trial(codec, encoded)
    trial["temperature_k"] = trial["temperature_k"] * 1.01
    with pytest.raises(AssertionError):
        report = codec_identity_report(codec, encoded, trial)
        assert report["decode_identity_passed"], report


def test_solve_returns_a_flat_vector_and_one_ulp_probe_is_finite():
    codec = GroundStateLogSimplexCodec(2)
    encoded = codec.encode(np.array([1e5, 1e5]),
                           np.array([[0.2, 0.8], [0.3, 0.7]]),
                           np.array([[0.1, 0.1, 0.8], [0.2, 0.2, 0.6]]))
    density = np.array([1e-10, 1e-10])
    temperature = np.array([1e5, 1e5])
    hydrogen = np.array([[0.2, 0.8], [0.3, 0.7]])
    helium = np.array([[0.1, 0.1, 0.8], [0.2, 0.2, 0.6]])
    feedback = {
        "half_photoionization_s1": np.full((2, 3), 1e-4),
        "half_total_recombination_cm3_s": np.full((2, 3), 1e-30),
        "half_atomic_rate_heating_erg_s_cm3": np.array([1e-12, 1e-12]),
    }
    vector, solved = solve(codec, encoded, density, temperature, hydrogen, helium,
                           1.0e3, feedback, heating_shift_ulp=1)
    assert vector.shape == (8,)
    assert np.all(np.isfinite(vector))
    assert np.all(np.isfinite(np.asarray(solved.temperature_k)))
