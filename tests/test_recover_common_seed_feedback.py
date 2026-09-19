from copy import deepcopy
import pytest
from operations.recover_common_seed_feedback import recovery_protocol,verify_previous,OUTPUT_KEYS


def protocol():
    return {'sources':{'previous_radiation':{'path':'old/state_0.dat','sha256':'a'*64}},
            'configuration':{**{k:'old/'+k for k in OUTPUT_KEYS},'maximum_concurrent_processes':16,
                             'block_count':2,'rate_quadrature_order_per_group':16},
            'formal_state_gates':{'wall':7200,'positive':0},'acceptance_gates':{'radiation':1e-4},
            'authorization':{'accept_material_step':False}}


def test_only_paths_and_concurrency_change():
    p=protocol();before=deepcopy(p);r=recovery_protocol(p,'new/run')
    assert p==before
    for k in OUTPUT_KEYS:
        assert r['configuration'][k].startswith('new/run/')
        r['configuration'][k]=p['configuration'][k]
    assert r['configuration']['maximum_concurrent_processes']==2
    r['configuration']['maximum_concurrent_processes']=16
    assert r==p


def previous():
    return {'status':'complete','state_gate_passed':True,'protocol_sha256':'b'*64,
            'state_label':'previous','state_sha256':'a'*64,'state_path':'old/state_0.dat',
            'completed_blocks':[{'block_index':0},{'block_index':1}]}


def test_good_previous_is_reusable():
    verify_previous(previous(),protocol(),'b'*64)


@pytest.mark.parametrize('field,value',[('state_gate_passed',False),('state_sha256','c'*64),
                                       ('protocol_sha256','c'*64),('status','running')])
def test_invalid_previous_is_not_reused(field,value):
    m=previous();m[field]=value
    with pytest.raises(RuntimeError,match='lineage'):verify_previous(m,protocol(),'b'*64)


def test_duplicate_block_refused():
    m=previous();m['completed_blocks']=[{'block_index':0},{'block_index':0}]
    with pytest.raises(RuntimeError,match='ownership'):verify_previous(m,protocol(),'b'*64)
