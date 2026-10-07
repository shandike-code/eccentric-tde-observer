"""New dyadic three-phase column fixture; no real scientific input."""
import json
import platform
import time
import numpy as np
from operations.x20_86304_preparation_column import full_column
from operations.x20_86304_preparation_inflate import PayloadLedger


def exercise():
    started = time.monotonic(); checkpoints = 0
    def check():
        nonlocal checkpoints
        checkpoints += 1
    material = dict(cell_mass_g_cm2=np.array([1 + (i % 4) / 4 for i in range(128)]),
        density_g_cm3=np.array([[1.] * 128, [2.] * 128, [4.] * 128]),
        temperature_k=np.full((3, 128), 8192.),
        hydrogen_fraction=np.tile([.75, .25], (3, 128, 1)),
        helium_fraction=np.tile([.5, .25, .25], (3, 128, 1)))
    ledger = PayloadLedger(); result = full_column(material, ledger, check)
    return dict(schema='86304-column-synthetic-v1', platform=platform.system(),
        elapsed_s=time.monotonic()-started, checkpoints=checkpoints,
        entries=ledger.entries, reserved_bytes=ledger.budget.used,
        arrays={k: dict(shape=list(a.shape), dtype=a.dtype.str, hex=a.tobytes().hex()) for k,a in result.items()},
        header_configuration_integrated=False, all_scientific_temporaries_metered=False,
        whole_lifecycle_guard_verified=False, production_authorized=False)


if __name__ == '__main__': print(json.dumps(exercise(), sort_keys=True))
