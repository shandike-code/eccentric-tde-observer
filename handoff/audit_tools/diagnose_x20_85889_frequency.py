"""Audit every stored frequency block of four map16 endpoints, without a solver."""
import argparse
import csv
import itertools
import json
import subprocess
from pathlib import Path

import numpy as np
from handoff.audit_tools.diagnose_x20_85889_energy import (
    ROOT, RECEIVED, COMMIT, STEM, arrays, digest, verify_file, log_secant, mass_norm,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.non_gray import EV_ERG
from eccentric_tde_observer.multigroup_continuum import gauss_legendre_frequency_group_quadrature

Q = 'atomic_rate_heating_erg_s_cm3'
ABS = 'absorbed_power_erg_s_cm3'
EM = 'emitted_power_erg_s_cm3'
FORMAL = 'source_formal_heating_erg_s_cm3'


def ownership(rows, groups=9632):
    counts = np.zeros(groups, int)
    if [r['block_index'] for r in rows] != list(range(len(rows))):
        raise ValueError('blocks missing, duplicated or out of order')
    for r in rows:
        a, b = r['core_group_start'], r['core_group_stop']
        if not 0 <= a < b <= groups:
            raise ValueError('invalid frequency interval')
        counts[a:b] += 1
    if not np.all(counts == 1):
        raise ValueError('frequency ownership gap or overlap')
    return counts


def projection(parts, total, mass):
    """有符号质量内积份额，含块间交叉项；不是独立范数平方百分比。"""
    parts, total, mass = map(np.asarray, (parts, total, mass))
    if parts.ndim != 2 or parts.shape[1:] != total.shape or total.shape != mass.shape:
        raise ValueError('projection shapes')
    if not all(np.isfinite(v).all() for v in (parts, total, mass)) or np.any(mass <= 0):
        raise ValueError('projection domain')
    denominator = np.sum(mass*total*total)
    if denominator == 0:
        return None
    return np.sum(parts*(mass*total)[None, :], axis=1)/denominator


def main(target):
    csvpath = target.with_suffix('.csv')
    if target.exists() or csvpath.exists():
        raise FileExistsError(target)
    inventory_path = ROOT/(STEM+'.json')
    claims = {c['path']: c for c in json.loads(inventory_path.read_text())['files']}
    sources = []
    def load(rel, binary=False):
        p = RECEIVED/rel; verify_file(p, claims[rel])
        sources.append(dict(path=str(p), **{k:claims[rel][k] for k in ('size_bytes','sha256')}))
        return arrays(p) if binary else json.loads(p.read_text())
    locations = json.loads((ROOT/'20261006-x20-85889-frequency-source-locations.json').read_text())
    for key in ('template','master'):
        verify_file(Path(locations[key]), locations[key+'_claim'])
    template = json.loads(Path(locations['template']).read_text())
    assert template['sources']['phase7b5p_master_input'] == locations['master_claim']
    master = arrays(Path(locations['master'])); edges = master['active_edge_hz']
    assert edges.shape == (9633,)
    # 原16点正权频率求积，仅核权重/组宽；不重算连续率或大场。
    quadrature = gauss_legendre_frequency_group_quadrature(edges, order_per_group=16)
    weight_error = float(np.max(np.abs(quadrature.node_weight_hz.sum(1)/np.diff(edges)-1)))
    code = []
    for rel in ['scripts/phase7b5x_full_depth_block_probe.py', 'scripts/phase7b7j_second_assembled_feedback.py', 'scripts/phase7b9_formal_feedback_pair_adapter.py', 'operations/common_native_feedback.py', 'src/eccentric_tde_observer/multigroup_continuum.py', 'src/eccentric_tde_observer/non_gray.py', 'src/eccentric_tde_observer/radiation.py']:
        frozen = subprocess.check_output(['git','show',COMMIT+':'+rel]); assert frozen == Path(rel).read_bytes()
        code.append(dict(path=rel,sha256=digest(rel)))
    energy_path = ROOT/'20261006-x20-85889-energy-diagnostic.json'
    energy_review_path = Path('handoff/evidence/20261006-x20-85889-energy-review.json')
    energy_review = json.loads(energy_review_path.read_text())
    verify_file(energy_path, next(c for c in energy_review['artifacts'] if c['path']==str(energy_path)))
    energy = json.loads(energy_path.read_text()); assert energy['archive_manifest_sha256']==digest(inventory_path)
    assert digest(energy['source_final_audit']['path'])==energy['source_final_audit']['sha256']
    trial = load('inputs/trial_material.npz', True); dt = float(trial['step_duration_s']); rho=trial['density_g_cm3']
    assert dt == 889.419892762322 and int(trial['phase_index'])==1367
    states = {}; checks = {}; intervals = None
    for branch, end in itertools.product(['accelerated','historical'],['previous','final']):
        base=f'{branch}/pair16/'; protocol=load(base+'feedback_protocol.json')
        assert protocol['sources']['phase7b7j_protocol']==locations['template_claim']
        assert protocol['configuration']['rate_quadrature_order_per_group']==16
        manifest=load(base+'feedback/'+end+'_manifest.json'); rows=manifest['completed_blocks']
        assert manifest['status']=='complete' and len(rows)==76
        ownership(rows)
        current=[(r['core_group_start'],r['core_group_stop']) for r in rows]
        if intervals is None: intervals=current
        assert current==intervals
        combined=None; partials={k:[] for k in (Q,ABS,EM)}
        for row in rows:
            i=row['block_index']; rel=base+f'feedback/{end}/block{i:02d}'
            receipt=load(rel+'.json'); assert receipt==row
            block=load(rel+'.npz',True); legacy=load(rel+'.legacy.npz',True); common=load(rel+'.common.npz',True)
            assert digest(RECEIVED/(rel+'.npz'))==row['partial_sha256']
            for name, suffix in [('legacy_partial','.legacy.npz'),('common_arrays','.common.npz')]:
                verify_file(RECEIVED/(rel+suffix), row[name])
            assert set(block)==set(legacy)
            for k in block:
                np.testing.assert_array_equal(block[k],common['common_formal_erg_s_cm3'] if k==FORMAL else legacy[k])
            np.testing.assert_array_equal(block[Q],block[ABS]-block[EM])
            if combined is None: combined={k:np.zeros_like(v) for k,v in block.items()}
            for k in combined: combined[k]+=block[k]
            for k in partials: partials[k].append(block[k].reshape(256,16).mean(1)[:128])
        fb=load(base+end+'_feedback.npz',True)
        for k,v in combined.items():
            np.testing.assert_array_equal(v,fb[k])
            np.testing.assert_array_equal(v.reshape(256,16,*v.shape[1:]).mean(1)[:128],fb['half_'+k])
        states[branch+'_'+end]={k:np.array(v) for k,v in partials.items()}
        checks[branch+'_'+end]=dict(blocks=76,groups=9632,fields=len(combined),all_fields_sum_bitwise=True,nonformal_legacy_bitwise=True,atomic_equals_absorbed_minus_emitted_bitwise=True)
    output={}; csvrows=[]
    for a_end,b_end in itertools.product(['previous','final'],repeat=2):
        label=b_end+'_vs_'+a_end; a=states['accelerated_'+a_end]; b=states['historical_'+b_end]
        e=energy['comparisons']['cross16'][label]; cells=e['cells']; mass=np.array([c['mass_g_cm2'] for c in cells])
        g=log_secant(np.array([c['gas_a_erg_g'] for c in cells]),np.array([c['gas_b_erg_g'] for c in cells]))
        heat_target=np.array([c['heating_log_contribution'] for c in cells])
        # 块已含频率积分，不能再次乘组宽。只执行原half归并、dt/rho和同一端点割线。
        delta_q=b[Q]-a[Q]; parts=g[None,:]*dt*delta_q/rho[None,:]
        total=parts.sum(0); error=float(np.max(np.abs(total-heat_target)))
        assert error < 4e-13, ('frequency sum vs energy diagnostic', error)
        share=projection(parts,total,mass); assert share is not None
        np.testing.assert_allclose(share.sum(),1,rtol=0,atol=5e-14)
        emitted_equal=np.array_equal(a[EM],b[EM]); absorbed_diff=b[ABS]-a[ABS]; emitted_diff=b[EM]-a[EM]
        net_power_error=float(np.max(np.abs(delta_q-(absorbed_diff-emitted_diff))))
        block_rows=[]
        for i,(start,stop) in enumerate(intervals):
            row=dict(block=i,start=start,stop=stop,energy_left_ev=float(edges[start]*PLANCK_ERG_S/EV_ERG),energy_right_ev=float(edges[stop]*PLANCK_ERG_S/EV_ERG),signed_projection=float(share[i]),log_contribution_mass_norm=mass_norm(parts[i],mass),delta_half_q_erg_s_cm3=delta_q[i].tolist(),log_contribution=parts[i].tolist())
            block_rows.append(row)
            for j,c in enumerate(cells):
                csvrows.append(dict(combination=label,block=i,cell=j,energy_left_ev=row['energy_left_ev'],energy_right_ev=row['energy_right_ev'],mass_fraction_left=c['mass_fraction_interval'][0],mass_fraction_right=c['mass_fraction_interval'][1],delta_half_q_erg_s_cm3=float(delta_q[i,j]),delta_absorbed_half_erg_s_cm3=float(absorbed_diff[i,j]),delta_emitted_half_erg_s_cm3=float(emitted_diff[i,j]),log_contribution=float(parts[i,j])))
        norms=np.array([mass_norm(v,mass) for v in parts]); order=np.argsort(-np.abs(share))
        output[label]=dict(blocks=block_rows,heating_log_sum_max_abs_error=error,emitted_all_blocks_half_bitwise_equal=emitted_equal,net_vs_absorbed_minus_emitted_max_abs_error_erg_s_cm3=net_power_error,signed_projection_sum=float(share.sum()),sum_block_norm_over_total_norm=float(norms.sum()/mass_norm(total,mass)),top10_by_absolute_projection=order[:10].tolist(),total_heating_log_mass_norm=mass_norm(total,mass),cell126_total_delta_q_erg_s_cm3=float(delta_q[:,126].sum()),cell126_sum_absolute_over_absolute_sum=float(np.abs(delta_q[:,126]).sum()/abs(delta_q[:,126].sum())))
    result=dict(job_id=85889,numerical_commit=COMMIT,scope='304 stored frequency partials of four map16 endpoints; 4 cross-history combinations; no solver or new map',sources=sources,external_frequency_sources=locations,code=code,energy_diagnostic_sha256=digest(energy_path),energy_review_sha256=digest(energy_review_path),quadrature_weight_relative_error=weight_error,endpoint_checks=checks,comparisons=output,new_slurm=0,new_maps=0,new_feedback=0,new_material=0,accepted20=True,baseline_replaced=False,strict_error_bound=False,causal_attribution=False)
    with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with csvpath.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]),lineterminator='\n');w.writeheader();w.writerows(csvrows)
    print(json.dumps({k:{n:v for n,v in r.items() if n!='blocks'} for k,r in output.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);main(p.parse_args().target)
