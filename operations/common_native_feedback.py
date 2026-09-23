"""Versioned complete H/He feedback using an independent common-window lab source.

The unchanged native atomic worker runs first. Its raw output remains on disk;
only the new protocol's formal field is replaced by the independent lab integral.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import numpy as np
from operations import common_feedback_bridge as bridge
from operations.constrained_hybrid_batch import relay_dispatch
from operations.common_frequency_four_force import common_frequency_four_force
pipeline=bridge.pipeline;pair=bridge.pair;native=bridge.native;reused=bridge.reused;ROOT=bridge.ROOT
load_arrays=bridge.load_arrays
MAPS='outputs/hpc/common-precision-maps-20260923'
REFERENCE='outputs/hpc/common-feedback-bridge-v2-20260923'
PILOT='outputs/hpc/common-native-pilot-20260923'


def code_claims():
    # 父进程冻结完整实现集合；worker检查本入口和直接包装层，模板核仍走原依赖检查。
    return [pipeline.claim(p) for d in ('src','scripts','hpc','operations','diagnostics')
            for p in sorted((ROOT/d).rglob('*.py'))]+[pipeline.claim(ROOT/p) for p in (
            'operations/common_native_feedback.sbatch','operations/common_native_pilot.sbatch',
            'tests/test_common_native_feedback.py','handoff/protocols/common-native-feedback-v1.md')]


def new_protocol(reference,out,endpoints,history,workers):
    p=deepcopy(reference);cfg=p['configuration']
    for k in ('reuse_completed_feedback_manifests','feedback_origin_protocol_sha256'):cfg.pop(k,None)
    for k in ('previous_feedback_manifest','final_feedback_manifest','previous_feedback_artifact','final_feedback_artifact','common_origin_protocol'):p['sources'].pop(k,None)
    p['authorization'].pop('reuse_only_after_bytewise_reproduction_audit',None)
    p['sources']['legacy_adapter']=deepcopy(p['sources']['adapter_runner'])
    p['sources']['adapter_runner']=pipeline.claim(Path(__file__))
    p['phase']='common-window-native-complete-feedback-v1';p['classification']='fixed trial feedback; not a promoted outer step'
    p['resource_change']='Actual cumulative worker-batch time below 900 s per new state; no historical bridge cost reuse.'
    cfg['maximum_concurrent_processes']=workers
    paths={'summary_path':'feedback_summary.json','figure_path':'feedback.png','target_material_output':'target_material.npz',
           'encoded_residual_output':'material_residual.npy','feedback_work_directory':'feedback',
           'previous_feedback_output':'previous_feedback.npz','final_feedback_output':'final_feedback.npz'}
    for k,v in paths.items():cfg[k]=str((out/v).relative_to(ROOT))
    if len(history)!=2:raise ValueError('two consecutive history rows required')
    for label,row in zip(('previous','final'),history):
        c=endpoints[label]
        if c['sha256']!=row['input_sha256']:raise RuntimeError('retained state differs from evaluated input')
        p['sources'][label+'_radiation']=c
        for key,field in (('global_original_operator_residual','residual'),('boundary_spectrum_l1','boundary_l1'),('boundary_bolometric_fraction','boundary_bolometric')):
            cfg[label+'_'+key]=row[field]
    if history[0]['output_sha256']!=history[1]['input_sha256'] or history[1]['iteration']!=history[0]['iteration']+1:
        raise RuntimeError('pair is not consecutive')
    if p['formal_state_gates']!=pair._formal_state_gates():raise RuntimeError('strict common bridge thresholds changed')
    pair._require_exact_acceptance_gates({'gates':p['acceptance_gates'],'authorization':p['authorization']})
    return p


def common_block(protocol,label,index):
    template=pair._validate_worker_template_sources(protocol)
    adapted=pair.adapt_phase7b7j_worker_protocol(protocol,template,label)
    mod=native.phase7b7f;context=mod.phase7b7e.phase7b5x._context(adapted)
    updated=native.phase7b7i._second_full_material(adapted)
    mapped=np.memmap(ROOT/adapted['sources']['mapped_radiation_state']['path'],mode='r',dtype=np.float64,shape=native.phase7b7i._shape(adapted))
    block,fields=native._fill_global_halo(adapted,context,updated,mapped,index)
    local=block.local_stencil
    comoving=mod.comoving_group_radiation(fields['outer'],local.outer_lab_edge_hz,local.comoving_collision_edge_hz,context['mu'],context['weight'],context['beta'])
    edges=context['stencil'].active_lab_edge_hz
    # 固定共动核心频域，lab射线积分由已验证的独立四力算子执行；不输入原子加热。
    return common_frequency_four_force(fields['outer'],local.outer_lab_edge_hz,local.comoving_collision_edge_hz,
        fields['true_absorption']+fields['scattering'],fields['thermal_emissivity']+fields['scattering']*comoving.mean_intensity_density,
        context['mu'],context['weight'],context['beta'],(float(edges[block.core_group_start]),float(edges[block.core_group_stop])))


def worker(protocol_path,sha,label,index,partial,report):
    started=time.monotonic();p=pair.load_frozen_pair_protocol(protocol_path,sha,validate_sources=False)
    reused.verify(p['common_worker_claims'])
    legacy=partial.with_suffix('.legacy.npz');legacy_report=report.with_suffix('.legacy.json');common_path=partial.with_suffix('.common.npz')
    if any(x.exists() for x in (partial,report,legacy,legacy_report,common_path)):raise FileExistsError('worker output already exists')
    pair.run_worker_adapter(protocol_path,sha,label,index,legacy,legacy_report)
    old=load_arrays(legacy);row=pipeline.read(legacy_report)
    if row['block_index']!=index or row['partial_sha256']!=pipeline.sha256(legacy):raise RuntimeError('native worker identity changed')
    common=common_block(p,label,index);new=bridge.replace_partial(old,common['common_formal_erg_s_cm3'])
    for k in old:
        if k!=bridge.FORMAL and not np.array_equal(old[k],new[k]):raise RuntimeError('atomic/direct field changed')
    np.savez(common_path,**common);np.savez(partial,**new)
    peak=bridge.ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
    if peak>=6144:raise RuntimeError('native common worker memory gate failed')
    row.update(partial_path=str(partial.relative_to(ROOT)),partial_sha256=pipeline.sha256(partial),
        runtime_s=time.monotonic()-started,peak_process_rss_mib=peak,legacy_partial=pipeline.claim(legacy),
        legacy_report=pipeline.claim(legacy_report),common_arrays=pipeline.claim(common_path),
        nonformal_fields_bitwise_unchanged=True,common_source_independent=True)
    pipeline.write_json(report,row)


def attach_code(p):
    claims=code_claims()
    p['common_code_claims']=claims
    selected=('operations/common_native_feedback.py','operations/common_frequency_four_force.py','operations/common_feedback_bridge.py','scripts/phase7b9_formal_feedback_pair_adapter.py')
    p['common_worker_claims']=[c for c in claims if c['path'] in selected]
    if len(p['common_worker_claims'])!=len(selected):raise RuntimeError('missing direct worker code pin')


def exact_identity(p):
    t=load_arrays(ROOT/p['sources']['trial_material']['path'])
    bridge.validate_identity(t,load_arrays(ROOT/p['sources']['outer_base_material']['path']),np.load(ROOT/p['sources']['base_residual']['path'],allow_pickle=False),load_arrays(ROOT/p['sources']['physical_old_time_level']['path']))
    template=pair._validate_worker_template_sources(p);adapted=pair.adapt_phase7b7j_worker_protocol(p,template,'final')
    ctx=native.phase7b7f.phase7b7e.phase7b5x._context(adapted);material=native.phase7b7i._second_full_material(adapted)
    for k,f in [('density_g_cm3','density_parent'),('temperature_k','temperature_parent'),('hydrogen_fraction','hydrogen_parent'),('helium_fraction','helium_parent')]:
        if not np.array_equal(material[f],np.concatenate((t[k],t[k][::-1]))):raise RuntimeError('native trial identity changed')
    if ctx['phase']!=int(t['phase_index']) or ctx['duration_s']!=float(t['step_duration_s']):raise RuntimeError('native physical time changed')
    return t


def verify_complete_pair(out,p,result):
    responses={};t=load_arrays(ROOT/p['sources']['trial_material']['path']);old=load_arrays(ROOT/p['sources']['physical_old_time_level']['path']);phase=int(t['phase_index'])
    for label in ('previous','final'):
        m=pipeline.read(out/'feedback'/f'{label}_manifest.json');fb=load_arrays(out/f'{label}_feedback.npz');ownership=np.zeros(9632,int)
        receipts=[]
        for row in m['completed_blocks']:
            reused.verify([row['legacy_partial'],row['legacy_report'],row['common_arrays']])
            raw=load_arrays(ROOT/row['legacy_partial']['path']);common=load_arrays(ROOT/row['common_arrays']['path']);a=load_arrays(ROOT/row['partial_path'])
            if row['partial_sha256']!=pipeline.sha256(ROOT/row['partial_path']):raise RuntimeError('new partial changed')
            if set(a)!=set(raw) or any(not np.array_equal(a[k],common['common_formal_erg_s_cm3'] if k==bridge.FORMAL else raw[k]) for k in a):raise RuntimeError('worker field substitution differs')
            ownership[row['core_group_start']:row['core_group_stop']]+=1
            paths=list((out/'feedback'/label).glob(f"block{row['block_index']:02d}.process-*.json"))
            if len(paths)!=1:raise RuntimeError('ambiguous process receipt')
            q=pipeline.read(paths[0]);receipts.append(q)
            if q['returncode']!=0 or not q['memory_guard_passed']:raise RuntimeError('independent memory/process gate failed')
        checks,*_=bridge.state_checks(fb,m['completed_blocks'],ownership,m['accumulated_wall_runtime_s'],m['maximum_process_peak_rss_mib'],p['formal_state_gates'])
        if not all(checks.values()) or not m['state_gate_passed']:raise RuntimeError('full state postcheck failed')
        book=bridge.ledger(fb,t['density_g_cm3'],float(t['step_duration_s']),old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
        np.savez(out/f'{label}_energy_ledger.npz',**book)
        responses[label]={'minimum_gas_erg_g':float(book['remaining'].min()),'failed_gas_cells':int(np.count_nonzero(book['remaining']<=0)),
            'full_state_checks':checks,'maximum_native_mib':m['maximum_process_peak_rss_mib'],
            'maximum_proc_kib':max(q['native_observed_peak_kib'] for q in receipts),'state_wall_s':m['accumulated_wall_runtime_s']}
        if label not in result.get('material_response_failures',{}):
            response,v,ctx=pair._material_response_residual(p,fb);bridge.verify_response_ledger(book,response)
            np.savez(out/f'{label}_response.npz',residual=v,temperature_k=response.temperature_k,hydrogen_fraction=response.hydrogen_fraction,
                helium_fraction=response.helium_fraction,target_specific_material_energy_erg_g=response.target_specific_material_energy_erg_g)
            responses[label]['norms']=asdict(bridge.encoded_residual_norms(v,ctx['cell_mass']))
            if label=='final' and not result.get('material_response_failures') and not np.array_equal(v,np.load(out/'material_residual.npy')):raise RuntimeError('response replay mismatch')
    report={'responses':responses,'gate_checks':result['gate_checks'],'comparison':result['comparison'],
        'material_response_failures':result.get('material_response_failures',{}),'pair_decision':result['decision'],
        'accepted_outer_steps_remain':15,'material_step_promoted':False,'frequency_truncation_convergence_established':False}
    reused.immutable(out/'postcheck.json',report);return report


def pilot(out):
    pipeline.require_allocation(1);out.mkdir(exist_ok=False)
    reference=pipeline.read(ROOT/REFERENCE/'feedback_protocol.json')
    # 复用已审的旧固定端点进行端到端bitwise预检，绝不当成新map的反馈。
    original=pipeline.read(ROOT/bridge.SOURCE/'feedback_protocol.json')
    history_source=(ROOT/bridge.SOURCE).parent
    rows=pipeline.read(history_source/'state.json')['pending_feedback']['history_rows']
    p=new_protocol(reference,out,{e:original['sources'][e+'_radiation'] for e in ('previous','final')},rows,1);attach_code(p)
    path=out/'protocol.json';reused.immutable(path,p);reused.verify(list(p['sources'].values())+p['common_code_claims']);exact_identity(p)
    partial=out/'block24.npz';report=out/'block24.json';receipt=out/'block24.process.json'
    cmd=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(receipt),'--',sys.executable,str(Path(__file__).resolve()),
         '--worker','--protocol',str(path),'--expected-protocol-sha256',pipeline.sha256(path),'--state-label','final','--block-index','24','--partial',str(partial),'--worker-report',str(report)]
    subprocess.run(cmd,cwd=ROOT,check=True)
    raw=load_arrays(partial.with_suffix('.legacy.npz'));prior=pipeline.read(ROOT/bridge.SOURCE/'feedback/final_manifest.json')['completed_blocks'][24]
    expected=load_arrays(ROOT/prior['partial_path'])
    if set(raw)!=set(expected) or any(not np.array_equal(v,expected[k]) for k,v in raw.items()):raise RuntimeError('pilot native replay differs')
    common=load_arrays(partial.with_suffix('.common.npz'));known=load_arrays(ROOT/bridge.COMMON/'final/block24.npz')
    if any(not np.array_equal(v,known[k]) for k,v in common.items()):raise RuntimeError('pilot independent common replay differs')
    reused.verify(list(p['sources'].values())+p['common_code_claims'])
    reused.immutable(out/'pilot.json',{'status':'passed','native_all_fields_bitwise':True,'independent_common_all_fields_bitwise':True,
        'worker':pipeline.read(report),'process':pipeline.read(receipt),'new_material_steps':0,'protocol':pipeline.claim(path)})


def run_pairs(out):
    pipeline.require_allocation(16);out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,new_material_steps=0,**kw))
    mark('preparing')
    try:
        pre=pipeline.read(ROOT/PILOT/'pilot.json')
        if pre['status']!='passed' or not pre['native_all_fields_bitwise'] or not pre['independent_common_all_fields_bitwise']:raise RuntimeError('pilot not passed')
        reused.verify([pre['protocol']]);frozen=pipeline.read(ROOT/pre['protocol']['path']);reused.verify(frozen['common_code_claims'])
        maps=ROOT/MAPS
        if pipeline.read(maps/'status.json')['status']!='maps_complete_feedback_required':raise RuntimeError('mapping has not finished validation')
        terminal=pipeline.read(ROOT/'outputs/review-20260923/scheduler-75951/scheduler-terminal.json')
        if terminal['state']!='COMPLETED' or terminal['job_id']!=75951:raise RuntimeError('mapping job not completed')
        state=pipeline.read(maps/'maps/state.json')
        if len(state['history'])!=8 or state['active_map']:raise RuntimeError('mapping count/partial state mismatch')
        reference=pipeline.read(ROOT/REFERENCE/'feedback_protocol.json');reports={}
        for n in (4,8):
            reused.checkpoint();end=maps/f'endpoints-map{n:02d}';retained=pipeline.read(end/'manifest.json')
            if retained['new_map_count']!=n or retained['history_rows']!=state['history'][n-2:n]:raise RuntimeError('retained history changed')
            reused.verify(list(retained['endpoints'].values()))
            folder=out/f'map{n:02d}';folder.mkdir();p=new_protocol(reference,folder,retained['endpoints'],retained['history_rows'],16)
            p['sources']['retained_manifest']=pipeline.claim(end/'manifest.json')
            if pipeline.sha256(maps/'maps/trial_material.npz')!=p['sources']['trial_material']['sha256']:raise RuntimeError('mapped trial differs from feedback trial')
            attach_code(p);p['sources']['native_pilot_evidence']=pipeline.claim(ROOT/PILOT/'pilot.json')
            reused.verify(p['common_code_claims']);exact_identity(p)
            path=folder/'feedback_protocol.json';reused.immutable(path,p);mark('feedback',endpoint_pair=n)
            with relay_dispatch(),reused.feedback_stop_guard():result=pair.run_pair(path,pipeline.sha256(path))
            reports[str(n)]=verify_complete_pair(folder,p,result)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'map{n:02d}-feedback')
            if reports[str(n)]['material_response_failures']:
                mark('physical_domain_rejected',completed_pairs=list(reports));return
        reused.immutable(out/'summary.json',{'pairs':reports,'new_material_steps':0,'accepted_outer_steps_remain':15})
        mark('complete_requires_baseline_and_confirmation',completed_pairs=[4,8]);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--pilot',action='store_true');parser.add_argument('--run',type=Path)
    parser.add_argument('--protocol',type=Path);parser.add_argument('--expected-protocol-sha256');parser.add_argument('--state-label',choices=('previous','final'))
    parser.add_argument('--block-index',type=int);parser.add_argument('--partial',type=Path);parser.add_argument('--worker-report',type=Path);a=parser.parse_args()
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    if a.worker:return worker(a.protocol,a.expected_protocol_sha256,a.state_label,a.block_index,a.partial,a.worker_report)
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    out=pipeline.safe_path(ROOT,str(a.run));out.relative_to(ROOT/'outputs/hpc')
    if a.pilot:pilot(out)
    else:run_pairs(out)


if __name__=='__main__':main()
