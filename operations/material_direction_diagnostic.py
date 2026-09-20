"""Finite-step residual comparisons, never a Jacobian or error-bound claim."""
import numpy as np


def latest_pair(state):
    history = state.get('history', [])
    rounds = state.get('diagnostic', {}).get('rounds', [])
    if (state.get('status') != 'diagnostic_round_complete' or state.get('active_map')
            or state.get('pending_feedback') or len(history) < 2 or not rounds):
        raise ValueError('completed settled history required')
    pair = rounds[-1]
    if pair['endpoints'] != [len(history)-1, len(history)]:
        raise ValueError('last pair does not evaluate the latest two map inputs')
    for row, label in zip(history[-2:], ('previous', 'final')):
        c = pair['endpoints_claim'][label]
        if (c['path'], c['sha256']) != (row['input_path'], row['input_sha256']):
            raise ValueError('feedback endpoint lineage mismatch')
    return pair


def common_direction(half, full):
    if float(half['relaxation']) != .001953125 or float(full['relaxation']) != .00390625:
        raise ValueError('unexpected material amplitudes')
    for k in ('base_encoded_state','finite_direction','base_residual','density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(half[k], full[k]): raise ValueError('frozen direction or physics changed: '+k)
    for t in (half, full):
        if not np.array_equal(t['encoded_state'], t['base_encoded_state']+float(t['relaxation'])*t['finite_direction']):
            raise ValueError('trial is not on the frozen encoded direction')


def secant_diagnostic(base, half, full, mass, alpha):
    """Report two finite secants and their disagreement without extrapolating acceptance."""
    b,h,f = [np.asarray(v, dtype=float).reshape(-1,4) for v in (base,half,full)]
    m = np.asarray(mass,dtype=float)
    if (b.shape != h.shape or b.shape != f.shape or m.shape != (len(b),)
            or not all(np.isfinite(v).all() for v in (b,h,f,m))
            or np.any(m <= 0) or not np.isfinite(alpha) or alpha <= 0):
        raise ValueError('invalid finite secant inputs')
    sh, sf = (h-b)/alpha, (f-b)/(2*alpha)
    def norm(x): return float(np.linalg.norm(x))
    nh,nf=norm(sh),norm(sf)
    if min(nh,nf) == 0: raise ValueError('zero secant cannot define relative disagreement or angle')
    # 中文：这是有限位移商；辐射误差和物质非线性都能导致两商不同，不能直接叫 Jv。
    def slopes(s):
        return {'l2_squared':float(2*np.sum(b*s)),
                'mass_norm_squared':float(2*np.sum(m[:,None]*b*s)/m.sum())}
    return {'half_alpha':alpha,'full_alpha':2*alpha,
            'half_secant_l2':nh,'full_secant_l2':nf,
            'secant_disagreement_l2':norm(sh-sf),
            'relative_secant_disagreement':norm(sh-sf)/max(nh,nf),
            'secant_cosine':float(np.sum(sh*sf)/(nh*nf)),
            'half_finite_secant_merit_slope':slopes(sh),
            'full_finite_secant_merit_slope':slopes(sf),
            'second_difference_l2':norm(f-2*h+b),
            'limitation':'Finite secants combine material nonlinearity and radiation error; no certified Jv, derivative sign, or error bound.'}
