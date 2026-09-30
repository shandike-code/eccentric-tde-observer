import copy
import pytest
from operations.x20_matched_chord_proposal import require_scan


def source():
    totals={k:{x:1. for x in ('dd','de','ee','rayleigh_action','mapped_difference_l2_ratio')} for k in ('8','16')}
    a=dict(job_id=82039,source_job=81769,independent_slab_reduction=True,source_code_and_field_claims_verified=True,new_maps=0,new_material_steps=0,baseline_replaced=False,results={k:dict(total=v) for k,v in totals.items()})
    d=dict(job_id='82039',shape=[9632,32,4096]);s=dict(status='scan_complete_requires_review',results=copy.deepcopy(totals));t=dict(job_id=82039,state='COMPLETED',scontrol='ExitCode=0:0')
    return a,d,s,t


def test_reviewed_source_accepts_only_reduction_roundoff():
    a,d,s,t=source();s['results']['16']['de']*=1+1e-15;require_scan(a,d,s,t)
    s['results']['16']['de']*=1.1
    with pytest.raises(ValueError):require_scan(a,d,s,t)


@pytest.mark.parametrize('bad',['incomplete','wrong_job','new_map','rebase','missing_audit'])
def test_source_authority_or_budget_change_is_rejected(bad):
    a,d,s,t=source()
    if bad=='incomplete':t['state']='RUNNING'
    elif bad=='wrong_job':d['job_id']='0'
    elif bad=='new_map':a['new_maps']=1
    elif bad=='rebase':a['baseline_replaced']=True
    else:a['independent_slab_reduction']=False
    with pytest.raises(ValueError):require_scan(a,d,s,t)
