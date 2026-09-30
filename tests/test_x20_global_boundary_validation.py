"""Global-source identity and cross-frequency affine-map regressions."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from operations.x20_global_boundary_validation import validate_prediction
from operations.x20_boundary_validation_fields import write_candidates, prediction_error


def audited_source():
    audit = json.loads(Path('handoff/evidence/20261001-x20-global-prediction-82512-review.json').read_text())
    declaration = dict(fields=copy.deepcopy(audit['fields']),
                       selected_coefficients=copy.deepcopy(audit['selected_coefficients']),
                       global_coefficients=list(audit['global_coefficients']),
                       coefficient_mode='one_global_triple_repeated', optimization_converged=True)
    return audit, declaration


@pytest.mark.parametrize('damage', ['none', 'job', 'gate', 'missing_gate', 'fields',
                                  'blockwise', 'global', 'nonfinite', 'mode', 'scope'])
def test_global_prediction_source_guard(damage):
    audit, declaration = audited_source()
    if damage == 'none':
        validate_prediction(audit, declaration)
        return
    if damage == 'job': audit['job_id'] = 82486
    elif damage == 'gate': audit['checks']['full_l2_benefit'] = False
    elif damage == 'missing_gate': del audit['checks']['half_boundary_l1']
    elif damage == 'fields': declaration['fields'] = []
    elif damage == 'blockwise':
        audit['selected_coefficients'][25][0] += .01
        declaration['selected_coefficients'] = copy.deepcopy(audit['selected_coefficients'])
    elif damage == 'global': declaration['global_coefficients'][0] += .01
    elif damage == 'nonfinite': audit['global_coefficients'][0] = float('nan')
    elif damage == 'mode': declaration['coefficient_mode'] = 'per_natural_block_with_boundary_scalars'
    else: audit['new_material_steps'] = 1
    with pytest.raises(ValueError): validate_prediction(audit, declaration)


@pytest.mark.parametrize('global_coefficients', [True, False])
def test_frequency_coupling_distinguishes_global_from_block_coefficients(tmp_path, global_coefficients):
    # 频组循环搬移构造一个有跨块耦合的仿射算子；测试的是次序，不拟合真实物理核。
    shape = (130, 2, 2)
    x = np.linspace(1., 5., np.prod(shape)).reshape(shape)
    def transfer(z): return .7*np.roll(z, 1, axis=0)+.2*z+.1
    inputs = []
    for i, state in enumerate((x, x+1., x*.8, x*.6)):
        for j, value in enumerate((state, transfer(state))):
            path = tmp_path/f'source-{2*i+j}.dat'
            value.tofile(path)
            inputs.append(path)
    coefficients = [[.1, -.2, .05], [.1, -.2, .05] if global_coefficients else [-.1, .1, .02]]
    full, half = tmp_path/'full.dat', tmp_path/'half.dat'
    write_candidates(inputs, shape, coefficients, full, half)
    outputs = []
    for i, path in enumerate((full, half)):
        output = tmp_path/f'true-{i}.dat'
        transfer(np.fromfile(path).reshape(shape)).tofile(output)
        outputs.append(output)
    report = prediction_error(inputs+outputs, shape, coefficients)
    assert report['passed'] is global_coefficients
    assert [r['group_count'] for r in report['slabs']] == [32, 32, 32, 32, 2]
