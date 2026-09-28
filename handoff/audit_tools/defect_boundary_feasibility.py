"""Conditional feasibility of two boundary gates in a fixed affine predictor."""
import math


def current_anchor_bound(original, current, full, half, theta):
    """No proof of global operator affinity is inferred from the measured half."""
    rows = (original, current, full, half)
    keys = ('total_input', 'total_mapped', 'signed_block_sum')
    if theta <= 0 or not math.isfinite(theta) or not all(math.isfinite(r[k]) for r in rows for k in keys):
        raise ValueError('finite positive threshold and fluxes required')
    vertices = []
    # z=x+a(q-x)+b(u-q), 0<=a,b<=1。这里只是固定两方向的仿射预测。
    for a, b in ((0,0), (1,0), (0,1), (1,1)):
        vertex = {k: original[k]+a*(current[k]-original[k])+b*(full[k]-current[k]) for k in keys}
        if min(vertex['total_input'], vertex['total_mapped']) <= 0:
            raise ValueError('predictor requires positive boundary flux')
        vertices.append(dict(a=a, b=b, **vertex))
    envelope = max(v[k] for v in vertices for k in ('total_input','total_mapped'))
    # 若D(h)=(D(q)+D(u))/2，则同时 |D(h)|<=theta*S_h、|D(u)|<=theta*S_u
    # 必须有 |D(q)|<=theta*(2*S_h+S_u)<=3*theta*envelope。
    capacity = 3*theta*envelope
    defect = abs(current['signed_block_sum'])
    measured_half_error = abs(half['signed_block_sum']-.5*(current['signed_block_sum']+full['signed_block_sum']))
    return dict(theta=theta, flux_envelope=envelope, vertices=vertices,
        current_absolute_signed_defect=defect, maximum_passing_defect_under_affine_model=capacity,
        excess_over_capacity=defect-capacity, conditional_infeasible=defect>capacity,
        measured_half_signed_error=measured_half_error,
        observed_error_is_not_uniform_bound=True, global_operator_affinity_proved=False,
        minimum_required_flux_envelope=defect/(3*theta),
        required_envelope_ratio=defect/capacity, previous_rejection_unchanged=True)
