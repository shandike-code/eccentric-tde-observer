"""Check real small inputs/native identity; large seed hashes stay in Slurm."""
import argparse
from pathlib import Path
import numpy as np
from operations import confirm_late_direction_windows as late


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.relative_to(late.ROOT/'outputs');out.mkdir(exist_ok=False)
    root=late.ROOT/late.SOURCE;read=late.pipeline.read
    states={k:read(root/k/'state.json') for k in late.NAMES}
    retained={k:read(root/k/'endpoints-map16/manifest.json') for k in late.NAMES}
    seeds=late.validate_source(read(root/'summary.json'),read(late.ROOT/late.AUDIT),states,retained)
    zero=read(root/'control/pair16/feedback_protocol.json');finite=read(root/'thermal/pair16/feedback_protocol.json')
    sources=zero['sources'];base=late.fresh.load_arrays(late.ROOT/sources['outer_base_material']['path'])
    residual=np.load(late.ROOT/sources['base_residual']['path'],allow_pickle=False)
    old=late.fresh.load_arrays(late.ROOT/sources['physical_old_time_level']['path'])
    cases={}
    for name in late.NAMES:
        trial_path=root/name/'trial_material.npz';trial=late.fresh.load_arrays(trial_path)
        late.fixed.exact_trial(trial,base,residual,old,name)
        seed=seeds[name];assert (late.ROOT/seed['path']).stat().st_size==seed['size_bytes']==late.pipeline.STATE_BYTES
        protocol=late.prior.make_protocol(finite,zero,out/name,retained[name],late.pipeline.claim(trial_path),
            late.pipeline.claim(root/name/'endpoints-map16/manifest.json'),late.pipeline.claim(root/'declaration.json'),name)
        late.fixed.native_identity(protocol)
        if protocol['acceptance_gates']!=zero['acceptance_gates'] or protocol['formal_state_gates']!=zero['formal_state_gates']:
            raise RuntimeError('original gates changed')
        if late.pipeline.sha256(root/name/'config.json')!=states[name]['config_sha256']:raise RuntimeError('config changed')
        cases[name]=dict(exact_trial=True,native_identity=True,original_gates_unchanged=True,
            own_seed=seed,seed_exists_and_size_verified=True,large_seed_sha_verified=False,
            trial=late.pipeline.claim(trial_path))
    report=dict(source_job=78950,cases=cases,physics_map_run=False,large_seed_hashes_deferred_to_batch=True)
    late.pipeline.write_json(out/'preflight.json',report);print(report)


if __name__=='__main__':main()
