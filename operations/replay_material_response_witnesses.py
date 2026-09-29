"""Replay stored small feedback through unchanged material equations; no radiation maps."""
from pathlib import Path
from dataclasses import asdict
import json,os,resource,sys,time
import numpy as np
from operations import diagnose_boundary_seed_response as source
from operations.common_feedback_bridge import ledger,verify_response_ledger
ROOT,pipeline,reused,v,fresh=source.ROOT,source.pipeline,source.reused,source.v,source.fresh
CURRENT='outputs/hpc/step21-boundary-seed-response-20260929'
ACCEPTED='outputs/hpc/common-confirmation20-20260924'
RUN='outputs/hpc/step21-response-witness-replay-20260929'
TOL=1e-12


def comparison(actual,stored):
    a,b=np.asarray(actual),np.asarray(stored)
    if a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('nonfinite or incompatible replay arrays')
    error=float(np.max(np.abs(a-b)/np.maximum(1.,np.abs(b))))
    return dict(bitwise_equal=bool(np.array_equal(a,b)),maximum_scaled_error=error,passed=error<=TOL)


def require_source(audit):
    if (audit.get('job_id')!=80195 or not audit.get('diagnostic_windows_passed') or not audit.get('final_summary_present')
        or audit.get('accepted_outer_steps')!=20 or audit.get('new_material_steps')!=0
        or audit.get('original_all_16_pass') is not False or audit.get('baseline_replaced') is not False
        or audit.get('production_signal_reducer_reused') is not False):raise RuntimeError('independently audited diagnostic windows required')


def execute():
    pipeline.require_allocation(1)
    out=ROOT/RUN;out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,**kw))
    mark('preparing');start=time.monotonic()
    try:
        ev=ROOT/'handoff/evidence';audit=ev/'20260929-boundary-response-review.json';terminal=ev/'20260929-boundary-response-80195-terminal.json'
        require_source(pipeline.read(audit))
        groups=[('accepted',ROOT/ACCEPTED/'confirm2/common-feedback')]+[(f'{name}{n:02d}',ROOT/CURRENT/name/f'pair{n:02d}') for n in (2,10) for name in ('control','population')]
        claims=v.audited_inputs(ROOT/CURRENT,audit,terminal,80195,['declaration.json','summary.json','control/trial_material.npz','population/trial_material.npz']+
            [f'{name}/pair{n:02d}/{file}' for n in (2,10) for name in ('control','population') for file in
             ('feedback_protocol.json','previous_feedback.npz','final_feedback.npz','previous_response.npz','final_response.npz')])
        # accepted审计已有档案：以其归档清单逐项证明旧反馈，不依赖目录名称。
        old_audit=ev/'20260924-common-confirmation20-review.json';a=pipeline.read(old_audit);reused.verify([a['archive']])
        import tarfile
        with tarfile.open(ROOT/a['archive']['path']) as t:inv={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
        for file in ('feedback_protocol.json','previous_feedback.npz','final_feedback.npz','previous_response.npz','final_response.npz'):
            relative='confirm2/common-feedback/'+file;c=pipeline.claim(ROOT/ACCEPTED/relative)
            if any(c[k]!=inv[relative][k] for k in ('size_bytes','sha256')):raise RuntimeError('accepted witness changed')
            claims.append(c)
        claims += [pipeline.claim(old_audit),a['archive']]
        old_trial=v.load_arrays(ROOT/ACCEPTED/'confirm2/trial_material.npz');new_trial=v.load_arrays(ROOT/CURRENT/'control/trial_material.npz')
        physical=('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s')
        if any(not np.array_equal(old_trial[k],new_trial[k]) for k in physical):raise RuntimeError('x20 physical state differs')
        old_source=None
        for _,folder in groups:
            p=pipeline.read(folder/'feedback_protocol.json')
            if old_source is None:old_source=p['sources']['physical_old_time_level']
            if any(p['sources']['physical_old_time_level'][k]!=old_source[k] for k in ('sha256','size_bytes')):raise RuntimeError('physical old time layer changed')
            claims += [p['sources'][k] for k in ('trial_material','physical_old_time_level','base_residual')]
        claims=list({(c['path'],c['sha256']):c for c in claims}.values())
        code=fresh.code_claims()+[pipeline.claim(ROOT/'operations/replay_material_response_witnesses.sbatch'),pipeline.claim(ROOT/'handoff/protocols/material-response-witness-replay-v1.md')]
        reused.verify(claims+code)
        reused.immutable(out/'declaration.json',dict(source_job=80195,accepted_job=76727,claims=claims,code=code,maximum_endpoints=10,
            tolerance=TOL,maximum_maps=0,maximum_feedback_integrations=0,physical_state_x20_unchanged=True,
            baseline_replacement_authorized=False,automatic_promotion=False,accepted_outer_steps=20,environment=pipeline.environment()))
        reports={}
        for tag,folder in groups:
            p=pipeline.read(folder/'feedback_protocol.json');trial=v.load_arrays(ROOT/p['sources']['trial_material']['path']);old=v.load_arrays(ROOT/p['sources']['physical_old_time_level']['path'])
            for end in ('previous','final'):
                mark('replaying',witness=tag,end=end)
                fb=v.load_arrays(folder/f'{end}_feedback.npz');stored=v.load_arrays(folder/f'{end}_response.npz')
                response,residual,context=fresh.pair._material_response_residual(p,fb)
                fields=dict(residual=residual,temperature_k=response.temperature_k,hydrogen_fraction=response.hydrogen_fraction,
                    helium_fraction=response.helium_fraction,target_specific_material_energy_erg_g=response.target_specific_material_energy_erg_g)
                checks={k:comparison(val,stored[k]) for k,val in fields.items()}
                phase=int(trial['phase_index']);book=ledger(fb,trial['density_g_cm3'],float(trial['step_duration_s']),old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
                verify_response_ledger(book,response)
                row=dict(fields=checks,minimum_gas_erg_g=float(np.min(book['remaining'])),phase=phase,duration_s=float(context['duration']),
                    norms=asdict(fresh.bridge.encoded_residual_norms(residual,context['cell_mass'])),material_ode_recomputed=True)
                # 重放容差只检查重复计算一致性，不改变任何物理域或原收缩门。
                if not all(c['passed'] for c in checks.values()) or row['minimum_gas_erg_g']<=0:raise RuntimeError('material replay or positive gas gate failed: '+tag+'/'+end)
                reports[tag+'/'+end]=row
                np.savez(out/(tag+'-'+end+'-response.npz'),**fields)
                reused.immutable(out/(tag+'-'+end+'.json'),row)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('replay parent memory guard')
        reused.verify(claims+code)
        result=dict(status='complete_requires_review',all_replays_passed=True,endpoints=reports,peak_rss_bytes=peak,wall_s=time.monotonic()-start,
            accepted_outer_steps=20,new_material_steps=0,new_maps=0,new_feedback_integrations=0,material_ode_recomputed=True,
            baseline_replaced=False,old_r20_reinterpreted=False,physical_state_x20_unchanged=True)
        reused.immutable(out/'summary.json',result);mark('complete_requires_review');reused.archive(out,'complete')
    except Exception as exc:
        mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':execute()
