"""Exact signed secant decomposition of archived gas-energy response differences.

No radiation or matter solve; no state modification. Input archive must already
have passed the complete 81769 audit. Components are diagnostic projections,
not positive probabilities or physical luminosity fractions.
"""
import json
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_feedback_snapshot import arrays, prior, history, ROOT


def secant_components(u_a, u_h, radiative, ion, mass):
    """Map additive energy increments to log(u_h/u_a), exactly on this secant."""
    u_a, u_h, radiative, ion, mass = map(np.asarray, (u_a, u_h, radiative, ion, mass))
    if (u_a.shape != u_h.shape or ion.shape != u_a.shape or mass.shape != u_a.shape
            or radiative.ndim != 2 or radiative.shape[1:] != u_a.shape):
        raise ValueError('incompatible energy decomposition shapes')
    if not all(np.isfinite(x).all() for x in (u_a,u_h,radiative,ion,mass)):
        raise ValueError('nonfinite energy decomposition')
    if np.any(u_a <= 0) or np.any(u_h <= 0) or np.any(mass <= 0):
        raise ValueError('nonpositive physical domain')
    du = u_h-u_a
    dq = np.log1p(du/u_a)
    secant = 1/u_a.copy()
    np.divide(dq, du, out=secant, where=du != 0)
    pieces = np.concatenate((radiative, -ion[None,:]), axis=0)*secant
    np.testing.assert_allclose(pieces.sum(axis=0), dq, rtol=2e-8, atol=2e-12)
    denom = np.sum(mass*dq*dq)
    shares = None if denom == 0 else np.sum(pieces*(mass*dq)[None,:],axis=1)/denom
    if shares is not None:
        np.testing.assert_allclose(shares.sum(),1.,rtol=2e-8,atol=2e-12)
    return dq, pieces, shares


def run():
    out = ROOT/'x20-feedback-81769-complete-received'
    evidence = Path('handoff/evidence/20260930-x20-81769-final-review.json')
    audit=json.loads(evidence.read_text())
    assert audit['completed_experiment'] and audit['all_original_zero_gates_passed']
    history.source_archive(out,evidence.name,ROOT)
    trial=arrays(out/'accelerated/trial_material.npz')
    old=arrays(Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'))
    mass=old['cell_mass_g_cm2'];dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
    results={}
    for name,h,a in [('cross08',('historical',8),('accelerated',8)),
                     ('cross16',('historical',16),('accelerated',16)),
                     ('historical_window',('historical',16),('historical',8)),
                     ('accelerated_window',('accelerated',16),('accelerated',8))]:
        # All four combinations retained; final/final is not substituted for gates.
        combinations={}
        for eh in ('previous','final'):
            for ea in ('previous','final'):
                hp=out/h[0]/f'pair{h[1]:02d}';ap=out/a[0]/f'pair{a[1]:02d}'
                hb=arrays(hp/f'{eh}_energy_ledger.npz');ab=arrays(ap/f'{ea}_energy_ledger.npz')
                hf=arrays(hp/f'{eh}_feedback.npz');af=arrays(ap/f'{ea}_feedback.npz')
                for key in ('total_old','gas_old','ion_old'):assert np.array_equal(hb[key],ab[key])
                hm=json.loads((hp/f'feedback/{eh}_manifest.json').read_text())
                am=json.loads((ap/f'feedback/{ea}_manifest.json').read_text())
                deltas=[];entries=[]
                for i,(hr,ar) in enumerate(zip(hm['completed_blocks'],am['completed_blocks'])):
                    assert hr['block_index']==ar['block_index']==i
                    assert (hr['core_group_start'],hr['core_group_stop'])==(ar['core_group_start'],ar['core_group_stop'])
                    xx=arrays(hp/f'feedback/{eh}/block{i:02d}.npz');yy=arrays(ap/f'feedback/{ea}/block{i:02d}.npz')
                    def half(x):return x.reshape(256,16).mean(axis=1)[:128]
                    delta=half(xx['atomic_rate_heating_erg_s_cm3'])-half(yy['atomic_rate_heating_erg_s_cm3'])
                    deltas.append(dt*delta/rho)
                    entries.append(dict(block=i,core_group_start=hr['core_group_start'],core_group_stop=hr['core_group_stop']))
                assert len(deltas)==76
                rad=np.asarray(deltas);di=hb['ion_new']-ab['ion_new']
                np.testing.assert_allclose(rad.sum(axis=0),dt*(hf['half_atomic_rate_heating_erg_s_cm3']-af['half_atomic_rate_heating_erg_s_cm3'])/rho,rtol=2e-8,atol=1.)
                dq,pieces,shares=secant_components(ab['remaining'],hb['remaining'],rad,di,mass)
                full=arrays(hp/f'{eh}_response.npz')['residual']-arrays(ap/f'{ea}_response.npz')['residual']
                np.testing.assert_allclose(dq,full.reshape(128,4)[:,0],rtol=2e-8,atol=2e-12)
                for row,v in zip(entries,shares[:-1]):row['signed_projection_fraction']=float(v)
                radiative_total=rad.sum(axis=0);gas_delta=hb['remaining']-ab['remaining']
                # Domain already checked. Retain signed arrays; do not clip or rank away any term.
                combinations[eh+'_vs_'+ea]=dict(blocks=entries,ionization_signed_projection_fraction=float(shares[-1]),
                    signed_projection_sum=float(shares.sum()),sum_absolute_projection=float(np.abs(shares).sum()),
                    delta_log_gas=dq.tolist(),delta_gas_erg_g=gas_delta.tolist(),radiative_delta_erg_g=radiative_total.tolist(),
                    ionization_delta_erg_g=di.tolist(),maximum_energy_closure_erg_g=float(np.max(np.abs(radiative_total-di-gas_delta))),
                    maximum_log_closure=float(np.max(np.abs(pieces.sum(axis=0)-dq))),
                    emitted_identical=np.array_equal(hf['emitted_power_erg_s_cm3'],af['emitted_power_erg_s_cm3']),
                    note='signed mass-inner-product projections onto total log-gas difference; not luminosity shares; no geometric depth inferred')
        results[name]=combinations
    result=dict(source_audit_sha256=prior.digest(evidence),archive=audit['archive'],comparisons=results,
                all_four_combinations=True,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    target=Path('handoff/evidence/20260930-x20-81769-energy-decomposition.json')
    assert not target.exists()
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for name,c in results.items():
        f=c['final_vs_final'];top=sorted(f['blocks'],key=lambda r:abs(r['signed_projection_fraction']),reverse=True)[:8]
        print(name,json.dumps(dict(top=top,ion=f['ionization_signed_projection_fraction'],closure=f['maximum_log_closure'],emitted_identical=f['emitted_identical'])))


if __name__=='__main__':run()
