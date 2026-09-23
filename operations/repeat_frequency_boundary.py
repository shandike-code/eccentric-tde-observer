"""Replicate finite-band identity on three other retained failed endpoints.

Independent version: source_frequency_boundary.worker with explicit plan source
and endpoint. Original frozen driver is not edited or patched at runtime.
"""
from operations.source_frequency_boundary import *
import signal
CASES=(
 ('backtrack-previous','outputs/hpc/step16-backtrack-20260923/full/feedback-round1','previous'),
 ('amplitude-previous','outputs/hpc/step16-amplitude-20260923/full/feedback-round2','previous'),
 ('amplitude-final','outputs/hpc/step16-amplitude-20260923/full/feedback-round2','final'),
)
STOP=False

def stop_after_batch(*args):
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
    boundary=float(context['stencil'].active_lab_edge_hz[0 if block==0 else -1])
    integrals=boundary_integrals(fields['outer'],local.outer_lab_edge_hz,local.comoving_collision_edge_hz,transform.doppler_lab_to_comoving,fields['true_absorption'],fields['thermal_emissivity'],fields['scattering'],comoving.mean_intensity_density,boundary)
    # H0=chi0*I0-eta0。H0[A,B]-H0[DA,DB]=H0[A,DA]-H0[B,DB]。
    arrays={k:(1 if block==0 else -1)*2*np.pi*np.sum(transform.comoving_angular_weight*v,axis=0) for k,v in integrals.items()}
    arrays['angular_measure_error']=0.5*np.sum(transform.comoving_angular_weight,axis=0)-1
    if not all(np.isfinite(v).all() for v in arrays.values()):raise RuntimeError('nonfinite boundary result')
    rss=ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
    if rss>=6144:raise RuntimeError('native memory gate failed')
    path=out/f'block{block:02d}.npz';np.savez(path,**arrays)
    reused.immutable(out/f'block{block:02d}.json',{'block':block,'boundary_hz':boundary,'original_source_bitwise_replayed':True,'native_peak_mib':rss,'wall_s':time.monotonic()-started,'arrays':pipeline.claim(path)})


def prepare_case(out,name,source,endpoint):
    folder=out/name;folder.mkdir(exist_ok=False)
    pp=ROOT/source/'feedback_protocol.json';proto=pipeline.read(pp)
    template=pair._validate_worker_template_sources(proto)
    adapted=pair.adapt_phase7b7j_worker_protocol(proto,template,endpoint)
    mp=ROOT/source/f'feedback/{endpoint}_manifest.json';manifest=pipeline.read(mp)
    if manifest['status']!='gate_failed' or manifest['protocol_sha256']!=pipeline.sha256(pp):
        raise RuntimeError('source is not the declared failed feedback')
    state_claim=proto['sources'][endpoint+'_radiation']
    if manifest['state_path']!=state_claim['path'] or manifest['state_sha256']!=state_claim['sha256']:
        raise RuntimeError('endpoint identity mismatch')
    rows=manifest['completed_blocks']
    if [r['block_index'] for r in rows]!=list(range(76)):raise RuntimeError('source ownership incomplete')
    old=pipeline.read(ROOT/'outputs/hpc/source-frequency-boundary-20260923/declaration.json')
    # 前次已经审计的代码/小源继续固定；新端点实际读取的大态单独核验。
    claims=[c for c in old['claims'] if not c['path'].endswith('.dat')]
    claims += [c for c in proto['sources'].values() if not c['path'].endswith('.dat')]
    claims += list(adapted['sources'].values())
    claims += [state_claim,pipeline.claim(pp),pipeline.claim(mp),pipeline.claim(Path(__file__)),pipeline.claim(ROOT/'operations/repeat_frequency_boundary.sbatch')]
    for row in rows:
        c=pipeline.claim(ROOT/row['partial_path'])
        if c['sha256']!=row['partial_sha256']:raise RuntimeError('source partial changed')
        claims.append(c)
    feedback=pipeline.claim(ROOT/manifest['feedback_artifact_path'])
    if feedback['sha256']!=manifest['feedback_artifact_sha256']:raise RuntimeError('source feedback changed')
    claims.append(feedback);unique={}
    for c in claims:
        if c['path'] in unique and unique[c['path']]!=c:raise RuntimeError('conflicting claims')
        unique[c['path']]=c
    plan={'source':source,'endpoint':endpoint,'claims':list(unique.values()),'feedback':feedback,'blocks':{str(r['block_index']):r for r in rows},'selected_blocks':list(BLOCKS),'environment':pipeline.environment(),'new_maps':0,'material_step_accepted':False}
    reused.verify(plan['claims']);reused.immutable(folder/'declaration.json',plan)
    return folder,plan


