"""Three-point quadratic diagnostic, not an interval bound on floating field kernels."""
import hashlib,json,math
from fractions import Fraction as F
from pathlib import Path


def quadratic(s0,sh,sf,h=F(1,8)):
    if h<=0 or min(s0,sh,sf)<=0:raise ValueError('positive step and squared norms required')
    a=(sf-2*sh+s0)/(2*h*h)
    b=(sh-s0-a*h*h)/h
    return a,b,s0


def constrained_minimum(a,b,c,upper):
    if a<=0 or c<=0 or upper<=0:raise ValueError('convex positive diagnostic required')
    t=-b/(2*a)
    t=max(F(0),min(upper,t)) # analytic minimizer over an interval; no field clipping
    return t,(a*t*t+b*t+c)/c


def run():
    root=Path('outputs/review-20260925')
    pp=root/'x20-quarter-prediction-83080-received/prediction.json'
    sp=root/'x20-subnormal-audit-83075-received/exact-signs.json'
    audit=Path('handoff/evidence/20261001-x20-quarter-prediction-83080-review.json')
    assert json.loads(audit.read_text())['result']['checks']['full_l2_benefit'] is False
    p=json.loads(pp.read_text());signs=json.loads(sp.read_text())
    sq=[sum((F(float(r['squared_l2'][i])) for r in p['slabs']),F(0)) for i in range(3)]
    bounds=[F(int(v['numerator']),int(v['denominator'])) for slab in signs['slabs'] for row in slab['checks'] for case in row['cases'] if (v:=case['full_direction_upper_fraction']) is not None]
    upper=min(bounds);a,b,c=quadratic(sq[0],sq[2],sq[1]);t,v=constrained_minimum(a,b,c,upper)
    roots=[float((-float(b)+sgn*math.sqrt(float(b*b-4*a*c*(1-F(16,25)))))/(2*float(a))) for sgn in (-1,1)]
    result=dict(source_claims=[dict(path=str(x),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (pp,sp,audit)],
        method='exact rational interpolation of three stored slab sums; field-expression rounding is not bounded',
        squared_norm_polynomial=[dict(numerator=str(x.numerator),denominator=str(x.denominator)) for x in (a,b,c)],
        local_necessary_upper=dict(numerator=str(upper.numerator),denominator=str(upper.denominator),value=float(upper)),
        minimum_location=float(t),minimum_l2_ratio=math.sqrt(float(v)),lower_threshold_root=min(roots),
        quadratic_model_cannot_reach_original_gate=bool(v>F(16,25)),
        full_field_rounding_error_bounded=False,strict_impossibility_certificate=False,
        decision='do not scan more scalar steps; collect full-field Gram for a new constrained direction',
        new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    target=Path('handoff/evidence/20261001-x20-83080-step-interval.json')
    with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_claims','squared_norm_polynomial')},indent=2))

if __name__=='__main__':run()
