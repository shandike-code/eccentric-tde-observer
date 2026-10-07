"""Tiny synthetic-only round trip; never accepts scientific source paths."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import time
import numpy as np
from operations import x20_86304_preparation_inputs as p
from handoff.audit_tools import review_x20_86304_preparation_inputs as review


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True)
    args = parser.parse_args(); out = Path(args.out); out.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    arrays = dict(encoded_state=np.arange(12, dtype='<f8'), base_encoded_state=np.arange(12, dtype='<f8'),
                  finite_direction=np.zeros(12), base_residual=np.zeros(12), relaxation=np.array(0.),
                  density_g_cm3=np.array([1., 2., 3.]), temperature_k=np.array([4., 5., 6.]),
                  hydrogen_fraction=np.array([[.25, .75]]*3), helium_fraction=np.array([[.25, .25, .5]]*3),
                  specific_material_energy_erg_g=np.array([8., 9., 10.]))
    memory = io.BytesIO(); np.savez_compressed(memory, **arrays); raw = memory.getvalue()
    (out/'synthetic.npz').write_bytes(raw)
    source = dict(path='synthetic.npz', size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    destination = dict(source, path='trial/trial.npz')
    plan = p.staging_plan([destination], {destination['path']: source})
    fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
    try: staging = p.stage_small_sources(fd, fd, 'staged', plan, p.Budget(1024**2))
    finally: os.close(fd)
    evidence = p.expected_fingerprints(raw, raw, p.Budget(p.STAGE_LIMIT), p.Budget(p.READ_LIMIT))
    oracle = review.review_synthetic(raw, evidence)
    try: p.native_configuration()
    except RuntimeError as error: rejection = str(error)
    else: raise AssertionError('unfinished native path enabled')
    metadata = dict(synthetic_only=True, source_bytes=len(raw), staging=staging,
                    wall_s=time.monotonic()-started,
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
                    native_rejection=rejection, actual_source_manifest_prepared=False,
                    process_guard_verified=False, physical_old_r20_verified=False,
                    numpy=np.__version__, platform=sys.platform)
    for name, value in [('fingerprints.json', evidence), ('oracle.json', oracle), ('metadata.json', metadata)]:
        with (out/name).open('x') as f: json.dump(value, f, indent=2, allow_nan=False)
    manifest = []
    for name in ('synthetic.npz', 'fingerprints.json', 'oracle.json', 'metadata.json'):
        data = (out/name).read_bytes()
        manifest.append(dict(path=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    with (out/'receipt.json').open('x') as f: json.dump(manifest, f, indent=2)
    print(json.dumps(metadata, allow_nan=False))


if __name__ == '__main__': main()
