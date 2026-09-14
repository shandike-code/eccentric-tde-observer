from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)


def test_hydrogen_rate_monitor_preserves_count_thresholds_and_positive_widths():
    grid = hydrogen_photoionization_monitor_group_grid(0.1, 5000.0, 2408, 0.25)
    assert grid.group_edge_ev.size == 2409
    assert np.sum(grid.segment_group_count) == 2408
    assert np.all(np.diff(grid.group_edge_ev) > 0.0)
    for threshold in (13.60, 24.59, 54.42):
        assert np.count_nonzero(grid.group_edge_ev == threshold) == 1


def test_hydrogen_rate_focus_moves_groups_to_the_hydrogen_edge_segment():
    weak = hydrogen_photoionization_monitor_group_grid(0.1, 5000.0, 2408, 0.25)
    strong = hydrogen_photoionization_monitor_group_grid(0.1, 5000.0, 2408, 0.75)
    assert strong.segment_group_count[1] > weak.segment_group_count[1]
    assert strong.segment_group_count[0] < weak.segment_group_count[0]
    assert strong.segment_group_count[-1] < weak.segment_group_count[-1]


def test_hydrogen_rate_monitor_edge_convergence_is_below_gate_scale():
    coarse = hydrogen_photoionization_monitor_group_grid(
        0.1, 5000.0, 2408, 0.75, integration_panels_per_segment=32768
    )
    fine = hydrogen_photoionization_monitor_group_grid(
        0.1, 5000.0, 2408, 0.75, integration_panels_per_segment=65536
    )
    relative = np.max(
        np.abs(coarse.group_edge_ev - fine.group_edge_ev) / fine.group_edge_ev
    )
    assert relative < 5.0e-9
    assert np.array_equal(coarse.segment_group_count, fine.segment_group_count)


def test_goal_oriented_frequency_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/goal_oriented_frequency.py")
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
