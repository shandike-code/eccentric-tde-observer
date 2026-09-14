import numpy as np

from eccentric_tde_observer.phase7a import (
    select_quasi_static_representative_annuli,
)
from eccentric_tde_observer.reference_case import (
    build_strict_domain_reference_model,
)


def test_representative_annuli_are_real_quasi_static_cells_and_deterministic():
    model = build_strict_domain_reference_model(17, 128)
    first = select_quasi_static_representative_annuli(
        model, count=6, optical_frequency_points=33
    )
    second = select_quasi_static_representative_annuli(
        model, count=6, optical_frequency_points=33
    )

    assert first.count == 6
    assert np.array_equal(first.radial_index, second.radial_index)
    assert np.array_equal(first.anomaly_index, second.anomaly_index)
    assert np.all(first.quasi_static_ratio < first.quasi_static_threshold)
    assert np.all(
        first.effective_temperature_k
        == model.source.effective_temperature_k[
            first.radial_index, first.anomaly_index
        ]
    )
    assert len(set(zip(first.radial_index, first.anomaly_index, strict=True))) == 6


def test_representative_cluster_fractions_and_domain_accounting():
    model = build_strict_domain_reference_model(17, 128)
    selection = select_quasi_static_representative_annuli(
        model, count=6, optical_frequency_points=33
    )

    assert selection.valid_cell_count + selection.excluded_cell_count == 17 * 128
    for fractions in (
        selection.cluster_area_fraction,
        selection.cluster_bolometric_fraction,
        selection.cluster_optical_fraction,
        selection.cluster_mixture_fraction,
    ):
        assert np.isclose(np.sum(fractions), 1.0, rtol=0.0, atol=2.0e-15)
        assert np.all(fractions > 0.0)
    assert 0.0 < selection.valid_area_fraction < 1.0
    assert 0.0 < selection.valid_bolometric_fraction < 1.0
    assert 0.0 < selection.valid_optical_fraction < 1.0
    assert selection.weighted_rms_distance > 0.0
    assert selection.maximum_distance >= selection.weighted_rms_distance
