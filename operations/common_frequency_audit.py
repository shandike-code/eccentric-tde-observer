"""Versioned common-frequency audit; never changes historical feedback verdicts."""
from operations import repeat_frequency_boundary as prep
from operations.repeat_frequency_boundary import *
from operations.common_frequency_four_force import common_frequency_four_force
SOURCE='outputs/hpc/step16-backtrack-20260923/full/feedback-round1'
PILOT='outputs/hpc/common-frequency-pilot-20260923'
STOP=False

def request_stop(*args):
    global STOP
    STOP=True

def worker(plan_path,block,out):
    started=time.monotonic();plan=pipeline.read(plan_path)
    reused.verify([c for c in plan['claims'] if not c['path'].endswith('.dat')])
    protocol=pipeline.read(ROOT/plan['source']/'feedback_protocol.json')
    template=pair._validate_worker_template_sources(protocol)
    adapted=pair.adapt_phase7b7j_worker_protocol(protocol,template,plan['endpoint'])
    mod=native.phase7b7f;context=mod.phase7b7e.phase7b5x._context(adapted)
    updated=native.phase7b7i._second_full_material(adapted)
    mapped=np.memmap(ROOT/adapted['sources']['mapped_radiation_state']['path'],mode='r',dtype=np.float64,shape=native.phase7b7i._shape(adapted))
    original=mod.assembled_block_diagnostics(adapted,context,updated,mapped,block)
    stored=load_arrays(ROOT/plan['blocks'][str(block)]['partial_path'])
    for k,key in KEYS.items():
        if not np.array_equal(original[key],stored[STORED[k]]):raise RuntimeError('original block changed: '+k)
    b=context['blocks'][block];local=b.local_stencil
    fields=mod.phase7b7e._local_fields(context,b,updated)
    active_start=int(context['stencil'].active_outer_group_start);active_stop=int(context['stencil'].active_outer_group_stop)
    start=max(b.outer_group_start,active_start);stop=min(b.outer_group_stop,active_stop)
    fields['outer'][start-b.outer_group_start:stop-b.outer_group_start]=mapped[start-active_start:stop-active_start]
    transform=mod.lorentz_ray_transform(context['mu'],context['weight'],context['beta'])
    comoving=mod.comoving_group_radiation(fields['outer'],local.outer_lab_edge_hz,local.comoving_collision_edge_hz,context['mu'],context['weight'],context['beta'])
    global_edge=context['stencil'].active_lab_edge_hz
    window=(float(global_edge[b.core_group_start]),float(global_edge[b.core_group_stop]))
    arrays=common_frequency_four_force(fields['outer'],local.outer_lab_edge_hz,local.comoving_collision_edge_hz,
        fields['true_absorption']+fields['scattering'],
        fields['thermal_emissivity']+fields['scattering']*comoving.mean_intensity_density,
        context['mu'],context['weight'],context['beta'],window)
    for k,key in KEYS.items():arrays['original_'+k]=np.array(original[key])
    if not all(np.isfinite(v).all() for v in arrays.values()):raise RuntimeError('nonfinite boundary result')
    rss=ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
    if rss>=6144:raise RuntimeError('native memory gate failed')
    path=out/f'block{block:02d}.npz';np.savez(path,**arrays)
    reused.immutable(out/f'block{block:02d}.json',{'block':block,'comoving_window_hz':list(window),'core_group_start':int(b.core_group_start),'core_group_stop':int(b.core_group_stop),'original_source_bitwise_replayed':True,'native_peak_mib':rss,'wall_s':time.monotonic()-started,'arrays':pipeline.claim(path)})


def metric(reference,value,width):
    a,b,ra,rb=native.phase7b7f._source_metrics(reference,value,width)
    if not all(np.isfinite(x) for x in (a,b,ra,rb)):raise RuntimeError('undefined source metric')
    return {'volume_l1':a,'net_fraction':b,'reference_integral':ra,'compared_integral':rb,
            'difference_depth_l1':float(np.sum(width*np.abs(reference-value)))}


