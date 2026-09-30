import pytest
from operations.x20_latest_window_basis import require_scan


def records():
    return [dict(job_id=82396,source_job=82273,independent_slab_reduction=True,
                 source_code_and_field_claims_verified=True,new_maps=0,new_material_steps=0,
                 baseline_replaced=False,results={'8':{},'16':{}}),
            dict(job_id='82396',source_job=82273,shape=[9632,32,4096],fields={'8':[],'16':[]}),
            dict(job_id=82396,state='COMPLETED',scontrol='ExitCode=0:0')]


def test_exact_reviewed_scan_can_supply_residual_basis():
    require_scan(*records())


@pytest.mark.parametrize('record,key,value', [
    (0,'job_id',82039),(0,'source_job',81769),(0,'independent_slab_reduction',False),
    (0,'source_code_and_field_claims_verified',False),(0,'new_maps',1),
    (0,'new_material_steps',1),(0,'baseline_replaced',True),(0,'results',{'8':{}}),
    (1,'job_id','82039'),(1,'shape',[9632,16,4096]),(1,'fields',{'16':[]}),
    (2,'state','RUNNING'),(2,'scontrol','ExitCode=1:0'),
])
def test_wrong_or_partial_evidence_is_rejected(record,key,value):
    args=records();args[record][key]=value
    with pytest.raises(ValueError):require_scan(*args)
