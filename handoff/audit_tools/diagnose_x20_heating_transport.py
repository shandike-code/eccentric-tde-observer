"""Read-only, finite secant diagnostics of already audited feedback pairs.

No new transfer evaluation or material update. All differences have units erg/g:
g(J) = dt * Q(J) / rho, with the original dt, density and mass weights.
The fitted scalar minimizes an observed heating defect only. It is not a
physical candidate, an eigenvalue, or a remaining-error bound.
"""
import json
from pathlib import Path

import numpy as np

from handoff.audit_tools.review_x20_feedback_snapshot import arrays, history, prior, ROOT


def diagnose(a, ta, h, th, mass):
    """Use consecutive feedback pairs without subtracting scalar norms."""
    a, ta, h, th, mass = [np.asarray(v, dtype=np.longdouble) for v in (a, ta, h, th, mass)]
    if (a.ndim != 1 or any(v.shape != a.shape for v in (ta, h, th, mass))
            or not all(np.isfinite(v).all() for v in (a, ta, h, th, mass))
            or np.any(mass <= 0)):
        raise ValueError('finite same-shape vectors and positive mass required')
    w = mass / mass.sum()
    def inner(x, y):
        return np.sum(w * x * y, dtype=np.longdouble)
    def norm(x):
        return np.sqrt(inner(x, x))
    ra, rh = ta-a, th-h
    d = h-a
    e = rh-ra
    mapped = th-ta
    # Check the algebra before giving it a scientific interpretation.
    np.testing.assert_allclose(d+e, mapped, rtol=1e-14, atol=0.)
    nd, ne, nr = norm(d), norm(e), norm(ra)
    ee = inner(e, e)
    alpha = None if ee == 0 else -inner(ra, e)/ee
    combined = None if alpha is None else ra+alpha*e
    f = lambda v: None if v is None else float(v)
    return dict(
        mass_norm_d_erg_g=f(nd), mass_norm_e_erg_g=f(ne),
        mass_norm_r_a_erg_g=f(nr), mass_norm_r_h_erg_g=f(norm(rh)),
        mapped_difference_over_difference=f(None if nd == 0 else norm(mapped)/nd),
        change_over_difference=f(None if nd == 0 else ne/nd),
        ray_projection=f(None if nd == 0 else inner(d,mapped)/(nd*nd)),
        defect_cosine=f(None if nr == 0 or ne == 0 else inner(ra,e)/(nr*ne)),
        unconstrained_observed_heating_alpha=f(alpha),
        predicted_heating_defect_ratio=f(None if nr == 0 or combined is None else norm(combined)/nr),
        stationary_inner_product_erg_g_squared=f(None if combined is None else inner(combined,e)),
        d_erg_g=[float(v) for v in d], e_erg_g=[float(v) for v in e],
        r_a_erg_g=[float(v) for v in ra],
        candidate_written=False, full_field_positivity_checked=False,
        true_map_evaluated=False, remaining_error_bound=False,
    )


def run():
    target=Path('handoff/evidence/20261001-x20-heating-transport-comparison.json')
    if target.exists():
        raise FileExistsError(target)
    old=arrays(Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'))
    sources=[(82273, '20260930-x20-82273-final-review.json', 'x20-feedback-82273-complete-received'),
             (82518, '20261001-x20-82518-final-review.json', 'x20-global-feedback-82518-complete-received')]
    results={}
    for job, name, directory in sources:
        ep=Path('handoff/evidence')/name
        audit=json.loads(ep.read_text())
        assert audit['job_id']==job and audit['completed_experiment']
        assert audit['all_original_zero_gates_passed'] and audit['reference_calibration_eligible'] is False
        out=ROOT/directory
        history.source_archive(out,name,ROOT)
        trial=arrays(out/'accelerated/trial_material.npz')
        other=arrays(out/'historical/trial_material.npz')
        for k in trial:
            np.testing.assert_array_equal(trial[k],other[k])
        dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
        assert dt==889.419892762322 and rho.shape==(128,) and np.all(rho>0)
        mass=old['cell_mass_g_cm2']; row={}
        for n in (8,16):
            vectors=[]; claims=[]
            for case in ('accelerated','historical'):
                folder=out/case/f'pair{n:02d}'
                manifest=json.loads((out/case/f'endpoints-map{n:02d}/manifest.json').read_text())
                previous, final = manifest['history_rows']
                assert (previous['iteration'],final['iteration'])==(n-1,n)
                assert previous['input_sha256']==manifest['endpoints']['previous']['sha256']
                assert previous['output_sha256']==final['input_sha256']==manifest['endpoints']['final']['sha256']
                assert final['output_sha256']==manifest['endpoints']['mapped_final']['sha256']
                for end in ('previous','final'):
                    p=folder/f'{end}_feedback.npz'
                    f=arrays(p)
                    q=f['half_atomic_rate_heating_erg_s_cm3']
                    assert q.shape==rho.shape and np.isfinite(q).all()
                    vectors.append(np.longdouble(dt)*q.astype(np.longdouble)/rho)
                    claims.append(dict(path=str(p),sha256=prior.digest(p)))
            row[str(n)]=dict(**diagnose(*vectors,mass),feedback_claims=claims)
        results[str(job)]=dict(audit_sha256=prior.digest(ep),archive=audit['archive'],checkpoints=row)
    result=dict(jobs=results,units='erg/g',quantity='original dt * atomic net heating / fixed density',
                same_mass_weights=True,new_maps=0,new_feedback_pairs=0,new_material_steps=0,
                baseline_replaced=False,source_matter_fixed=True,
                warning='Scalar fit is only an observed heating-defect minimizer; no field feasibility, operator affinity or convergence certification.')
    with target.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    for job,result in results.items():
        for n,row in result['checkpoints'].items():
            print(job,n,json.dumps({k:v for k,v in row.items() if not isinstance(v,list)}))


if __name__=='__main__':
    run()
