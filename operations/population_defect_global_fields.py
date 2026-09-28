"""Dual-reference actual-map checks; only the current midpoint tests affinity."""
import math
import numpy as np
from operations import seven_block_global_fields as fields

GATES = fields.GATES.copy()
CENTERS = (23, 30)
SELECTED = tuple(range(20, 34))
TOTAL_SELECTED = tuple(range(20, 48))


def write_candidates(source, replacements, full, half, shape, checkpoint=lambda: None):
    return fields.write_candidates(source, replacements, full, half, shape,
                                   centers=CENTERS, checkpoint=checkpoint)


def original_reference(paths, shape, checkpoint=lambda: None):
    """Original x,T(x), new full,T(full), current midpoint,T(midpoint)."""
    if len(paths) != 6:
        raise ValueError('three actual input/output pairs required')
    rows = []
    for start, (x, y, q, tq, h, th) in fields.chunks(paths, shape):
        checkpoint()
        if start // 128 not in TOTAL_SELECTED and not (np.array_equal(x, q) and np.array_equal(x, h)):
            raise ValueError('unselected original input changed')
        # h 是本次起点与新全步的中点，不是原79151 x与新全步的中点。
        # 这里只比较真实缺陷的大小；不能构造一项假的“原参考半步仿射误差”。
        with np.errstate(invalid='raise', over='raise', divide='raise'):
            defects = (y-x, tq-q, th-h)
            ss = [float(np.sum(z*z)) for z in defects]
            pp = [float(np.max(abs(z))) for z in defects]
        if not np.isfinite(ss+pp).all():
            raise ValueError('nonfinite original-reference statistics')
        rows.append(dict(first_group=start, group_count=len(x), block=start//128,
                         squared_l2=ss, linf=pp, output_change_linf=float(np.max(abs(tq-y)))))
    sums = [math.fsum(row['squared_l2'][i] for row in rows) for i in range(3)]
    peaks = [max(row['linf'][i] for row in rows) for i in range(3)]
    if sums[0] <= 0 or peaks[0] <= 0:
        raise ValueError('zero original defect')
    return dict(fixed_scale_l2_ratios=[math.sqrt(s/sums[0]) for s in sums],
                fixed_scale_linf_ratios=[p/peaks[0] for p in peaks], slabs=rows,
                original_defect_l2=math.sqrt(sums[0]), original_defect_linf=peaks[0],
                all_groups_evaluated=shape[0], half_is_original_midpoint=False,
                affinity_tested_here=False)


def validate(paths, original_pair, shape, checkpoint=lambda: None):
    current = fields.validate(paths, shape, blocks=SELECTED, checkpoint=checkpoint)
    original = original_reference(list(original_pair)+list(paths[2:]), shape, checkpoint)
    return current, original


def checks(current, original, current_row, original_row, full, half):
    results = {'current_'+k: v for k, v in fields.checks(current, current_row, full, half).items()}
    a, b = original['fixed_scale_l2_ratios'], original['fixed_scale_linf_ratios']
    if len(a) != 3 or len(b) != 3 or not np.isfinite(a+b).all():
        raise ValueError('invalid original-reference ratios')
    original_checks = dict(full_l2_benefit=a[1] <= .8,
        full_linf_nonincrease=b[1] <= GATES['nonincrease_ratio_max'],
        half_l2_nonincrease=a[2] <= GATES['nonincrease_ratio_max'],
        half_linf_nonincrease=b[2] <= GATES['nonincrease_ratio_max'])
    for name, row in [('full', full), ('half', half)]:
        original_checks[name+'_radiation'] = row['residual'] < GATES['radiation_max']
        for key in ('boundary_l1', 'boundary_bolometric'):
            original_checks[name+'_'+key] = (row[key] < GATES['boundary_max']
                and row[key] <= original_row[key]*GATES['nonincrease_ratio_max'])
    results.update({'original_'+k: bool(v) for k, v in original_checks.items()})
    return results
