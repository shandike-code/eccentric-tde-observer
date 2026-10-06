"""Audit all stored map8/map16 blocks and their finite signed changes; no solver."""
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
    arraypath = target.with_suffix('.npz')
    if target.exists() or csvpath.exists() or arraypath.exists():
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
    for branch, n, end in itertools.product(['accelerated','historical'],[8,16],['previous','final']):
        base=f'{branch}/pair{n:02d}/'; protocol=load(base+'feedback_protocol.json')
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
        states[f'{branch}{n}_{end}']={k:np.array(v) for k,v in partials.items()}
        checks[f'{branch}{n}_{end}']=dict(blocks=76,groups=9632,fields=len(combined),all_fields_sum_bitwise=True,nonformal_legacy_bitwise=True,atomic_equals_absorbed_minus_emitted_bitwise=True)
    prior_review_path=Path('handoff/evidence/20261006-x20-85889-frequency-review.json')
    prior_review=json.loads(prior_review_path.read_text())
    prior_path=ROOT/'20261006-x20-85889-frequency-diagnostic.json'
    verify_file(prior_path,next(c for c in prior_review['artifacts'] if c['path']==str(prior_path)))
    prior=json.loads(prior_path.read_text())
    assert prior['energy_diagnostic_sha256']==digest(energy_path)
    assert prior['code']==code and prior['external_frequency_sources']==locations
    intervals_ev=[dict(block=i,start=a,stop=b,left_ev=float(edges[a]*PLANCK_ERG_S/EV_ERG),right_ev=float(edges[b]*PLANCK_ERG_S/EV_ERG)) for i,(a,b) in enumerate(intervals)]
    output={}; saved={}; csvrows=[]
    groups={'cross8':('accelerated8','historical8'),'cross16':('accelerated16','historical16'),
            'accelerated_window':('accelerated8','accelerated16'),'historical_window':('historical8','historical16')}
    mass=None
    for group,(al,bl) in groups.items():
        output[group]={}
        for ae,be in itertools.product(['previous','final'],repeat=2):
            label=be+'_vs_'+ae; key=group+'__'+label
            a,b=states[al+'_'+ae],states[bl+'_'+be]
            cells=energy['comparisons'][group][label]['cells']
            current_mass=np.array([c['mass_g_cm2'] for c in cells])
            if mass is None: mass=current_mass
            np.testing.assert_array_equal(mass,current_mass)
            np.testing.assert_array_equal(rho,np.array([c['density_g_cm3'] for c in cells]))
            g=log_secant(np.array([c['gas_a_erg_g'] for c in cells]),np.array([c['gas_b_erg_g'] for c in cells]))
            dq=b[Q]-a[Q]; da=b[ABS]-a[ABS]; de=b[EM]-a[EM]
            hp=dt*dq/rho[None,:]; lp=log_parts(g,dt,dq,rho)
            target_heat=np.array([c['heating_log_contribution'] for c in cells])
            err=float(np.max(np.abs(lp.sum(0)-target_heat)))
            assert err<4e-13, (group,label,err)
            if group=='cross16':
                previous=prior['comparisons'][label]['blocks']
                np.testing.assert_array_equal(dq,np.array([r['delta_half_q_erg_s_cm3'] for r in previous]))
                # 严格保留前轮乘除顺序，避免极小数中间乘积的舍入差。
                np.testing.assert_array_equal(lp,np.array([r['log_contribution'] for r in previous]))
            stats=describe(lp,mass)
            stats.update(heat_mass_norm_erg_g=mass_norm(hp.sum(0),mass),heating_log_sum_max_abs_error=err,
                         emitted_half_bitwise_equal=np.array_equal(a[EM],b[EM]),
                         net_absorption_emission_max_abs_error=float(np.max(np.abs(dq-(da-de)))))
            output[group][label]=stats
            for name,v in [('delta_q',dq),('delta_absorbed',da),('delta_emitted',de),('delta_h',hp),('log_contribution',lp)]:saved[key+'__'+name]=v
            for i,interval in enumerate(intervals_ev):
                csvrows.append(dict(comparison=key,**interval,projection=stats['signed_projection'][i],block_mass_norm=mass_norm(lp[i],mass),norm_unit='dimensionless'))
    evolution={}
    for a8,a16,h8,h16 in itertools.product(['previous','final'],repeat=4):
        label=f'A8_{a8}__A16_{a16}__H8_{h8}__H16_{h16}'
        qa8=states['accelerated8_'+a8][Q]; qa16=states['accelerated16_'+a16][Q]
        qh8=states['historical8_'+h8][Q]; qh16=states['historical16_'+h16][Q]
        # 在同一比能坐标比较差值，避免不同端点割线g混入逐块恒等式。
        c8=dt*(qh8-qa8)/rho; c16=dt*(qh16-qa16)/rho
        wa=dt*(qa16-qa8)/rho; wh=dt*(qh16-qh8)/rho
        change=c16-c8; alternate=wh-wa
        identity_error=float(np.max(np.abs(change-alternate)))
        identity_scale=np.abs(c8)+np.abs(c16)+np.abs(wa)+np.abs(wh)
        assert np.all(np.abs(change-alternate)<=32*np.finfo(float).eps*identity_scale)
        stats=describe(change,mass)
        v8,v16,d=c8.sum(0),c16.sum(0),change.sum(0)
        n8=mass_norm(v8,mass); n16=mass_norm(v16,mass)
        stats.update(cross16_over_cross8_heat_mass_norm=n16/n8 if n8 else None,
                     change_over_cross8_heat_mass_norm=mass_norm(d,mass)/n8 if n8 else None,
                     change_projection_on_cross8=inner(d,v8,mass)/inner(v8,v8,mass) if n8 else None,
                     cross8_cross16_cosine=inner(v8,v16,mass)/(n8*n16) if n8 and n16 else None,
                     identity_max_abs_error_erg_g=identity_error,
                     a_window_projection_on_cross8=inner(wa.sum(0),v8,mass)/(n8*n8) if n8 else None,
                     h_window_projection_on_cross8=inner(wh.sum(0),v8,mass)/(n8*n8) if n8 else None)
        evolution[label]=stats
        for name,v in [('cross8_h',c8),('cross16_h',c16),('a_window_h',wa),('h_window_h',wh),('change_h',change)]:saved['evolution__'+label+'__'+name]=v
        for i,interval in enumerate(intervals_ev):
            csvrows.append(dict(comparison='evolution__'+label,**interval,projection=stats['signed_projection'][i],block_mass_norm=mass_norm(change[i],mass),norm_unit='erg/g'))
    saved['mass_g_cm2']=mass; saved['density_g_cm3']=rho
    for name,state in states.items():
        for field,v in state.items():saved['endpoint__'+name+'__'+field]=v
    assert all(np.isfinite(v).all() for v in saved.values())
    with arraypath.open('xb') as f:np.savez_compressed(f,**saved)
    result=dict(job_id=85889,numerical_commit=COMMIT,scope='608 stored blocks, 8 endpoints, 16 comparisons and 16 endpoint quartets; map16 re-audited, no solver',
                sources=sources,code=code,external_frequency_sources=locations,archive_manifest_sha256=digest(inventory_path),
                energy_diagnostic_sha256=digest(energy_path),prior_frequency_review_sha256=digest(prior_review_path),prior_frequency_diagnostic_sha256=digest(prior_path),
                endpoint_checks=checks,intervals=intervals_ev,comparisons=output,evolution=evolution,
                arrays=dict(path=str(arraypath),sha256=digest(arraypath),size_bytes=arraypath.stat().st_size),
                new_slurm=0,new_maps=0,new_feedback=0,new_material=0,accepted_outer_steps=20,reference_calibration_eligible=False,baseline_replaced=False,strict_error_bound=False)
    with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with csvpath.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]),lineterminator='\n');w.writeheader();w.writerows(csvrows)
    print(json.dumps(dict(endpoints=len(checks),source_records=len(sources),comparisons=16,quartets=len(evolution),arrays=len(saved),target=str(target)),indent=2))


