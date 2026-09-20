import pytest
from operations.scan_recent_positive_subspace import recent_basis


def source(name, hashes):
    paths = [f'{name}/state_{i}.dat' for i in range(3)]
    history = [{'input_path': paths[i], 'input_sha256': hashes[i],
                'output_path': paths[i+1], 'output_sha256': hashes[i+1]} for i in range(2)]
    return {'status': 'diagnostic_round_complete', 'active_map': None, 'pending_feedback': None,
            'history': history, 'slots': paths, 'current_slot': 2, 'current_sha256': hashes[2],
            'diagnostic': {'rounds': [{'endpoints': [1, 2], 'endpoints_claim': {
                label: {'path': paths[i], 'sha256': hashes[i]} for i, label in enumerate(('previous', 'final'))}}]}}


def test_four_recent_maps_use_measured_inputs_and_outputs():
    basis = recent_basis(source('a', ['0','1','2']), source('b', ['2','3','4']))
    assert [r['sha256'] for r in basis] == ['0','1','2','2','3','4']
    assert basis[2]['path'] != basis[3]['path']


def test_unrelated_history_cannot_be_called_a_consecutive_chain():
    with pytest.raises(RuntimeError, match='consecutive chain'):
        recent_basis(source('a', ['0','1','2']), source('b', ['7','8','9']))


def test_feedback_endpoint_mismatch_blocks_scan():
    a = source('a', ['0','1','2'])
    a['diagnostic']['rounds'][0]['endpoints_claim']['final']['sha256'] = 'wrong'
    with pytest.raises(RuntimeError, match='unrelated radiation endpoints'):
        recent_basis(a, source('b', ['2','3','4']))
