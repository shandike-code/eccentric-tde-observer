"""Stored-array energy/encoding audit; never calls the population solver or reads dat."""
import argparse
import hashlib
import itertools
import json
import subprocess
from pathlib import Path

import numpy as np

from eccentric_tde_observer.atmosphere import PROTON_MASS_G, SOLAR_FULLY_IONIZED_H_HE
from eccentric_tde_observer.non_gray import (
    HYDROGEN_IONIZATION_ERG, HELIUM_I_IONIZATION_ERG, HELIUM_II_IONIZATION_ERG,
)
from eccentric_tde_observer.radiation import BOLTZMANN_ERG_K

ROOT = Path('outputs/review-20260925')
RECEIVED = ROOT / 'x20-85875-matched-85889-received'
COMMIT = '9555a78a77b9025e30405684dee2669d9e43baee'
STEM = 'complete-1791262858167332668'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_file(path, claim):
    if str(path).endswith('.dat'):
        raise ValueError('large field is outside this audit')
    if Path(path).stat().st_size != claim['size_bytes'] or digest(path) != claim['sha256']:
        raise ValueError('source bytes changed: ' + str(path))


def arrays(path):
    with np.load(path, allow_pickle=False) as z:
        result = {k: np.array(z[k]) for k in z.files}
    # 旧层含文本来源元数据；有限性检查只作用于数值数组，不删除元数据。
    if any(v.dtype.kind not in 'biufUS' for v in result.values()):
        raise ValueError('unsupported array dtype: ' + str(path))
    if not all(np.isfinite(v).all() for v in result.values() if v.dtype.kind in 'biuf'):
        raise ValueError('nonfinite input: ' + str(path))
    return result


def energy_parts(temperature, hydrogen, helium):
    """独立展开热比能与基态电离比能，单位均为 erg/g。"""
    t, h, he = map(np.asarray, (temperature, hydrogen, helium))
    if t.ndim != 1 or h.shape != (t.size, 2) or he.shape != (t.size, 3):
        raise ValueError('material shapes')
    if not all(np.isfinite(v).all() for v in (t, h, he)) or np.any(t <= 0) or np.any(h <= 0) or np.any(he <= 0):
        raise ValueError('material domain')
    np.testing.assert_allclose(h.sum(1), 1, rtol=0, atol=128*np.finfo(float).eps)
    np.testing.assert_allclose(he.sum(1), 1, rtol=0, atol=128*np.finfo(float).eps)
    composition = SOLAR_FULLY_IONIZED_H_HE
    nh = composition.hydrogen_mass_fraction / PROTON_MASS_G
    nhe = composition.helium_mass_fraction / (4*PROTON_MASS_G)
    coefficient = 1.5*BOLTZMANN_ERG_K*(nh+nhe+nh*h[:, 1]+nhe*(he[:, 1]+2*he[:, 2]))
    gas = coefficient*t
    ion = nh*h[:, 1]*HYDROGEN_IONIZATION_ERG + nhe*(he[:, 1]*HELIUM_I_IONIZATION_ERG + he[:, 2]*(HELIUM_I_IONIZATION_ERG+HELIUM_II_IONIZATION_ERG))
    return gas, ion


def log_secant(gas_a, gas_b):
    """对数割线系数；两热能相等时使用解析极限 1/u，不添加 floor。"""
    a, b = np.asarray(gas_a), np.asarray(gas_b)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all() or np.any(a <= 0) or np.any(b <= 0):
        raise ValueError('gas domain')
    delta = b-a
    result = 1/a
    different = delta != 0
    result[different] = np.log1p(delta[different]/a[different])/delta[different]
    if not np.isfinite(result).all() or np.any(result <= 0):
        raise ValueError('log secant not representable')
    return result


def norms(delta, mass):
    v = np.asarray(delta).reshape(-1, 4)
    return np.array([np.sqrt(np.sum(v*v)), np.sqrt(np.sum(mass[:, None]*v*v)/mass.sum()), np.sqrt(np.max(np.sum(v*v, axis=1)))])


def mass_norm(v, mass):
    return float(np.sqrt(np.sum(mass*v*v)/mass.sum()))