def summarize(folder,plan):
    fb=load_arrays(ROOT/plan['feedback']['path']);width=fb['subcell_width_cm'];total={};reports=[];receipts=[]
    ownership=np.zeros(9632,dtype=np.int64)
    for i in plan['selected_blocks']:
        r=pipeline.read(folder/f'block{i:02d}.json');reused.verify([r['arrays']]);a=load_arrays(ROOT/r['arrays']['path'])
        if not r['original_source_bitwise_replayed'] or r['native_peak_mib']>=6144:raise RuntimeError('native audit failed')
        q=pipeline.read(folder/f'block{i:02d}.process.json')
        if q['returncode']!=0 or not q['memory_guard_passed']:raise RuntimeError('independent worker/memory audit failed')
        ownership[r['core_group_start']:r['core_group_stop']]+=1
        if not total:total={k:np.zeros_like(v) for k,v in a.items()}
        for k,v in a.items():total[k]+=v
        reports.append(r);receipts.append(q)
    if not all(np.isfinite(v).all() for v in total.values()):raise RuntimeError('nonfinite assembled source')
    full=plan['selected_blocks']==list(range(76))
    if full:
        if not np.all(ownership==1):raise RuntimeError('common-window ownership gap/overlap')
        for k in KEYS:
            if not np.array_equal(total['original_'+k],fb[STORED[k]]):raise RuntimeError('original full assembly changed')
        rate=fb['atomic_rate_heating_erg_s_cm3']
    else:rate=total['original_rate']
    width=np.asarray(width);common=total['common_formal_erg_s_cm3']
    metrics={'atomic_vs_common':metric(rate,common,width),
             'direct_vs_common':metric(total['original_direct'],common,width),
             'atomic_vs_old_formal':metric(rate,total['original_formal'],width),
             'atomic_vs_direct':metric(rate,total['original_direct'],width)}
    gates=pipeline.read(ROOT/SOURCE/'feedback_protocol.json')['formal_state_gates']
    checks={'volume_l1':metrics['atomic_vs_common']['volume_l1']<gates['atomic_rate_vs_inverse_four_force_volume_l1_below'],
            'net_fraction':metrics['atomic_vs_common']['net_fraction']<gates['atomic_rate_vs_inverse_four_force_global_fraction_below'],
            'rate_direct':metrics['atomic_vs_direct']['volume_l1']<gates['atomic_rate_vs_direct_comoving_heating_volume_l1_below']}
    if not full:
        checks['pilot_direct_consistency']=metrics['direct_vs_common']['volume_l1']<1e-10
    np.savez(folder/'comparison.npz',subcell_width_cm=width,atomic_rate_heating_erg_s_cm3=rate,**total)
    summary={'status':'common_source_consistent' if all(checks.values()) else 'common_source_inconsistent',
             'endpoint':plan['endpoint'],'all_76_blocks':full,'source_checks':checks,'metrics':metrics,
             'maximum_native_mib':max(r['native_peak_mib'] for r in reports),
             'maximum_proc_kib':max(r['native_observed_peak_kib'] for r in receipts),
             'arrays':pipeline.claim(folder/'comparison.npz'),'original_formal_verdict_retained':'gate_failed',
             'formal_state_gate_thresholds':gates,'material_response_evaluated':False,'material_step_accepted':False,
             'frequency_truncation_convergence_established':False,'claims':plan['claims']}
    reused.immutable(folder/'summary.json',summary)
    if not all(checks.values()):raise RuntimeError('common source consistency checks failed; evidence retained')
    return summary


def run_audit(out,pilot):
    workers=1 if pilot else 16;pipeline.require_allocation(workers)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,request_stop)
    pipeline.write_json(out/'status.json',{'status':'preparing','maximum_states':1 if pilot else 2,'maximum_blocks_per_state':1 if pilot else 76,'new_maps':0})
    try:
        prior_claims=[]
        if not pilot:
            p=ROOT/PILOT/'final/summary.json';r=pipeline.read(p)
            if r['status']!='common_source_consistent' or r['all_76_blocks']:raise RuntimeError('pilot not passed')
            reused.verify(r['claims']);prior_claims.append(pipeline.claim(p))
        results=[]
        for endpoint in (('final',) if pilot else ('previous','final')):
            if STOP:
                pipeline.write_json(out/'status.json',{'status':'interrupted','completed_states':len(results)});return
            folder,old=prep.prepare_case(out,endpoint,SOURCE,endpoint)
            files=['operations/common_frequency_audit.py','operations/common_frequency_four_force.py',
                   'operations/common_frequency_audit.sbatch','operations/common_frequency_pilot.sbatch',
                   'tests/test_common_frequency_four_force.py','handoff/protocols/common-frequency-source-v1.md']
            claims=old['claims']+prior_claims+[pipeline.claim(ROOT/f) for f in files]
            plan={**old,'claims':claims,'selected_blocks':[24] if pilot else list(range(76)),
                  'workers':workers,'common_frequency_protocol':'common-frequency-source-v1',
                  'pilot':pilot,'physical_updates':False}
            reused.verify([c for c in claims if not c['path'].endswith('.dat')])
            reused.immutable(folder/'common_declaration.json',plan)
            for start in range(0,len(plan['selected_blocks']),workers):
                if STOP:
                    pipeline.write_json(out/'status.json',{'status':'interrupted','endpoint':endpoint,'completed_blocks':start});return
                processes=[]
                for i in plan['selected_blocks'][start:start+workers]:
                    cmd=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(folder/f'block{i:02d}.process.json'),'--',sys.executable,str(Path(__file__).resolve()),'--worker',str(i),'--run',str(folder.relative_to(ROOT))]
                    processes.append(subprocess.Popen(cmd,cwd=ROOT))
                codes=[p.wait() for p in processes]
                if any(codes):raise RuntimeError('common source worker failed: '+str(codes))
                pipeline.write_json(out/'status.json',{'status':'running','endpoint':endpoint,'completed_blocks':min(start+workers,len(plan['selected_blocks']))})
            reused.verify(claims);results.append(summarize(folder,plan))
        reused.immutable(out/'summary.json',{'status':'common_source_consistent','states':results,'new_maps':0,'material_step_accepted':False})
        pipeline.write_json(out/'status.json',{'status':'common_source_consistent','completed_states':len(results)})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)});raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--pilot',action='store_true');p.add_argument('--worker',type=int);a=p.parse_args();out=pipeline.safe_path(ROOT,a.run)
    if a.worker is None:run_audit(out,a.pilot)
    else:
        plan=pipeline.read(out/'common_declaration.json')
        if a.worker not in plan['selected_blocks']:raise ValueError('undeclared common-frequency block')
        worker(out/'common_declaration.json',a.worker,out)


if __name__=='__main__':main()
