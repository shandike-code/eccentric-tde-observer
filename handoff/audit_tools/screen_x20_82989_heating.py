"""Bounded historical-only heating-defect screen; never writes radiation fields.

The exact certificate refers to Gram products of the stored binary64 diagnostic
energy increments, not to an exact physical operator or full radiation domain.
"""
import json
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_feedback_snapshot import arrays, history, prior, ROOT
from handoff.audit_tools.diagnose_x20_heating_transport import diagnose
from handoff.audit_tools.bounded_window_gram import exact_qp
from handoff.audit_tools.analyze_x20_latest_gram import encode
from handoff.audit_tools.verify_x20_bounded_gram import check
from operations.x20_history_operator import same_operator_config


def run():
    target=Path('handoff/evidence/20261001-x20-82989-heating-screen.json')
    if target.exists():raise FileExistsError(target)
    ev=Path('handoff/evidence')
    source={82989:'x20-historical-seed-feedback-82989-received',82518:'x20-global-feedback-82518-complete-received',82273:'x20-feedback-82273-complete-received'}
    claims=[];trials={};configs=[]
    for job,name in source.items():
        ap=ev/f'{"20260930" if job==82273 else "20261001"}-x20-{job}-final-review.json'
        a=json.loads(ap.read_text());assert a['job_id']==job and a['completed_experiment'] and a['all_original_zero_gates_passed']
        history.source_archive(ROOT/name,ap.name,ROOT)
        trials[job]=arrays(ROOT/name/'historical/trial_material.npz')
        for case in ('historical',):
            cp=ROOT/name/case/'config.json'
            configs.append(json.loads(cp.read_text()))
            claims.append(dict(path=str(cp),sha256=prior.digest(cp)))
        claims.append(dict(path=str(ap),sha256=prior.digest(ap)))
    for config in configs:same_operator_config(configs[0],config)
    trial=trials[82989]
    for t in trials.values():
        for k in trial:np.testing.assert_array_equal(t[k],trial[k])
    dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
    old=arrays(Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'))
    mass=old['cell_mass_g_cm2'];order=[(82989,16),(82989,8),(82518,16),(82273,16)]
    pairs=[];fields=[]
    for job,n in order:
        root=ROOT/source[job]/'historical';folder=root/f'pair{n:02d}'
        mp=root/f'endpoints-map{n:02d}/manifest.json';m=json.loads(mp.read_text())
        r0,r1=m['history_rows'];assert (r0['iteration'],r1['iteration'])==(n-1,n)
        assert r0['input_sha256']==m['endpoints']['previous']['sha256']
        assert r0['output_sha256']==r1['input_sha256']==m['endpoints']['final']['sha256']
        fields.extend(m['endpoints'][e] for e in ('previous','final'))
        claims.append(dict(path=str(mp),sha256=prior.digest(mp)))
        pair=[]
        for e in ('previous','final'):
            p=folder/f'{e}_feedback.npz';q=arrays(p)['half_atomic_rate_heating_erg_s_cm3']
            assert q.shape==rho.shape==(128,) and np.isfinite(q).all() and np.all(rho>0)
            # Keep the actual diagnostic binary64 vectors used by the exact screen.
            pair.append(np.asarray(np.longdouble(dt)*q.astype(np.longdouble)/rho,dtype=float))
            claims.append(dict(path=str(p),sha256=prior.digest(p)))
        pairs.append(pair)
    raw=[[F(float(b))-F(float(a)) for a,b in zip(*pair)] for pair in pairs]
    basis=[raw[0]]+[[b-a for a,b in zip(raw[0],r)] for r in raw[1:]]
    mw=list(map(lambda v:F(float(v)),mass));den=sum(mw)
    gram=[[sum(w*a*b for w,a,b in zip(mw,vi,vj))/den for vj in basis] for vi in basis]
    fitted=exact_qp(gram,cap=17);encoded=encode(fitted,gram)
    check(gram,encoded) # determinant and vertex supporting-plane check, not another solve
    c=fitted['coefficients'];selected=[float(F(9,10)*v) for v in c]
    sq=sum(gram[i][j]*([F(1)]+list(map(F,selected)))[i]*([F(1)]+list(map(F,selected)))[j] for i in range(4) for j in range(4))
    ratios=dict(raw=float(fitted['value']/gram[0][0])**.5,selected=float(sq/gram[0][0])**.5)
    one={f'{j}-H{n}':diagnose(*pairs[0],*pair,mass) for (j,n),pair in zip(order[1:],pairs[1:])}
    result=dict(source_claims=claims,field_order=[f'{j}-H{n}-previous/final' for j,n in order],fields=fields,
        quantity='dt * atomic heating / rho',units='erg/g',mass_weights=mass.tolist(),
        stored_binary64_feedback_energy_pairs=[[v.tolist() for v in p] for p in pairs],
        exact_stored_vector_gram=[[dict(numerator=str(x.numerator),denominator=str(x.denominator)) for x in r] for r in gram],
        bounded_solution=encoded,independent_supporting_plane_check=True,coefficient_l1_cap=17,
        selected_coefficients=selected,step_safety=.9,predicted_heating_defect_ratios=ratios,
        historical_single_direction=one,screening_only=True,full_field_positivity_checked=False,
        field_l2_benefit_checked=False,boundary_checked=False,candidate_written=False,true_map_evaluated=False,
        new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,
        physical_solution_existence_claimed=False)
    with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(ratios=ratios,coefficients=selected,raw=encoded['coefficients_float'],weight=encoded['weight_l1'],screening_only=True)))


if __name__=='__main__':run()
