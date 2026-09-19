from copy import deepcopy
from operations.replay_pair_nohuge import replay_protocol, OUTPUT_KEYS


def test_only_declared_execution_fields_change():
    old = {'configuration': {k: f'old/{k}.json' for k in OUTPUT_KEYS},
           'sources': {'trial': {'sha256': 'frozen'}}, 'formal_state_gates': {'wall': 7200},
           'acceptance_gates': {'inner': 1e-4}, 'authorization': {'physical_dt_changed': False}}
    old['configuration'].update(maximum_concurrent_processes=2, material_update=False)
    backup = deepcopy(old)
    new = replay_protocol(old, 'outputs/hpc/new')
    assert old == backup
    for k in OUTPUT_KEYS:
        assert new['configuration'].pop(k) == f'outputs/hpc/new/{k}.json'
        backup['configuration'].pop(k)
    assert new['configuration'].pop('maximum_concurrent_processes') == 16
    backup['configuration'].pop('maximum_concurrent_processes')
    assert new == backup
