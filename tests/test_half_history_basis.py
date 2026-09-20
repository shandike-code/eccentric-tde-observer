from copy import deepcopy
import pytest
from operations.half_history_basis import last_actual_map


def state():
    h=[{'input_path':str(i),'input_sha256':'h'+str(i),'output_path':str(i+1),'output_sha256':'h'+str(i+1)} for i in range(8)]
    p={'endpoints':[7,8],'endpoints_claim':{'previous':{'path':'6','sha256':'h6'},'final':{'path':'7','sha256':'h7'}}}
    return {'status':'diagnostic_round_complete','history':h,'diagnostic':{'rounds':[p]},
            'slots':['8'],'current_slot':0,'current_sha256':'h8'}


def test_selects_last_real_map_in_an_eight_map_run():
    assert last_actual_map(state())==[{'path':'7','sha256':'h7'},{'path':'8','sha256':'h8'}]


@pytest.mark.parametrize('fault',['link','sha','slot','active','feedback'])
def test_rejects_broken_or_unsettled_lineage(fault):
    s=deepcopy(state())
    if fault=='link':s['history'][-2]['output_sha256']='wrong'
    if fault=='sha':s['current_sha256']='wrong'
    if fault=='slot':s['slots'][0]='wrong'
    if fault=='active':s['active_map']={'index':9}
    if fault=='feedback':s['diagnostic']['rounds'][-1]['endpoints']=[3,4]
    with pytest.raises(ValueError):last_actual_map(s)
