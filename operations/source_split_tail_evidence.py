"""Record rejected tail source-split arithmetic without accepting failed checks."""
from operations.formal_source_split import *
TAIL_BLOCKS=(71,72,73,74)
BASE_RUN='outputs/hpc/formal-source-split-all-20260923'

def linearity_measurement(pieces, original):
    scale=max(float(np.max(sum(np.abs(v) for v in pieces))),float(np.max(np.abs(original))))
    error=float(np.max(np.abs(sum(pieces)-original)))
    return error/scale if scale>0 else error, error, scale


def worker(plan_path, block, out):
    started=time.monotonic();plan=pipeline.read(plan_path)
    # Parent hashes the 9.41GiB source once inside its allocation. Workers verify
    # small immutable inputs and reproduce the original block output exactly.
    reused.verify([c for c in plan['claims'] if not c['path'].endswith('.dat')])
    protocol=pipeline.read(ROOT/SOURCE/'feedback_protocol.json')
    template=pair._validate_worker_template_sources(protocol)
    adapted=pair.adapt_phase7b7j_worker_protocol(protocol,template,'final')
    context=native.phase7b7f.phase7b7e.phase7b5x._context(adapted)
    updated=native.phase7b7i._second_full_material(adapted)
    shape=native.phase7b7i._shape(adapted)
    mapped=np.memmap(ROOT/adapted['sources']['mapped_radiation_state']['path'],mode='r',dtype=np.float64,shape=shape)
    original=native.phase7b7f.assembled_block_diagnostics(adapted,context,updated,mapped,block)
    row=plan['blocks'][str(block)];stored=load_arrays(ROOT/row['partial_path'])
    for k,key in KEYS.items():
        if not np.array_equal(original[key],stored[STORED[k]]):raise RuntimeError('original source did not replay bitwise: '+k)
    result={'original_'+k:np.array(original[key]) for k,key in KEYS.items()}
    for component in FIELDS:
        with component_operator(component):
            part=native.phase7b7f.assembled_block_diagnostics(adapted,context,updated,mapped,block)
        for k,key in KEYS.items():result[component+'_'+k]=np.array(part[key])
        del part;gc.collect()
    closure={};absolute_errors={};scales={}
    for k in KEYS:
        pieces=[result[c+'_'+k] for c in FIELDS]
        closure[k],absolute_errors[k],scales[k]=linearity_measurement(pieces,result['original_'+k])
    zero=dict(context);zero['beta']=np.zeros_like(context['beta']);zero['parent_beta']=np.zeros_like(context['parent_beta'])
    control=native.phase7b7f.assembled_block_diagnostics(adapted,zero,updated,mapped,block)
    for k,key in KEYS.items():result['beta0_'+k]=np.array(control[key])
    if not all(np.all(np.isfinite(v)) for v in result.values()):raise RuntimeError('nonfinite source diagnostic')
    rss=ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
    if rss>=6144:raise RuntimeError('native memory gate failed')
    file=out/f'block{block:02d}.npz';np.savez(file,**result)
    report={'block':block,'original_source_bitwise_replayed':True,'linear_closure_error':closure,'linear_absolute_error':absolute_errors,'linear_scale':scales,'linear_check_passed':all(v<=1e-12 for v in closure.values()),'original_check_threshold':1e-12,'measurement_only_not_acceptance':True,'native_peak_mib':rss,'wall_s':time.monotonic()-started,'arrays':pipeline.claim(file)}
    reused.immutable(out/f'block{block:02d}.json',report)


def run_tail(out):
    pipeline.require_allocation(2)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    pipeline.write_json(out/'status.json',{'status':'preparing'})
    try:
        old_path=ROOT/BASE_RUN/'declaration.json';old=pipeline.read(old_path)
        state=pipeline.read(ROOT/BASE_RUN/'status.json')
        if state['status']!='failed':raise RuntimeError('source diagnostic no longer failed')
        proto=pipeline.read(ROOT/SOURCE/'feedback_protocol.json')
        # This fixed-state measurement reads one radiation state, not historical
        # states used to construct the already-frozen accepted material lineage.
        selected=[c for c in old['claims'] if not c['path'].endswith('.dat')]
        selected += [proto['sources']['final_radiation'],pipeline.claim(old_path),pipeline.claim(ROOT/BASE_RUN/'status.json'),pipeline.claim(Path(__file__)),pipeline.claim(ROOT/'operations/source_split_tail_evidence.sbatch')]
        claims={}
        for c in selected:
            if c['path'] in claims and claims[c['path']]!=c:raise RuntimeError('conflicting source claims')
            claims[c['path']]=c
        reused.verify(list(claims.values()))
        plan={**old,'claims':list(claims.values()),'selected_blocks':list(TAIL_BLOCKS),'workers':2,'maximum_block_diagnostics':4,'source_calls_per_block':5,'environment':pipeline.environment(),'measurement_only_not_acceptance':True,'original_check_threshold':1e-12,'historical_dat_not_read_or_rehashed':[c for c in old['claims'] if c['path'].endswith('.dat') and c!=proto['sources']['final_radiation']]}
        reused.immutable(out/'declaration.json',plan)
        for start in (0,2):
            processes=[]
            for block in TAIL_BLOCKS[start:start+2]:
                command=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(out/f'block{block:02d}.process.json'),'--',sys.executable,str(Path(__file__).resolve()),'--worker',str(block),'--run',str(out.relative_to(ROOT))]
                processes.append(subprocess.Popen(command,cwd=ROOT))
            codes=[p.wait() for p in processes]
            if any(codes):raise RuntimeError('evidence worker or memory failure: '+str(codes))
        reports=[pipeline.read(out/f'block{i:02d}.json') for i in TAIL_BLOCKS]
        receipts=[pipeline.read(out/f'block{i:02d}.process.json') for i in TAIL_BLOCKS]
        if not all(r['returncode']==0 and r['memory_guard_passed'] for r in receipts):raise RuntimeError('independent memory gate failed')
        reused.verify(plan['claims'])
        reused.immutable(out/'summary.json',{'status':'evidence_complete','measurement_only_not_acceptance':True,'original_check_threshold':1e-12,'failed_blocks':[r['block'] for r in reports if not r['linear_check_passed']],'blocks':reports,'max_proc_kib':max(r['native_observed_peak_kib'] for r in receipts),'new_maps':0,'material_step_accepted':False})
        pipeline.write_json(out/'status.json',{'status':'evidence_complete','material_step_accepted':False})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)});raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--worker',type=int);a=p.parse_args();out=pipeline.safe_path(ROOT,a.run)
    if a.worker is None:run_tail(out)
    else:
        if a.worker not in TAIL_BLOCKS:raise ValueError('undeclared evidence block')
        worker(out/'declaration.json',a.worker,out)

if __name__=='__main__':main()