def run(target):
    if target.exists():
        raise FileExistsError(target)
    inventory = json.loads((ROOT/(STEM+'.json')).read_text())
    claims = {c['path']: c for c in inventory['files']}
    sources = []
    def load(rel):
        p = RECEIVED/rel
        verify_file(p, claims[rel]); sources.append(dict(path=str(p), **{k:claims[rel][k] for k in ['size_bytes','sha256']}))
        return arrays(p)
    audit_path = Path('handoff/evidence/20261006-x20-85889-final-review.json')
    audit = json.loads(audit_path.read_text())
    assert audit['numerical_commit'] == COMMIT and audit['scheduler_terminal_verified'] and audit['numerical_artifacts_complete']
    assert not audit['reference_calibration_eligible']
    # 绑定已审完整清单与数值提交；不重新执行已完成的大场实验。
    archived_manifest = RECEIVED/'archive-manifest.json'
    if archived_manifest.exists():
        assert json.loads(archived_manifest.read_text()) == inventory
    code = []
    for rel in ['src/eccentric_tde_observer/atmosphere.py', 'src/eccentric_tde_observer/non_gray.py', 'src/eccentric_tde_observer/radiation.py', 'src/eccentric_tde_observer/radiation_matter_feedback.py', 'src/eccentric_tde_observer/coupled_material_newton_krylov.py', 'scripts/phase7b9_formal_feedback_pair_adapter.py']:
        frozen = subprocess.check_output(['git', 'show', COMMIT+':'+rel])
        assert Path(rel).read_bytes() == frozen
        code.append(dict(path=rel, sha256=hashlib.sha256(frozen).hexdigest()))
    trial = load('inputs/trial_material.npz')
    old_path = Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    assert digest(old_path) == '33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455'
    old = arrays(old_path); phase = int(trial['phase_index']); dt = float(trial['step_duration_s'])
    assert phase == 1367 and dt == 889.419892762322 and dt == float(old['step_duration_s'][phase])
    rho = trial['density_g_cm3']; mass = old['cell_mass_g_cm2']; edges = old['mass_fraction_edges']
    assert rho.shape == mass.shape == (128,) and edges.shape == (129,)
    assert np.all(rho > 0) and np.all(mass > 0) and np.all(np.diff(edges) > 0)
    np.testing.assert_array_equal(rho, old['density_g_cm3'][phase])
    old_gas, old_ion = energy_parts(old['temperature_k'][phase], old['hydrogen_fraction'][phase], old['helium_fraction'][phase])
    states = {}; checks = {}; widths = None
    for branch, n, endpoint in itertools.product(['accelerated','historical'], [8,16], ['previous','final']):
        key = f'{branch}{n}_{endpoint}'; base=f'{branch}/pair{n:02d}/'
        f = load(base+endpoint+'_feedback.npz'); response = load(base+endpoint+'_response.npz')
        if widths is None: widths=f['subcell_width_cm']
        np.testing.assert_array_equal(widths, f['subcell_width_cm']); assert widths.shape == (4096,) and np.all(widths>0)
        # 按生产核重建16子层算术均值与前128父层；同时记录子层宽度是否均匀。
        for name in [k[5:] for k in f if k.startswith('half_')]:
            parent = f[name].reshape(256,16,*f[name].shape[1:]).mean(1)
            np.testing.assert_array_equal(parent, f['parent_'+name])
            np.testing.assert_array_equal(parent[:128], f['half_'+name])
        gas, ion = energy_parts(response['temperature_k'], response['hydrogen_fraction'], response['helium_fraction'])
        q = f['half_atomic_rate_heating_erg_s_cm3']; heat = dt*q/rho
        expected = old_gas+old_ion+heat; target_energy=response['target_specific_material_energy_erg_g']
        target_error=float(np.max(np.abs(expected-target_energy)/(np.abs(expected)+np.abs(target_energy))))
        recovery_error=float(np.max(np.abs(gas+ion-target_energy)/(gas+ion+np.abs(target_energy))))
        assert target_error < 32*np.finfo(float).eps and recovery_error < 32*np.finfo(float).eps
        h=response['hydrogen_fraction']; he=response['helium_fraction']
        encoded=np.column_stack([np.log(gas),np.log(h[:,1]/h[:,0]),np.log(he[:,1]/he[:,0]),np.log(he[:,2]/he[:,0])]).reshape(-1)
        codec_error=float(np.max(np.abs(encoded-trial['encoded_state']-response['residual'])))
        assert codec_error < 2e-13
        states[key]=dict(gas=gas,ion=ion,heat=heat,q=q,residual=response['residual'],fine_q=f['atomic_rate_heating_erg_s_cm3'])
        checks[key]=dict(target_energy_symmetric_relative_error=target_error,recovered_energy_symmetric_relative_error=recovery_error,codec_max_abs_error=codec_error,minimum_gas_erg_g=float(gas.min()))
    r20_path=ROOT/'common-step21-76808-received/inputs/base_residual.npy'
    assert digest(r20_path)=='b6f337ce30d323acada31ea9f3e1772ccb2be1075753f432ab13a8e299ee2a45'
    r20_norm=norms(np.load(r20_path,allow_pickle=False),mass)
    scale=np.array([.02929545590160747,.0015563020846738518,.015995237347141762])
    groups={f'cross{n}':(f'accelerated{n}',f'historical{n}') for n in [8,16]}
    groups.update({b+'_window':(b+'8',b+'16') for b in ['accelerated','historical']})
    comparisons={}
    for group,(a_label,b_label) in groups.items():
        records={}
        expected_comparison=audit['cross_history'][group[5:]]['residual_comparison'] if group.startswith('cross') else audit['pairs'][b_label]['eight_map_window']
        for a_end,b_end in itertools.product(['previous','final'],repeat=2):
            a=states[a_label+'_'+a_end]; b=states[b_label+'_'+b_end]; label=b_end+'_vs_'+a_end
            du=b['gas']-a['gas']; dh=b['heat']-a['heat']; di=b['ion']-a['ion']
            energy_error=float(np.max(np.abs(du-(dh-di))/(a['gas']+b['gas']+np.abs(dh)+np.abs(di))))
            assert energy_error < 64*np.finfo(float).eps
            # 割线分解是同一实际两端点的恒等式，不是更换加热/布居后的反事实求解。
            g=log_secant(a['gas'],b['gas']); heat_log=g*dh; ion_log=-g*di
            delta=b['residual']-a['residual']; delta0=delta.reshape(128,4)[:,0]
            log_error=float(np.max(np.abs(delta0-heat_log-ion_log))); assert log_error < 4e-13
            nn=norms(delta,mass)
            np.testing.assert_allclose(nn/r20_norm,expected_comparison['frozen_r20']['vector_difference_over_frozen_r20_norms'][label],rtol=2e-12,atol=0)
            np.testing.assert_allclose(nn/scale,expected_comparison['vector_difference_over_frozen_80195_signal'][label],rtol=2e-12,atol=0)
            cell_power=mass*np.sum(delta.reshape(128,4)**2,axis=1); total=cell_power.sum(); order=np.argsort(-cell_power)
            fine_num=widths*np.abs(b['fine_q']-a['fine_q']); fine_den=widths*np.maximum(np.abs(a['fine_q']),np.abs(b['fine_q']))
            assert total>0 and fine_den.sum()>0
            full_norm=mass_norm(delta0,mass)
            cells=[]
            for i in range(128):
                cells.append(dict(index=i,mass_fraction_interval=edges[i:i+2].tolist(),mass_g_cm2=float(mass[i]),density_g_cm3=float(rho[i]),gas_a_erg_g=float(a['gas'][i]),gas_b_erg_g=float(b['gas'][i]),delta_heat_erg_g=float(dh[i]),delta_ion_erg_g=float(di[i]),delta_log_gas=float(delta0[i]),heating_log_contribution=float(heat_log[i]),ionization_log_contribution=float(ion_log[i]),mass_norm_squared_fraction=float(cell_power[i]/total)))
            records[label]=dict(norms=nn.tolist(),over_r20=(nn/r20_norm).tolist(),over_signal=(nn/scale).tolist(),energy_identity_error=energy_error,log_identity_max_abs_error=log_error,gas_component_fraction=float(np.sum(mass*delta0**2)/total),heating_log_mass_norm=mass_norm(heat_log,mass),ionization_log_mass_norm=mass_norm(ion_log,mass),gas_log_mass_norm=full_norm,ionization_to_gas_log_mass_norm=mass_norm(ion_log,mass)/full_norm,heating_to_gas_log_mass_norm=mass_norm(heat_log,mass)/full_norm,cross_term_mass_mean=float(2*np.sum(mass*heat_log*ion_log)/mass.sum()),atomic_heating_volume_l1=float(fine_num.sum()/fine_den.sum()),top5_cells=order[:5].tolist(),top5_mass_norm_squared_fraction=float(cell_power[order[:5]].sum()/total),cells=cells)
        comparisons[group]=records
    out=dict(job_id=85889,scope='stored-array algebra only; 8 endpoints, 16 comparisons; no ODE or large field recomputation',numerical_commit=COMMIT,source_final_audit=dict(path=str(audit_path),sha256=digest(audit_path)),archive_manifest_sha256=digest(ROOT/(STEM+'.json')),sources=sources,code=code,external_small_sources=[dict(path=str(old_path),sha256=digest(old_path)),dict(path=str(r20_path),sha256=digest(r20_path))],endpoint_checks=checks,maximum_relative_width_spread_within_parent=float(np.max(np.ptp(widths.reshape(256,16),axis=1)/np.mean(widths.reshape(256,16),axis=1))),comparisons=comparisons,accepted_outer_steps=20,new_material_steps=0,new_maps=0,new_feedback_pairs=0,reference_calibration_eligible=False,baseline_replaced=False,strict_error_bound=False,not_a_causal_decomposition=True)
    with target.open('x') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(target=str(target),endpoint_checks=checks,comparisons={k:{label:{x:v[x] for x in ['gas_component_fraction','heating_to_gas_log_mass_norm','ionization_to_gas_log_mass_norm','top5_cells','top5_mass_norm_squared_fraction','atomic_heating_volume_l1']} for label,v in rows.items()} for k,rows in comparisons.items()}),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);run(p.parse_args().target)
