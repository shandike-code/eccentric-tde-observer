"""Read-only test of finite-band source differences on the retained endpoint."""
from operations.source_split_tail_evidence import *
from operations.frequency_boundary_integral import boundary_integrals
BLOCKS=(0,75)


def worker(plan_path,block,out):
    started=time.monotonic();plan=pipeline.read(plan_path)
    reused.verify([c for c in plan['claims'] if not c['path'].endswith('.dat')])
    protocol=pipeline.read(ROOT/SOURCE/'feedback_protocol.json')
    template=pair._validate_worker_template_sources(protocol)
    adapted=pair.adapt_phase7b7j_worker_protocol(protocol,template,'final')
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


def aggregate_boundary(out,plan):
    fb=load_arrays(ROOT/plan['feedback']['path']);width=fb['subcell_width_cm']
    total={};reports=[]
    for i in range(76):
        folder=ROOT/BASE_RUN if i not in TAIL_BLOCKS else ROOT/'outputs/hpc/source-split-tail-evidence-20260923'
        a=load_arrays(folder/f'block{i:02d}.npz')
        if not total:total={k:np.zeros_like(v) for k,v in a.items()}
        for k,v in a.items():total[k]+=v
    for k in KEYS:
        if not np.array_equal(total['original_'+k],fb[STORED[k]]):raise RuntimeError('full original assembly changed')
    ends=[]
    for i in BLOCKS:
        report=pipeline.read(out/f'block{i:02d}.json');reused.verify([report['arrays']]);reports.append(report)
        receipt=pipeline.read(out/f'block{i:02d}.process.json')
        if receipt['returncode']!=0 or not receipt['memory_guard_passed']:raise RuntimeError('worker/memory failure')
        ends.append(load_arrays(out/f'block{i:02d}.npz'))
    result={};saved={'width_cm':width}
    for c in FIELDS:
        observed=total[c+'_direct']-total[c+'_formal'];predicted=ends[0][c]+ends[1][c];residual=observed-predicted
        saved.update({c+'_direct_minus_formal':observed,c+'_boundary_prediction':predicted,c+'_residual':residual,c+'_rate_minus_direct':total[c+'_rate']-total[c+'_direct']})
        result[c]={name:float(np.sum(width.astype(np.longdouble)*v.astype(np.longdouble))) for name,v in {'observed':observed,'boundary':predicted,'residual':residual,'residual_depth_l1':np.abs(residual),'observed_depth_l1':np.abs(observed),'rate_minus_direct':saved[c+'_rate_minus_direct']}.items()}
    np.savez(out/'comparison.npz',**saved)
    reused.immutable(out/'summary.json',{'status':'evidence_complete','metrics_erg_s_cm2':result,'blocks':reports,'arrays':pipeline.claim(out/'comparison.npz'),'original_source_bitwise_replayed':True,'prior_split_failed_checks_retained':list(TAIL_BLOCKS),'physical_gates_changed':False,'material_step_accepted':False,'new_maps':0})


def run_boundary(out):
    pipeline.require_allocation(2)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    pipeline.write_json(out/'status.json',{'status':'preparing'})
    try:
        old_path=ROOT/'outputs/hpc/source-split-tail-evidence-20260923/declaration.json';old=pipeline.read(old_path)
        selected=old['claims']+[pipeline.claim(old_path)]
        for name in ('source_frequency_boundary.py','source_frequency_boundary.sbatch','frequency_boundary_integral.py'):
            selected.append(pipeline.claim(ROOT/'operations'/name))
        for i in range(76):
            folder=ROOT/BASE_RUN if i not in TAIL_BLOCKS else ROOT/'outputs/hpc/source-split-tail-evidence-20260923'
            report=pipeline.read(folder/f'block{i:02d}.json');selected.extend([report['arrays'],pipeline.claim(folder/f'block{i:02d}.json')])
        claims={}
        for c in selected:
            if c['path'] in claims and claims[c['path']]!=c:raise RuntimeError('conflicting claims')
            claims[c['path']]=c
        reused.verify(list(claims.values()))
        plan={**old,'claims':list(claims.values()),'selected_blocks':list(BLOCKS),'workers':2,'maximum_block_diagnostics':2,'source_calls_per_block':1,'environment':pipeline.environment(),'purpose':'finite_band_boundary_identity_only','new_maps':0}
        reused.immutable(out/'declaration.json',plan)
        processes=[]
        for i in BLOCKS:
            command=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(out/f'block{i:02d}.process.json'),'--',sys.executable,str(Path(__file__).resolve()),'--worker',str(i),'--run',str(out.relative_to(ROOT))]
            processes.append(subprocess.Popen(command,cwd=ROOT))
        codes=[p.wait() for p in processes]
        if any(codes):raise RuntimeError('boundary worker failure: '+str(codes))
        reused.verify(plan['claims']);aggregate_boundary(out,plan)
        pipeline.write_json(out/'status.json',{'status':'evidence_complete','material_step_accepted':False})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)});raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--worker',type=int);a=p.parse_args();out=pipeline.safe_path(ROOT,a.run)
    if a.worker is None:run_boundary(out)
    else:
        if a.worker not in BLOCKS:raise ValueError('undeclared boundary block')
        worker(out/'declaration.json',a.worker,out)


if __name__=='__main__':main()
