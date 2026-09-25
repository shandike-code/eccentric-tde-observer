"""Read-only, bounded Anderson(1) feasibility on the three audited fixed trials."""
import argparse
from contextlib import contextmanager
import json,resource,signal,sys,tarfile
from pathlib import Path
import numpy as np
from operations import common_native_feedback as fresh
from operations.diagnose_history_slow_modes import serial
from scripts import phase7b9bx_slow_mode_anderson as algebra
pipeline=fresh.pipeline;ROOT=fresh.ROOT
SOURCE='outputs/hpc/common-step21-direction-precision-20260925'


class StreamState:
    """Read one frequency slab; never map all 9.41 GiB into resident memory."""
    def __init__(self,path,shape):
        self.path=Path(path);self.shape=tuple(shape)
        if self.path.stat().st_size!=int(np.prod(shape))*8:raise ValueError('wrong state size')
    def __getitem__(self,index):
        if not isinstance(index,slice) or index.step not in (None,1):raise ValueError('contiguous slab required')
        start=0 if index.start is None else index.start;stop=self.shape[0] if index.stop is None else index.stop
        if not 0<=start<stop<=self.shape[0]:raise ValueError('invalid slab')
        stride=int(np.prod(self.shape[1:]));count=(stop-start)*stride
        with self.path.open('rb') as f:
            f.seek(start*stride*8);a=np.fromfile(f,dtype=np.float64,count=count)
        if a.size!=count or not np.isfinite(a).all() or np.any(a<0):raise ValueError('short, nonfinite or negative basis')
        return a.reshape((stop-start,)+self.shape[1:])


@contextmanager
def streaming_states():
    original=algebra._open_states
    algebra._open_states=lambda cfg,shape:tuple(StreamState(ROOT/cfg[f'x{i}_state_path'],shape) for i in (9,10,11))
    try:yield
    finally:algebra._open_states=original


def retained_basis(state,retained):
    if len(state.get('history',[]))!=8 or state.get('active_map') is not None:raise ValueError('not completed eight-map history')
    a,b=state['history'][-2:]
    if a['output_sha256']!=b['input_sha256'] or retained['history_rows']!=[a,b]:raise ValueError('broken history lineage')
    basis=[retained['endpoints'][k] for k in ('previous','final','mapped_final')]
    if [c['sha256'] for c in basis]!=[a['input_sha256'],b['input_sha256'],b['output_sha256']]:raise ValueError('retained bytes not mapped triple')
    return basis


def execute(out):
    pipeline.require_allocation(1);out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,new_maps=0,candidate_written=False,**kw))
    mark('preparing')
    try:
        audit_path=ROOT/'handoff/evidence/20260925-common-step21-direction-precision-review.json';audit=pipeline.read(audit_path)
        terminal_path=ROOT/'handoff/evidence/20260925-step21-direction-precision-76931-terminal.json';terminal=pipeline.read(terminal_path)
        if terminal['job_id']!=76931 or terminal['state']!='COMPLETED' or audit['accepted_outer_steps']!=20 or len(audit['pairs'])!=6:raise RuntimeError('missing independent audit')
        fresh.reused.verify([audit['archive']])
        with tarfile.open(ROOT/audit['archive']['path']) as t:inventory={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
        def claim_source(name):
            c=pipeline.claim(ROOT/SOURCE/name);expected=inventory[name]
            if any(c[k]!=expected[k] for k in ('size_bytes','sha256')):raise RuntimeError('source replaced: '+name)
            return c
        master=pipeline.claim(ROOT/pipeline.MASTER)
        with np.load(ROOT/pipeline.MASTER,allow_pickle=False) as z:edges=z['active_edge_hz'].copy()
        code=fresh.code_claims()+[pipeline.claim(Path(__file__).with_suffix('.sbatch')),pipeline.claim(ROOT/'handoff/protocols/step21-radiation-history-scan-v1.md')]
        cases={};claims=[pipeline.claim(audit_path),pipeline.claim(terminal_path),master]
        for case in ('control','thermal','population'):
            for name in ('state.json','config.json','trial_material.npz','endpoints-map08/manifest.json'):claims.append(claim_source(case+'/'+name))
            folder=ROOT/SOURCE/case;state=pipeline.read(folder/'state.json');cfg=pipeline.read(folder/'config.json')
            if pipeline.sha256(folder/'config.json')!=state['config_sha256'] or not any(c['sha256']==master['sha256'] for c in cfg['sources']):raise RuntimeError('config/master identity changed')
            basis=retained_basis(state,pipeline.read(folder/'endpoints-map08/manifest.json'));fresh.reused.verify(basis)
            cases[case]={'basis':basis,'latest_actual_residual':state['history'][-1]['residual']};claims+=basis
        plan={'cases':cases,'claims':claims,'code':code,'environment':pipeline.environment(),'scope':'algebraic feasibility only; no candidate/map/feedback/promotion','scan_frequency_chunk':16,'diagnostic_frequency_block':128,'fraction_bounds':[1.,96.]}
        fresh.reused.immutable(out/'declaration.json',plan);result={'histories':{},'fresh_map_required':True,'strict_error_bound':False,'accepted_outer_steps':20,'new_maps':0,'candidate_written':False}
        for case,info in cases.items():
            mark('scanning',case=case)
            cfg={'scan_frequency_chunk':16,'diagnostic_frequency_block':128,'minimum_forward_picard_fraction':1.,'maximum_forward_picard_fraction':96.}
            for i,c in enumerate(info['basis'],9):cfg[f'x{i}_state_path']=c['path']
            # 只改变一个全局外推系数，正性上界来自所有单元；不裁剪任何强度。
            with streaming_states(),np.errstate(invalid='raise',over='raise',divide='raise'):
                direction=algebra._scan_direction(cfg,pipeline.SHAPE);s=float(direction['selected_forward_fraction']);metrics=algebra._candidate_metrics(cfg,pipeline.SHAPE,s,edges)
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('scan memory guard exceeded')
            gates={'basis_positive':bool(np.all(direction['minimum_basis_intensities']>=0)),'direction_resolved':bool(direction['difference_ratio']>1e-12),'fraction_above_one':s>1.,'coefficient_l1_below_192':abs(1-s)+abs(s)<192.,'predicted_positive':metrics['candidate_negative_count']==metrics['predicted_map_negative_count']==0,'predicted_max_ratio_below_099':metrics['predicted_global_original_operator_residual']/info['latest_actual_residual']<.99,'predicted_boundary_pass':metrics['predicted_boundary_spectrum_l1']<1e-3 and metrics['predicted_boundary_bolometric_fraction']<1e-3}
            result['histories'][case]=serial({'direction':direction,'metrics':metrics,'algebraic_gates':gates,'algebraic_feasibility':all(gates.values()),'latest_actual_residual':info['latest_actual_residual'],'peak_rss_bytes':peak,'actual_candidate_residual':None,'actual_map_performed':False})
            pipeline.write_json(out/'prediction.json',result)
        fresh.reused.verify(claims+code);mark('complete_requires_review');fresh.reused.archive(out,'complete')
    except BaseException as exc:
        mark('failed',error=repr(exc));fresh.reused.archive(out,'failed');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    def stop(*_):raise InterruptedError('bounded scan interrupted; no candidate written')
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,stop)
    execute(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
