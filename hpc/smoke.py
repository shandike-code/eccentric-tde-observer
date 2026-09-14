"""Run explicit, data-independent physics controls from a clean checkout."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "test_atomic_continuum.py", "test_atomic_kinetics.py",
    "test_continuum_emission.py", "test_radiative_transfer_1d.py",
    "test_mixed_frame_ale.py", "test_mixed_frame_frequency.py",
    "test_mixed_frame_streaming.py", "test_annulus_bridge.py",
    "test_geometry.py", "test_observer_frame.py", "test_hpc_handoff.py",
)

if __name__ == "__main__":
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(map(str, (ROOT, ROOT / "src", ROOT / "scripts")))
    print("Data-independent smoke suite; NOT the full historical suite.", flush=True)
    raise SystemExit(subprocess.call(
        [sys.executable, "-m", "pytest", "-q", *[str(ROOT / "tests" / t) for t in TESTS]],
        cwd=ROOT, env=env,
    ))
