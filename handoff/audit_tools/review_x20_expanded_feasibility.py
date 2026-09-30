"""Independent four-dimensional dual/cut audit; no production optimizer imported."""
import itertools,json,math
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_spectral import D,dot,linear
from handoff.audit_tools.review_x20_operator import old,read,arrays

ROOT=Path.cwd();RUN=ROOT/'outputs/review-20260925/x20-expanded-feasibility-20260930'
SOURCE=ROOT/'outputs/review-20260925/x20-long-chord-81647-received'


def cap_halfspaces():
    return [([D(s[i]-s[1]) for i in (0,2,3,4)],D(17-s[1])) for s in itertools.product((-1,1),repeat=5)]


def cap_vertices():
    points=[]
    for i,j in itertools.permutations(range(5),2):
        w=[D(0)]*5;w[i]=D(9);w[j]=D(-8)
        points.append([w[k] for k in (0,2,3,4)])
    return points


def numbers(g,fs,result):
    a,b,c,h,j,k,x,y=fs;scale=max(math.fsum(b),math.fsum(c));r=(c-b)/scale;base=b/scale
    directions=np.stack(((b-a)-(c-b),(j-h)-(c-b),(k-j)-(c-b),(y-x)-(c-b)),axis=1)/scale
    input_directions=np.stack((a-b,h-b,j-b,x-b),axis=1)/scale
    limit=math.fsum(abs(r))*(1+1e-10);assert result['boundary_limit']==limit
    cap=[(row,bound) for row,bound in cap_halfspaces() if any(row)]
    aa=[row for row,_ in cap];bb=[bound for _,bound in cap];trace=[]
    with localcontext() as ctx:
        ctx.prec=70
        gram=[[D(v)/D(g[0,0]) for v in row] for row in g]
        # 正定性用70位LDL主元核实，支撑平面不依赖浮点优化器宣称凸性。
        hessian=[row[1:].copy() for row in gram[1:]];pivots=[]
        for n in range(4):
            pivot=hessian[n][n];assert pivot>0;pivots.append(str(pivot))
            for i in range(n+1,4):
                for j in range(n+1,4):hessian[i][j]-=hessian[i][n]*hessian[n][j]/pivot
        assert pivots==result['positive_hessian_ldl_pivots']
        vertices=cap_vertices();assert len(vertices)==20
        r0=sum(map(D,r));f0=sum(map(D,base));di=[sum(map(D,x)) for x in input_directions.T];dr=[sum(map(D,x)) for x in directions.T]
        for tfloat,saved in zip((.9,.45),result['denominator_bounds']):
            t=D(tfloat);values=[]
            for v in vertices:
                fin=f0+t*dot(v,di);fout=fin+r0+t*dot(v,dr);values.extend((fin,fout))
            maximum=max(values)
            assert D(saved['upper'])>=maximum
            assert abs(maximum-Decimal(saved['maximum_70digit']))<Decimal('1e-45')
        for row in result['trace']:
            assert row['a']==[[float(x) for x in z] for z in aa] and row['b']==list(map(float,bb))
            point=list(map(D,row['point']));u=[D(1)]+[D(.9)*x for x in point]
            q=sum(u[i]*gram[i][j]*u[j] for i in range(5) for j in range(5))
            grad=[2*D(.9)*dot(gram[i+1],u) for i in range(4)]
            # 独立重算对偶余项；无需相信LP最优性或SLSQP的success。
            cert=row['certificate'];y=list(map(D,cert['dual_multipliers']))
            assert abs(q-Decimal(cert['squared_value_70digit']))<Decimal('1e-40')
            assert all(z<=0 for z in y) and all(z==min(D(raw),D(0)) for z,raw in zip(y,cert['raw_dual_multipliers']))
            residual=[grad[j]-sum(z*a[j] for z,a in zip(y,aa)) for j in range(4)]
            correction=9*sum(map(abs,residual));dual=q-dot(grad,point)+dot(y,bb)-correction-Decimal(cert['decimal_allowance'])
            assert abs(dual-Decimal(cert['squared_lower_70digit']))<Decimal('1e-40')
            assert Decimal(cert['decimal_allowance'])>0
            assert abs(correction-Decimal(cert['residual_box_correction_70digit']))<Decimal('1e-40')
            assert cert['l2_lower']<=float(dual.sqrt()) if dual>0 else cert['l2_lower']==0
            new=[];ratios=[]
            for tfloat,den,cut in zip((.9,.45),result['denominator_bounds'],row['cuts']):
                t=D(tfloat);v=r+tfloat*(directions@np.array(row['point']));sign=np.sign(v);lim=D(limit)
                coeff=[t*sum(D(s)*D(z) for s,z in zip(sign,col))/lim for col in directions.T]
                bound=D(den['upper'])-sum(D(s)*D(z) for s,z in zip(sign,r))/lim
                stored=list(map(D,cut['a']));saved_b=D(cut['b'])
                assert saved_b-bound>=9*sum(abs(x-y) for x,y in zip(stored,coeff))
                ratio=math.fsum(abs(v))/(limit*den['upper']);assert math.isclose(ratio,cut['relaxed_ratio'],rel_tol=1e-13)
                actual_den=float(f0)+tfloat*math.fsum(np.array(row['point'])*np.array(list(map(float,di))))+max(math.fsum(v),0.)
                assert math.isclose(actual_den,cut['exact_denominator'],rel_tol=1e-13)
                assert np.count_nonzero(v>0)==cut['positive_groups'] and np.count_nonzero(v<0)==cut['negative_groups']
                ratios.append(ratio)
                if ratio>1:new.append((stored,saved_b))
            trace.append(dict(iteration=row['iteration'],verified_dual_squared_lower=str(dual),spectral_relaxed_ratios=ratios))
            for z,t in new:aa.append(z);bb.append(t)
        assert result['status']=='cut_iteration_budget_exhausted' and len(trace)==64 and dual<Decimal('.64')
    return dict(trace=trace,decimal_precision=70,positive_hessian_ldl_pivots=pivots,
        no_20pct_candidate_in_full_registered_cap=False, unresolved_boundary_precision=True,physical_model_nonexistence=False,
        scope='four measured directions, raw affine-weight L1 cap17, full/half fractions0.9/0.45')


