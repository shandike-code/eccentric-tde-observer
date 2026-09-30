"""Independent 70-digit candidate witness; no optimizer or witness kernel imported."""
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_operator import old, read, arrays

ROOT=Path.cwd()
RUN=ROOT/'outputs/review-20260925/x20-window-candidate-20260930'
SOURCE=ROOT/'outputs/review-20260925/x20-basis-82166-received'
D=lambda x:Decimal.from_float(float(x))


def numbers(gram,spectra,result):
    raw=result['raw_coefficients'];selected=result['selected_coefficients']
    assert len(raw)==len(selected)==3 and all(math.isfinite(x) for x in raw+selected)
    np.testing.assert_array_equal(selected,.9*np.array(raw))
    assert result['full_fraction']==.9 and result['half_fraction']==.45
    assert not result['full_field_positivity_and_linf_evaluated'] and not result['true_maps_evaluated']
    answers=[]
    with localcontext() as ctx:
        ctx.prec=70
        weights=[D(raw[0]),1-sum(map(D,raw)),*map(D,raw[1:])]
        assert sum(map(abs,weights))<=17
        fs=[[D(x) for x in row] for row in spectra]
        b,c=fs[1:3];scale=max(sum(b),sum(c));orig=[sum(abs(y-x) for x,y in zip(b,c))/scale,abs(sum(c)-sum(b))/scale]
        gd=[[D(x)/D(gram[0,0]) for x in row] for row in gram]
        for index,t in enumerate((D(.9),D(.45))):
            co=[t*D(x) for x in raw];incoming=[];outgoing=[]
            for nu in range(len(b)):
                incoming.append(b[nu]+sum(z*(fs[i][nu]-b[nu]) for z,i in zip(co,(0,4,6))))
                outgoing.append(c[nu]+sum(z*(fs[i][nu]-c[nu]) for z,i in zip(co,(3,5,7))))
            assert min(incoming)>=0 and min(outgoing)>=0
            den=max(sum(incoming),sum(outgoing));difference=[y-x for x,y in zip(incoming,outgoing)]
            l1=sum(map(abs,difference))/den;bol=abs(sum(difference))/den
            u=[D(1),*co];q=sum(u[i]*gd[i][j]*u[j] for i in range(4) for j in range(4));assert q>=0
            l2=q.sqrt();saved=result['endpoints'][index]
            assert l2<=(D(.8) if index==0 else D(1+1e-10))
            errors={}
            for key,val,ref in [('boundary_l1',l1,orig[0]),('boundary_bolometric',bol,orig[1])]:
                assert val<D(1e-3) and val<=ref*D(1+1e-10)
                # ARM Mac的longdouble实为float64。大谱相消后的约1e-9量不能
                # 用其自身再乘1e-9当复现容差；按原通量及系数放大计舍入尺度。
                allowance=64*D(np.finfo(np.longdouble).eps)*(1+sum(map(abs,co)))*scale/den
                discrepancy=abs(D(saved[key])-val)
                assert discrepancy<=allowance
                assert abs(D(saved[key+'_ratio'])-val/ref)<=allowance/ref
                errors[key]=dict(absolute_difference=str(discrepancy),reproduction_allowance=str(allowance))
            assert abs(q-Decimal(saved['squared_l2_70digit']))<Decimal('1e-40')
            answers.append(dict(l2_ratio=str(l2),boundary_l1_ratio=str(l1/orig[0]),boundary_bolometric_ratio=str(bol/orig[1]),positive_spectra=True,reproduction_errors=errors))
        assert result['available_gates_passed'] and all(result['checks'].values())
    return dict(endpoints=answers,raw_coefficients=raw,selected_coefficients=selected,raw_weight_l1=result['raw_weight_l1'],
        independent_70digit_spectral_witness=True,full_field_gates_pending=True,true_maps_pending=True,
        accepted_outer_steps=20,new_material_steps=0,physical_model_nonexistence=False)


def main():
    declaration=read(RUN/'declaration.json');result=read(RUN/'result.json')
    for c in declaration['source_claims']+declaration['code']:old.verify_claim(c,ROOT/c['path'])
    assert declaration['source_job']==82166
    assert declaration['fixed_phase']==1367 and declaration['fixed_dt_s']==889.419892762322
    for key in ('new_maps','new_feedback_pairs','new_material_steps'):assert result[key]==declaration[key]==0
    data=read(SOURCE/'basis.json');gram=np.array(data['gram']);spectra=np.concatenate([np.array(r['boundary_spectra']) for r in data['slabs']],axis=1)[[2,0,1,3,4,5,6,7]];review=numbers(gram,spectra,result)
    review.update(source_job=82166,result_sha256=old.digest(RUN/'result.json'),
        declaration_sha256=old.digest(RUN/'declaration.json'),wall_s=result['wall_s'])
    Path('handoff/evidence/20260930-x20-window-candidate-review.json').write_text(json.dumps(review,indent=2,allow_nan=False)+'\n')
    # 字节不改写：平台以该SHA读取已审固定系数，不在batch再优化。
    Path('handoff/evidence/20260930-x20-window-candidate-result.json').write_bytes((RUN/'result.json').read_bytes())
    print(json.dumps(review['endpoints'],indent=2))


if __name__=='__main__':main()
