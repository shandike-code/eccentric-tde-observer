import copy
import pytest
from handoff.audit_tools.review_x20_85889_chord_sources import bind_pair, bind_observation

def fixture():
    rows=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,17)]
    e={k:dict(sha256=str(i),size_bytes=10099884032) for k,i in [('previous',14),('final',15),('mapped_final',16)]}
    return dict(new_map_count=16,history_rows=rows[-2:],endpoints=e),dict(history=rows,active_map=None,current_sha256='16')

def test_two_true_maps():
    m,s=fixture();assert bind_pair(m,s)['final']['sha256']=='15'

@pytest.mark.parametrize('fault',['swap','current','active','chain','size'])
def test_reject_lineage_fault(fault):
    m,s=fixture();m=copy.deepcopy(m);s=copy.deepcopy(s)
    if fault=='swap':m['endpoints']['final'],m['endpoints']['mapped_final']=m['endpoints']['mapped_final'],m['endpoints']['final']
    if fault=='current':s['current_sha256']='15'
    if fault=='active':s['active_map']={}
    if fault=='chain':s['history'][8]['input_sha256']='wrong'
    if fault=='size':m['endpoints']['previous']['size_bytes']-=8
    with pytest.raises(ValueError):bind_pair(m,s)

@pytest.mark.parametrize('fault',[None,'missing','duplicate','size','symlink'])
def test_observation(fault):
    m,_=fixture();e=m['endpoints']
    rows=[dict(branch='accelerated',endpoint=k,claim=v,symlink=False,size_bytes=v['size_bytes']) for k,v in e.items()]
    if fault=='missing':rows.pop()
    if fault=='duplicate':rows.append(rows[0])
    if fault=='size':rows[0]['size_bytes']-=8
    if fault=='symlink':rows[0]['symlink']=True
    if fault is None:bind_observation(rows,'accelerated',e)
    else:
        with pytest.raises(ValueError):bind_observation(rows,'accelerated',e)