def main():
    declaration=read(RUN/'declaration.json');result=read(RUN/'result.json')
    for c in declaration['source_files']+declaration['code']+[declaration[k] for k in ('source_audit','source_archive','source_manifest')]:old.verify_claim(c,ROOT/c['path'])
    assert declaration['source_job']==81647 and declaration['source_basis']==read(SOURCE/'expanded-basis.json')
    assert declaration['maximum_cut_iterations']==64 and declaration['accepted_outer_steps']==20
    for key in ('large_fields_read','new_maps','new_feedback_pairs','new_material_steps'):assert declaration[key]==result[key]==0
    assert not declaration['baseline_replaced'] and not result['baseline_replaced'] and not result['candidate_written']
    assert result['coefficient_l1_cap']==17 and result['full_fraction']==.9 and result['half_fraction']==.45 and not result['zero_net_boundary_equality_used']
    data=arrays(SOURCE/'expanded-system.npz');assert data['spectra'].shape==(8,9632) and data['gram'].shape==(5,5)
    review=numbers(data['gram'],data['spectra'],result)
    review.update(source_job=81647,run=str(RUN.relative_to(ROOT)),result_sha256=old.digest(RUN/'result.json'),
        declaration_sha256=old.digest(RUN/'declaration.json'),independent_dual_and_cut_audit=True,
        large_fields_recomputed=False,strict_physical_error_bound=False,accepted_outer_steps=20,new_material_steps=0,wall_s=result['wall_s'])
    Path('handoff/evidence/20260930-x20-expanded-feasibility-review.json').write_text(json.dumps(review,indent=2)+'\n');print(json.dumps(dict(status=result['status'],rounds=len(review['trace']),last=review['trace'][-1]),indent=2))


if __name__=='__main__':main()
