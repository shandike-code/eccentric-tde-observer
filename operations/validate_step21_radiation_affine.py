"""Three true affine-map checks, then conditional fixed-trial common feedback."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
import os
import resource
import shutil
import signal
import sys
import tarfile
import time
import numpy as np
from operations import common_step21_direction_precision as fixed
from operations.scan_step21_radiation_history import StreamState,retained_basis
from operations.validate_history_extrapolation import affine_chunk,write_candidate,validation_checks

fresh=fixed.fresh;pipeline=fresh.pipeline;reused=fresh.reused;ROOT=fresh.ROOT
pair=fresh.pair;driver=fixed.driver;load_arrays=fresh.load_arrays
SCAN='outputs/hpc/step21-radiation-history-scan-20260925'
SOURCE='outputs/hpc/common-step21-direction-precision-20260925'
NAMES=('control','thermal','population')
LIMITS={k:3 for k in NAMES}


def fraction(prediction):
    if prediction['actual_map_performed'] is not False or prediction['actual_candidate_residual'] is not None:
        raise ValueError('scan must not masquerade as measured validation')
    if not prediction['algebraic_feasibility'] or not all(prediction['algebraic_gates'].values()):raise ValueError('scan not eligible')
    v=prediction['direction'];s=float(v['selected_forward_fraction'])
    if not np.isfinite(s) or not 1<s<=96 or s>=v['exact_positive_upper'] or abs(1-s)+abs(s)>=192:
        raise ValueError('invalid global coefficient')
    return s


def ratio(a,b):
    if b==0:
        if a==0:return 0.
        raise ArithmeticError('nonzero change with zero scale')
    return a/b


def compare_fields(paths,shape,s,chunk=16):
    """Compare all cells of the measured map with the affine predicted map."""
    # 输入依次为旧b、旧c、新候选q、真实T(q)。正性只检查，不作任何修补。
    states=[StreamState(p,shape) for p in paths];rows=[]
    err=scale=change=actual_scale=0.;err2=map2=change2=0.
    for start in range(0,shape[0],chunk):
        reused.checkpoint();stop=min(start+chunk,shape[0])
        b,c,q,actual=[state[start:stop] for state in states]
        predicted=affine_chunk(b,c,s)
        with np.errstate(invalid='raise',over='raise',divide='raise'):
            delta=actual-predicted;res=actual-q
            e=float(np.max(np.abs(delta)));z=max(float(np.max(actual)),float(np.max(predicted)))
            r=float(np.max(np.abs(res)))
            err=max(err,e);scale=max(scale,z);change=max(change,r)
            actual_scale=max(actual_scale,float(np.max(actual)),float(np.max(q)))
            err2+=float(np.sum(delta*delta));map2+=float(np.sum(actual*actual));change2+=float(np.sum(res*res))
        rows.append({'start':start,'stop':stop,'error_max':e,'field_scale':z,'actual_change_max':r,
                     'error_relative_to_local_field':ratio(e,z),'actual_local_residual':ratio(r,max(z,float(np.max(q))))})
    return {'max_error_over_field':ratio(err,scale),'max_error_over_actual_change':ratio(err,change),
            'l2_error_over_actual_field':np.sqrt(ratio(err2,map2)),
            'l2_error_over_actual_change':np.sqrt(ratio(err2,change2)),
            'actual_global_residual':ratio(change,actual_scale),
            'slabs':rows,'full_intensity_prediction_error_evaluated':True}


def measured_checks(row,latest,fields):
    checks=validation_checks(row,latest)
    checks.update(strict_inner_pass=0<=row['residual']<1e-4,
                  full_field_prediction_error_small=0<=fields['max_error_over_field']<1e-7,
                  prediction_error_below_tenth_actual_change=0<=fields['max_error_over_actual_change']<.1)
    return checks


def conditional_sequence(validate,evaluate):
    """Finish all three map checks; a bad control forbids all paired comparisons."""
    valid={name:bool(validate(name)) for name in NAMES}
    if not valid['control']:return 'control_map_not_validated'
    if evaluate('control')!='baseline_stable':return 'control_feedback_not_stable'
    for name in NAMES[1:]:
        if valid[name] and evaluate(name)=='physical_domain_rejected':return name+'_physical_domain_rejected'
    return 'bounded_affine_diagnostic_complete_requires_review'


def prepare(out):
    review_path=ROOT/'handoff/evidence/20260925-step21-radiation-scan-review.json';review=pipeline.read(review_path)
    terminal_path=ROOT/'handoff/evidence/20260925-step21-radiation-scan-76946-terminal.json';terminal=pipeline.read(terminal_path)
    if terminal['job_id']!=76946 or terminal['state']!='COMPLETED' or review['accepted_outer_steps']!=20 or review['new_maps']!=0:raise RuntimeError('scan audit unavailable')
    reused.verify([review['archive']])
    with tarfile.open(ROOT/review['archive']['path']) as t:
        inventory={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    claims=[pipeline.claim(review_path),pipeline.claim(terminal_path)]
    for file in ('declaration.json','prediction.json','status.json'):
        c=pipeline.claim(ROOT/SCAN/file)
        if any(c[k]!=inventory[file][k] for k in ('size_bytes','sha256')):raise RuntimeError('scan differs from audited archive')
        claims.append(c)
    scan=pipeline.read(ROOT/SCAN/'declaration.json');prediction=pipeline.read(ROOT/SCAN/'prediction.json')
    reused.verify(scan['claims']+scan['code']);claims+=scan['claims']+scan['code']
    prior_audit_path=ROOT/'handoff/evidence/20260925-common-step21-direction-precision-review.json';prior_audit=pipeline.read(prior_audit_path)
    reused.verify([prior_audit['archive']]);claims.append(pipeline.claim(prior_audit_path))
    with tarfile.open(ROOT/prior_audit['archive']['path']) as t:
        prior_inventory={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    rp=ROOT/SOURCE/'population/pair08/feedback_protocol.json';rc=pipeline.claim(rp)
    if any(rc[k]!=prior_inventory['population/pair08/feedback_protocol.json'][k] for k in ('size_bytes','sha256')):raise RuntimeError('reference protocol replaced')
    reference=pipeline.read(rp);claims.append(rc);sources=reference['sources']
    base=load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path']);old=load_arrays(ROOT/sources['physical_old_time_level']['path'])
    fixed.validate_zero(base,base,r,old);fixed.validate_base_against_accepted(base,load_arrays(ROOT/fixed.BASE/'trial_material.npz'))
    accepted=ROOT/'handoff/evidence/20260924-accepted-step20.json';acceptance=pipeline.read(accepted)
    fixed.validate_acceptance(acceptance,pipeline.read(ROOT/'handoff/evidence/20260924-confirmation20-76727-terminal.json'));reused.verify(acceptance['claims'])
    if not np.array_equal(r,load_arrays(ROOT/fixed.BASE/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    claims+=[pipeline.claim(accepted)]+[sources[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]
    cases={};inputs=out/'inputs';inputs.mkdir()
    for name in NAMES:
        state=pipeline.read(ROOT/SOURCE/name/'state.json');ret=pipeline.read(ROOT/SOURCE/name/'endpoints-map08/manifest.json')
        if retained_basis(state,ret)!=scan['cases'][name]['basis']:raise RuntimeError('basis changed')
        trial=load_arrays(ROOT/SOURCE/name/'trial_material.npz');fixed.exact_trial(trial,base,r,old,name)
        folder=inputs/name;folder.mkdir();shutil.copyfile(ROOT/SOURCE/name/'trial_material.npz',folder/'trial_material.npz')
        fixed.same_trial(load_arrays(folder/'trial_material.npz'),trial)
        cfg=pipeline.read(ROOT/SOURCE/name/'config.json')
        if pipeline.sha256(ROOT/SOURCE/name/'config.json')!=state['config_sha256']:raise RuntimeError('source config changed')
        reused.verify(cfg['sources']);pipeline.write_json(folder/'config.json',cfg)
        cases[name]={'trial':pipeline.claim(folder/'trial_material.npz'),'config':pipeline.claim(folder/'config.json')}
        check=deepcopy(reference);check['sources']['trial_material']=cases[name]['trial'];fixed.native_identity(check)
        claims+=list(cases[name].values());fraction(prediction['histories'][name])
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/validate_step21_radiation_affine.sbatch','tests/test_validate_step21_radiation_affine.py','handoff/protocols/step21-radiation-affine-validation-v1.md')]
    plan={'cases':cases,'claims':claims,'code':code,'basis':scan['cases'],'prediction':prediction['histories'],
          'limits':LIMITS,'maximum_maps':9,'maximum_feedback_pairs':3,'accepted_outer_steps':20,
          'automatic_promotion':False,'physical_dt_changed':False,'environment':pipeline.environment()}
    reused.immutable(out/'declaration.json',plan);return plan,reference,base,r,old


def map_once(folder,cfg,state):
    reused.checkpoint()
    if len(state['history'])>=3:raise RuntimeError('three-map hard limit')
    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
    if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('mapping resource/fault')
    records=list((folder/f"map{len(state['history']):04d}").glob('block*.process-*.json'))
    if len(records)!=76:raise RuntimeError('missing/ambiguous process receipts')
    for path in records:
        q=pipeline.read(path)
        if q['returncode']!=0 or not q['memory_guard_passed'] or q['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('native process resource guard')


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<24*pipeline.STATE_BYTES:raise RuntimeError('insufficient checkpoint space')
        plan,reference,base,r,old=prepare(out);reused.LIMITS=LIMITS.copy();children={};validations={};reports={};baseline={}
        def validate(name):
            reused.checkpoint();mark('writing_candidate',case=name)
            pred=plan['prediction'][name];s=fraction(pred);basis=plan['basis'][name]['basis']
            seedpath=out/(name+'-affine-candidate.dat')
            minimum=write_candidate([ROOT/c['path'] for c in basis[:2]],seedpath,s,int(np.prod(pipeline.SHAPE)),16*pipeline.SHAPE[1]*pipeline.SHAPE[2])
            reused.verify(basis);seed=pipeline.claim(seedpath)
            folder,cfg,state=reused.child(out,name,name,seed,plan);children[name]=(folder,cfg,state)
            fixed.same_trial(load_arrays(folder/'trial_material.npz'),load_arrays(ROOT/plan['cases'][name]['trial']['path']))
            for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
            mark('validating_map',case=name);map_once(folder,cfg,state);row=state['history'][0]
            if row['input_sha256']!=seed['sha256']:raise RuntimeError('candidate not mapped')
            reused.checkpoint();fields=compare_fields([ROOT/basis[1]['path'],ROOT/basis[2]['path'],seedpath,ROOT/row['output_path']],pipeline.SHAPE,s)
            np.testing.assert_allclose(fields['actual_global_residual'],row['residual'],rtol=1e-12,atol=0)
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            checks=measured_checks(row,pred['latest_actual_residual'],fields)
            result={'case':name,'candidate':seed,'minimum_candidate':minimum,'fraction':s,'actual_map':row,
                    'field_comparison':fields,'checks':checks,'validated':all(checks.values()),
                    'parent_peak_rss_bytes':peak,'accepted_material_step':False}
            validations[name]=result;reused.immutable(folder/'validation.json',result);reused.verify(basis)
            reused.archive(out,name+'-validation');return result['validated']
        def evaluate(name):
            folder,cfg,state=children[name];mark('precision_maps',case=name)
            map_once(folder,cfg,state);map_once(folder,cfg,state)
            if not pipeline.pair_ready(state['history'],1e-4):
                reports[name]={'feedback_evaluated':False,'inner_pair_ready':False};return 'inner_pair_not_ready'
            fixed.retain_pair(folder,state);ret=pipeline.read(folder/'endpoints-map03/manifest.json');rd=folder/'pair03';rd.mkdir()
            p=fresh.new_protocol(reference,rd,ret['endpoints'],ret['history_rows'],16)
            p['sources']['trial_material']=pipeline.claim(folder/'trial_material.npz');p['sources']['retained_manifest']=pipeline.claim(folder/'endpoints-map03/manifest.json')
            p['sources']['affine_validation']=pipeline.claim(folder/'validation.json')
            p['numerical_backtracking']={'alpha':fixed.ALPHAS[name],'fixed_base_accepted_index':20,'direction_family':name,'diagnostic_only':True,'physical_time_advanced':False}
            p['outer_iteration'].update(direction_is_latest_confirmed_response=name=='control',diagnostic_only=True)
            fixed.set_authorization(p,name);fixed.exact_trial(load_arrays(folder/'trial_material.npz'),base,r,old,name);fixed.native_identity(p)
            fresh.attach_code(p);p['common_code_claims']+=plan['code'];path=rd/'feedback_protocol.json';reused.immutable(path,p)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',case=name)
            with reused.feedback_stop_guard():
                if name=='control':stable=fixed.zero_feedback(rd,p,path,state['history'][-2:]);result=pipeline.read(rd/'baseline_summary.json')
                else:result=pair.run_pair(path,pipeline.sha256(path));fixed.verify_step21_pair(rd,p,result)
            reused.verify(list(p['sources'].values())+p['common_code_claims'])
            report={'feedback_evaluated':True,'original_gates':result['gate_checks'],'physical_response_failures':result.get('material_response_failures',{}),'promoted':False,'pair_supported':False}
            if not report['physical_response_failures']:
                vectors={e:load_arrays(rd/(e+'_response.npz'))['residual'] for e in ('previous','final')}
                if name=='control':
                    baseline.update(vectors);report['baseline_stable']=stable
                    report['fresh_control_minus_r20_norms']=asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2']))
                else:
                    report['fresh_baseline_comparison']=fixed.cross_comparisons(vectors,baseline,old['cell_mass_g_cm2'])
                    report['pair_supported']=fixed.all_pair_gates(result) and report['fresh_baseline_comparison']['passed']
            reports[name]=report;reused.immutable(rd/'decision.json',report);reused.archive(out,name+'-feedback')
            if report['physical_response_failures']:return 'physical_domain_rejected'
            return ('baseline_stable' if stable else 'baseline_unstable') if name=='control' else 'diagnostic_complete'
        with fixed.relay_dispatch():terminal=conditional_sequence(validate,evaluate)
        reused.verify(plan['claims']+plan['code'])
        reused.immutable(out/'summary.json',{'status':terminal,'validations':validations,'cases':reports,'accepted_outer_steps':20,'new_material_steps':0})
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
