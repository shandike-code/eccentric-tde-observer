from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.log_frequency_moments import (
    log_frequency_group_p1_gauss_node_values,
    lorentz_translate_log_frequency_group_p1_intensity,
)


def test_log_p1_lorentz_translation_is_exact_for_linear_energy_density():
    source_y = np.linspace(1.0, 5.0, 101)
    target_y = np.linspace(2.0, 4.0, 51)
    source_edge = np.exp(source_y)
    target_edge = np.exp(target_y)
    doppler = np.array([0.92, 1.07])
    centre = 0.5 * (source_y[:-1] + source_y[1:])
    width = np.diff(source_y)
    intercept = 2.0
    slope = 0.15
    mean = np.broadcast_to(
        intercept + slope * centre[:, None],
        (centre.size, doppler.size),
    ).copy()
    first = np.broadcast_to(slope * width[:, None] / 6.0, mean.shape).copy()
    result = lorentz_translate_log_frequency_group_p1_intensity(
        mean,
        first,
        source_edge,
        target_edge,
        doppler,
        direction="lab_to_comoving",
    )
    target_centre = 0.5 * (target_y[:-1] + target_y[1:])[:, None]
    target_width = np.diff(target_y)[:, None]
    shift = np.log(doppler)[None, :]
    amplitude = doppler[None, :] ** 4
    expected_mean = amplitude * (
        intercept + slope * (target_centre - shift)
    )
    expected_first = amplitude * slope * target_width / 6.0
    np.testing.assert_allclose(result.mean_density, expected_mean, rtol=4.0e-14)
    np.testing.assert_allclose(
        result.first_moment_density, expected_first, rtol=2.0e-10, atol=2.0e-14
    )
    assert result.limited_group_count == 0


def test_zero_velocity_log_p1_translation_preserves_both_moments_exactly():
    edge = np.geomspace(1.0, 100.0, 81)
    rng = np.random.default_rng(20260829)
    mean = 1.0 + rng.random((edge.size - 1, 3, 2))
    first = 0.1 * (rng.random(mean.shape) - 0.5) * mean
    result = lorentz_translate_log_frequency_group_p1_intensity(
        mean,
        first,
        edge,
        edge,
        np.ones((3, 2)),
        direction="lab_to_comoving",
    )
    assert np.array_equal(result.mean_density, mean)
    assert np.array_equal(result.first_moment_density, first)
    assert result.limited_group_count == 0


def test_log_p1_group_integral_is_positive_after_gauss_reconstruction():
    mean = np.array([1.0, 2.0])
    first = np.array([0.2, -0.3])
    node = log_frequency_group_p1_gauss_node_values(mean, first)
    assert np.all(node > 0.0)
    np.testing.assert_allclose(0.5 * np.sum(node, axis=1), mean)


def test_log_frequency_module_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/log_frequency_moments.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