def log_parts(g,dt,dq,rho):
    """沿前轮 g*dt*deltaQ/rho 顺序复现，不重新结合乘除。"""
    return g[None,:]*dt*dq/rho[None,:]


def inner(a,b,mass):
    a,b,mass=map(np.asarray,(a,b,mass))
    if a.shape!=b.shape or a.shape!=mass.shape or not all(np.isfinite(x).all() for x in (a,b,mass)) or np.any(mass<=0):
        raise ValueError('mass inner product domain')
    return float(np.sum(mass*a*b)/np.sum(mass))


def describe(parts,mass):
    total=np.sum(parts,axis=0); share=projection(parts,total,mass)
    norm=mass_norm(total,mass)
    norms=np.array([mass_norm(v,mass) for v in parts])
    if share is None:
        return dict(signed_projection=[None]*len(parts),total_mass_norm=norm,sum_block_norm_over_total_norm=None,top10=[],positive_projection_sum=None,negative_projection_sum=None)
    np.testing.assert_allclose(share.sum(),1,rtol=0,atol=5e-13)
    return dict(signed_projection=share.tolist(),total_mass_norm=norm,sum_block_norm_over_total_norm=float(norms.sum()/norm),
                top10=np.argsort(-np.abs(share))[:10].tolist(),positive_projection_sum=float(share[share>0].sum()),negative_projection_sum=float(share[share<0].sum()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);main(p.parse_args().target)
