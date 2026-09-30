"""Declare a new candidate from an audited full/half rejection; no field edits."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT, read, digest
from handoff.audit_tools.review_x20_window_prediction import reduce_prediction
from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis


def main():
    audit_path = Path('handoff/evidence/20261001-x20-block-prediction-82472-review.json')
    a = read(audit_path)
    assert a['job_id'] == 82472 and a['independent_complete_field_reduction'] and a['passed'] is False
    ppath = ROOT/'x20-block-prediction-82472-received/prediction.json'
    claim = next(r for r in a['receipt']['files'] if r['path'] == 'prediction.json')
    assert digest(ppath) == claim['sha256']
    rows = read(ppath)['slabs']
    assert {r['first_group']//128 for r in rows if min(r['minima']) < 0} == {65}
    assert all(min(r['minima'][2:]) >= 0 for r in rows)
    # The selected full field in block 65 is the already measured old half.
    # The third endpoint below stays OLD half everywhere, not the new half.
    mixed = deepcopy(rows)
    for r in mixed:
        if r['first_group']//128 != 65:
            continue
        for key in ('squared_l2', 'linf', 'scales', 'boundary_l1_numerator', 'boundary_signed'):
            r[key][1] = r[key][2]
        r['minima'][:2] = r['minima'][2:]
        r['boundary_flux'][2:4] = r['boundary_flux'][4:6]
    reduced = reduce_prediction(mixed)
    coefficients = deepcopy(a['selected_coefficients'])
    coefficients[65] = [v*.5 for v in coefficients[65]]
    expectation = expected_from_basis(read(ROOT/'x20-latest-basis-82441-received/basis.json')['slabs'], coefficients)
    np.testing.assert_allclose(reduced['squared_l2'][1], expectation['squared_l2'][1], rtol=3e-10, atol=0)
    full_checks = {k:v for k,v in reduced['checks'].items() if k.startswith('full_')}
    result = dict(source_job=82472, source_audit_sha256=digest(audit_path), source_prediction_sha256=digest(ppath),
                  selected_coefficients=coefficients, changed_blocks=[65], coefficient_factor=.5,
                  full_checks_on_spliced_measured_fields=full_checks,
                  full_l2_ratio=reduced['l2_ratios'][1], full_linf_ratio=reduced['linf_ratios'][1],
                  full_boundary=reduced['boundary'][1], baseline_boundary=reduced['boundary'][0],
                  new_half_not_measured=True, candidate_field_not_written=True,
                  arithmetic_order_not_identical_to_recomputing_half_coefficients=True,
                  needs_fresh_full_field_prediction=all(full_checks.values()),
                  new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,
                  scope='small-artifact screening only; neither true map nor accepted candidate')
    target = Path('handoff/evidence/20261001-x20-block65-half-proposal.json')
    with target.open('x') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='selected_coefficients'},indent=2))


if __name__ == '__main__':
    main()