def summarize_case(folder,plan):
    fb=load_arrays(ROOT/plan['feedback']['path']);width=fb['subcell_width_cm'];original={k:np.zeros_like(width) for k in KEYS}
    for i in range(76):
        a=load_arrays(ROOT/plan['blocks'][str(i)]['partial_path'])
        for k in KEYS:original[k]+=a[STORED[k]]
    for k in KEYS:
        if not np.array_equal(original[k],fb[STORED[k]]):raise RuntimeError('assembled original changed')
    boundary=np.zeros_like(width);ends={}
    for i in BLOCKS:
        report=pipeline.read(folder/f'block{i:02d}.json');reused.verify([report['arrays']])
        receipt=pipeline.read(folder/f'block{i:02d}.process.json')
        if receipt['returncode']!=0 or not receipt['memory_guard_passed']:raise RuntimeError('worker/memory failure')
        a=load_arrays(folder/f'block{i:02d}.npz');ends[str(i)]={}
        for k in FIELDS:
            boundary+=a[k];ends[str(i)][k]=float(np.sum(width.astype(np.longdouble)*a[k].astype(np.longdouble)))
    observed=original['direct']-original['formal'];residual=observed-boundary
    values={'observed':observed,'boundary':boundary,'residual':residual,'residual_depth_l1':np.abs(residual),'observed_depth_l1':np.abs(observed),'rate_minus_direct':original['rate']-original['direct']}
    metrics={k:float(np.sum(width.astype(np.longdouble)*v.astype(np.longdouble))) for k,v in values.items()}
    if not all(np.isfinite(v).all() for v in values.values()):raise RuntimeError('nonfinite result')
    np.savez(folder/'comparison.npz',width_cm=width,**values)
    summary={'status':'evidence_complete','source':plan['source'],'endpoint':plan['endpoint'],'metrics_erg_s_cm2':metrics,'boundary_components':ends,'arrays':pipeline.claim(folder/'comparison.npz'),'material_step_accepted':False,'physical_gates_changed':False}
    reused.immutable(folder/'summary.json',summary);return summary


def run_repeats(out):
    pipeline.require_allocation(2)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,stop_after_batch)
    pipeline.write_json(out/'status.json',{'status':'preparing','maximum_endpoints':3,'maximum_boundary_workers':6,'new_maps':0})
    try:
        reports=[]
        for name,source,endpoint in CASES:
            if STOP:
                pipeline.write_json(out/'status.json',{'status':'interrupted','completed_endpoints':len(reports)});return
            folder,plan=prepare_case(out,name,source,endpoint)
            if STOP:
                pipeline.write_json(out/'status.json',{'status':'interrupted','completed_endpoints':len(reports)});return
            processes=[]
            for i in BLOCKS:
                cmd=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(folder/f'block{i:02d}.process.json'),'--',sys.executable,str(Path(__file__).resolve()),'--worker',str(i),'--run',str(folder.relative_to(ROOT))]
                processes.append(subprocess.Popen(cmd,cwd=ROOT))
            codes=[p.wait() for p in processes]
            if any(codes):raise RuntimeError('repeat worker failed: '+str(codes))
            reused.verify(plan['claims']);reports.append(summarize_case(folder,plan))
            pipeline.write_json(out/'status.json',{'status':'running','completed_endpoints':len(reports)})
        reused.immutable(out/'summary.json',{'status':'evidence_complete','endpoints':reports,'material_step_accepted':False,'new_maps':0})
        pipeline.write_json(out/'status.json',{'status':'evidence_complete','completed_endpoints':len(reports)})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)});raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--worker',type=int);a=p.parse_args();out=pipeline.safe_path(ROOT,a.run)
    if a.worker is None:run_repeats(out)
    else:
        if a.worker not in BLOCKS:raise ValueError('undeclared boundary block')
        worker(out/'declaration.json',a.worker,out)


if __name__=='__main__':main()
