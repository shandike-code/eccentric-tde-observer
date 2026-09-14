import inspect
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eccentric_tde_observer import (
    ImplicitALESlabStep,
    solve_implicit_ale_slab_step,
)
from scripts.phase7b4s_implicit_ale_radiation import (
    analytic_control_rows,
    centred_full_column_trajectory,
    run_all,
)


def test_centred_full_trajectory_preserves_lagrangian_mass_and_mirror():
    phase_points = 3
    depth_points = 4
    cell_mass = np.array([0.1, 0.2, 0.3, 0.4])
    density = np.array(
        [
            [1.0, 2.0, 3.0, 4.0],
            [2.0, 4.0, 6.0, 8.0],
            [0.5, 1.0, 1.5, 2.0],
        ]
    )
    temperature = 1.0e4 + np.arange(phase_points * depth_points).reshape(
        phase_points, depth_points
    )
    hydrogen = np.broadcast_to(
        np.array([0.2, 0.8]), (phase_points, depth_points, 2)
    ).copy()
    helium = np.broadcast_to(
        np.array([0.1, 0.3, 0.6]), (phase_points, depth_points, 3)
    ).copy()
    full = centred_full_column_trajectory(
        {
            "cell_mass_g_cm2": cell_mass,
            "density_g_cm3": density,
            "temperature_k": temperature,
            "hydrogen_fraction": hydrogen,
            "helium_fraction": helium,
        }
    )
    assert full["edges_cm"].shape == (phase_points, 2 * depth_points + 1)
    np.testing.assert_allclose(full["cell_width_cm"], full["cell_width_cm"][:, ::-1])
    np.testing.assert_allclose(full["density_g_cm3"], full["density_g_cm3"][:, ::-1])
    recovered = full["density_g_cm3"] * full["cell_width_cm"]
    expected_mass = np.concatenate((cell_mass, cell_mass[::-1]))
    np.testing.assert_allclose(
        recovered, np.broadcast_to(expected_mass, recovered.shape)
    )
    np.testing.assert_allclose(full["edges_cm"][:, depth_points], 0.0, atol=2.0e-16)


def test_phase7b4s_analytic_controls_and_convergence_all_pass():
    rows = analytic_control_rows()
    assert len(rows) == 9
    assert all(bool(row["passed"]) for row in rows)
    advection = [
        float(row["error"])
        for row in rows
        if row["control"] == "periodic vacuum advection"
    ]
    frozen = [
        float(row["error"])
        for row in rows
        if row["control"] == "frozen formal recovery"
    ]
    assert advection[2] < advection[1] < advection[0]
    assert frozen[2] < frozen[1] < frozen[0]


def test_phase7b4s_public_api_and_scope_do_not_hide_open_physics():
    assert ImplicitALESlabStep.__name__ == "ImplicitALESlabStep"
    assert callable(solve_implicit_ale_slab_step)
    source = inspect.getsource(run_all)
    assert '"full_dynamic_nonlocal_spectrum_authorized": False' in source
    assert "velocity_frequency_angle_gate_required" in source
    combined = inspect.getsource(solve_implicit_ale_slab_step) + source
    assert "nan_to_num" not in combined
    assert "np.clip" not in combined
