"""Small-artifact evidence inventory for a prospective six-field diagnostic.

Does not open .dat or compute a field Gram, coefficient, map or response.
"""
import json
import argparse
import subprocess
from pathlib import Path
import numpy as np
from handoff.audit_tools.diagnose_x20_85889_energy import ROOT, RECEIVED, COMMIT, STEM, arrays, digest, verify_file
from handoff.audit_tools.diagnose_x20_85889_frequency import ownership


def bind_pair(manifest,state):
    """两次真实映射分别为previous->final与final->mapped_final。"""
    rows=manifest['history_rows'];e=manifest['endpoints'];hist=state['history']
    if manifest['new_map_count']!=16 or len(hist)!=16 or state['active_map'] is not None or rows!=hist[-2:]:
        raise ValueError('unsettled source history')
    if [r['iteration'] for r in hist]!=list(range(1,17)) or any(a['output_sha256']!=b['input_sha256'] for a,b in zip(hist,hist[1:])):
        raise ValueError('broken history')
    hashes=[e[k]['sha256'] for k in ['previous','final','mapped_final']]
    if hashes!=[rows[0]['input_sha256'],rows[0]['output_sha256'],rows[1]['output_sha256']] or rows[1]['input_sha256']!=hashes[1] or state['current_sha256']!=hashes[2]:
        raise ValueError('wrong map endpoints')
    if any(c['size_bytes']!=10099884032 for c in e.values()):raise ValueError('field size')
    return e


def bind_observation(rows, branch, endpoints):
    selected=[r for r in rows if r['branch']==branch]
    if len(selected)!=3 or {r['endpoint'] for r in selected}!=set(endpoints):
        raise ValueError('missing or repeated field observation')
    for row in selected:
        claim=endpoints[row['endpoint']]
        if row['claim']!=claim or row['symlink'] or row['size_bytes']!=claim['size_bytes']:
            raise ValueError('field stat mismatch')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'20261006-x20-85889-chord-source-review.json')
    target=parser.parse_args().output
    if target.exists():raise FileExistsError(target)
    ixp=ROOT/(STEM+'.json');ix=json.loads(ixp.read_text());claims={c['path']:c for c in ix['files']};checked=[]
    def load(rel,binary=False):
        p=RECEIVED/rel;verify_file(p,claims[rel]);checked.append(dict(path=rel,sha256=digest(p)))
        return arrays(p) if binary else json.loads(p.read_text())
    # 原清单通过前次能量审阅的工件SHA及final-review绑定，不重新执行旧全批审计。
    erp=Path('handoff/evidence/20261006-x20-85889-energy-review.json');er=json.loads(erp.read_text())
    ep=ROOT/'20261006-x20-85889-energy-diagnostic.json';verify_file(ep,next(c for c in er['artifacts'] if c['path']==str(ep)))
    energy=json.loads(ep.read_text());assert digest(ixp)==energy['archive_manifest_sha256']
    ap=Path(energy['source_final_audit']['path']);assert digest(ap)==energy['source_final_audit']['sha256']
    audit=json.loads(ap.read_text());assert audit['job_id']==85889 and audit['numerical_artifacts_complete'] and audit['scheduler_terminal_verified']
    observation=json.loads((ROOT/'20261006-x20-85889-chord-requirements-observation.json').read_text())
    fields={};configs=[];trials=[];schemas=set();map_receipts=0
    for branch in ['accelerated','historical']:
        state=load(branch+'/state.json');config=load(branch+'/config.json');trial=load(branch+'/trial_material.npz',True)
        assert digest(RECEIVED/branch/'config.json')==state['config_sha256']
        assert digest(RECEIVED/branch/'trial_material.npz')==state['trial_sha256']
        e=bind_pair(load(branch+'/endpoints-map16/manifest.json'),state);fields[branch]=e
        p=load(branch+'/pair16/feedback_protocol.json')
        for end in ['previous','final']:
            assert p['sources'][end+'_radiation']==e[end]
        bind_observation(observation['school']['fields'],branch,e)
        for n in [15,16]:
            rows=[load(branch+f'/map{n:04d}/block{i:02d}.json') for i in range(76)]
            ownership(rows);map_receipts+=len(rows)
            assert all(row['input_state_sha256']==state['history'][n-1]['input_sha256'] for row in rows)
            schemas.update(tuple(sorted(row)) for row in rows)
        configs.append(config);trials.append(trial)
    assert set(configs[0])==set(configs[1])
    different=[k for k in configs[0] if configs[0][k]!=configs[1][k]]
    assert set(different)=={'run','warm_seed','sources'}
    assert configs[0]['shape']==configs[1]['shape']==[9632,32,4096]
    assert set(trials[0])==set(trials[1])
    for k in trials[0]:np.testing.assert_array_equal(trials[0][k],trials[1][k])
    assert float(trials[0]['step_duration_s'])==889.419892762322 and int(trials[0]['phase_index'])==1367
    code=[]
    for rel in ['operations/common_precision_maps.py','operations/x20_85875_matched_feedback.py','diagnostics/interval_diagnostic.py','hpc/pipeline.py','operations/x20_history_operator.py','operations/x20_cross_seed_chord.py']:
        assert Path(rel).read_bytes()==subprocess.check_output(['git','show',COMMIT+':'+rel])
        code.append(dict(path=rel,sha256=digest(rel)))
    # 枚举完整归档的文件名，再核代表性NPZ schema；不假装仅凭文件名证明数学充分性。
    schemas_npz={}
    for rel in ['inputs/trial_material.npz','accelerated/pair16/previous_response.npz','accelerated/pair16/previous_energy_ledger.npz','accelerated/pair16/previous_feedback.npz']+[f'accelerated/pair16/feedback/previous/block00{s}.npz' for s in ['', '.legacy','.common']]:
        z=load(rel,True);schemas_npz[rel]={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in z.items()}
    out=dict(job_id=85889,scope='metadata/source requirements only; no dat content or new physics',fields=fields,school_observation=observation,
        source_manifest_sha256=digest(ixp),source_final_review_sha256=digest(ap),source_energy_review_sha256=digest(erp),
        checked_small_sources=checked,code=code,operator_config_differences=different,trial_all_arrays_bitwise_equal=True,map_receipts=map_receipts,
        map_receipt_schemas=[list(s) for s in sorted(schemas)],representative_npz_schemas=schemas_npz,
        archived_files=len(claims),archived_dat_files=[p for p in claims if p.endswith('.dat')],
        archived_gram_named_files=[p for p in claims if any(s in p.lower() for s in ['gram','chord','basis'])],
        missing_statistics=['cross-history intensity inner products','cross-history defect inner products','intensity-difference versus individual-defect inner products'],
        sufficiency='not reconstructible from existing maxima/boundary summaries and frequency-integrated feedback; six retained fields needed for proposed full-grid Gram',
        proposed_basis=['H_final-A_final','A_final-A_previous','A_mapped_final-A_final','H_final-H_previous','H_mapped_final-H_final'],
        large_field_sha_refreshed=False,large_field_stat_only=True,large_field_bytes_read=0,new_slurm=0,new_maps=0,new_feedback=0,new_material=0,
        accepted_outer_steps=20,baseline_replaced=False,reference_calibration_eligible=False,strict_error_bound=False)
    with target.open('x') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(target=str(target),small_sources=len(checked),map_receipts=map_receipts,config_differences=different,fields=6,archived_gram_named_files=out['archived_gram_named_files']),indent=2))

if __name__=='__main__':main()
