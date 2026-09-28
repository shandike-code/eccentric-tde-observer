"""School-side small-input preflight; never opens the 9.41 GiB radiation seed."""
import argparse
from pathlib import Path
import numpy as np
from operations import remeasure_step21_directions as r


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    out=a.output.resolve();out.relative_to(r.ROOT/'outputs');out.mkdir(exist_ok=False)
    root=r.ROOT/r.SOURCE;read=r.pipeline.read;ret=read(root/'control/endpoints-map16/manifest.json')
    seed=r.source_seed(read(root/'summary.json'),read(r.ROOT/'handoff/evidence/20260928-stationarity-complete-review.json'),read(root/'control/state.json'),ret)
    zero=read(root/'control/pair16/feedback_protocol.json')
    finite=read(r.ROOT/r.station.original.SOURCE/'thermal/pair03/feedback_protocol.json')
    sources=zero['sources'];base=r.fresh.load_arrays(r.ROOT/sources['outer_base_material']['path'])
    residual=np.load(r.ROOT/sources['base_residual']['path'],allow_pickle=False)
    old=r.fresh.load_arrays(r.ROOT/sources['physical_old_time_level']['path'])
    checks={}
    for name in r.NAMES:
        path=out/(name+'-trial.npz');trial=r.directions.make_trial(base,residual,old,name);np.savez(path,**trial)
        r.fixed.exact_trial(r.fresh.load_arrays(path),base,residual,old,name)
        p=r.make_protocol(finite,zero,out/name,ret,r.pipeline.claim(path),r.pipeline.claim(root/'control/endpoints-map16/manifest.json'),r.pipeline.claim(root/'declaration.json'),name)
        r.fixed.native_identity(p)
        if p['acceptance_gates']!=zero['acceptance_gates'] or p['formal_state_gates']!=zero['formal_state_gates']:
            raise RuntimeError('original gates changed')
        checks[name]=dict(exact_trial=True,native_identity=True,original_gates_unchanged=True,
            zero_authorization=p['authorization'].get('zero_displacement_control',False),trial=r.pipeline.claim(path))
    report=dict(source_job=78594,seed=seed,cases=checks,large_seed_bytes_verified=False,physics_map_run=False)
    r.pipeline.write_json(out/'preflight.json',report);print(report)


if __name__=='__main__':main()
