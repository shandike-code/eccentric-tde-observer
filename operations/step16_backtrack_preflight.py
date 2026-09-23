"""Small allocation-only exact-decode test on original Linux material bytes."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
import pipeline
from operations import sixteenth_step_backtrack_probe as probe
from operations.second_outer_step import rebase_trial, validate_trial
from operations.prepare_encoded_backtrack import load_arrays


def main():
    # One small Python process inside the allocated four CPUs, not four
    # radiation workers (which would require >26 GiB under the original guard).
    pipeline.require_allocation(1)
    folder=ROOT/probe.CONFIRMATION/'confirm4';rd=folder/'feedback-round1'
    proto=pipeline.read(rd/'feedback_protocol.json');summary=pipeline.read(rd/'feedback_summary.json')
    # Canonical feedback protocols snapshot inputs under round/inputs; the
    # run-root trial is a byte-identical copy, not the same path claim.
    paths=[ROOT/proto['sources']['trial_material']['path'],rd/'material_residual.npy',
           ROOT/proto['sources']['physical_old_time_level']['path'],rd/'feedback_protocol.json']
    claims=[pipeline.claim(p) for p in paths]
    assert claims[0]==proto['sources']['trial_material']
    root_trial=pipeline.claim(folder/'trial_material.npz')
    assert all(root_trial[k]==claims[0][k] for k in ('size_bytes','sha256'))
    assert claims[1]['sha256']==summary['encoded_residual_sha256']
    assert claims[2]==proto['sources']['physical_old_time_level']
    assert claims[3]['sha256']==summary['protocol_sha256']
    accepted=load_arrays(paths[0]);r=np.load(paths[1],allow_pickle=False)
    base=rebase_trial(accepted,r,load_arrays(paths[2]))
    with probe.amplitude_contract():
        for alpha in probe.ALPHAS.values():
            trial=probe.batch.make_trial(base,r,alpha)
            validate_trial(trial,base,r)
    result={'native_exact_rebase':True,'alphas':probe.ALPHAS,'sources':claims,
        'environment':pipeline.environment(),'new_radiation_maps':0,
        'physical_response_replayed':False,'formal_trial_accepted':False}
    dest=ROOT/probe.PREFLIGHT;dest.parent.mkdir(parents=True,exist_ok=True)
    probe.reused.immutable(dest,result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
