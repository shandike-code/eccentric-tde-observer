"""Attribute the audited 79151 population window; no new matter or radiation solve."""
import itertools
import json
import math
from pathlib import Path
import tarfile
import numpy as np
from handoff.audit_tools import review_step21_control_windows as audit

ROOT = Path(__file__).resolve().parents[2]
ENDS = ('previous', 'final')
CHANNELS = ('ln_gas_energy', 'ln_HII_HI', 'ln_HeII_HeI', 'ln_HeIII_HeI')


def split_change(p_new, p_old, c_new, c_old, mass):
    """Keep signed vectors; triangle bounds are bounds on measured differences only."""
    dp, dc = p_new-p_old, c_new-c_old
    ds = (p_new-c_new)-(p_old-c_old)
    np.testing.assert_allclose(ds, dp-dc, rtol=0, atol=8*np.finfo(float).eps)
    pn, cn, sn = [audit.independent_norms(v, mass) for v in (dp, dc, ds)]
    return dict(candidate=pn.tolist(), control=cn.tolist(), signal=sn.tolist(),
                triangle_lower=np.abs(pn-cn).tolist(), triangle_upper=(pn+cn).tolist()), ds


def log_secant(before, after):
    before, after = np.asarray(before, float), np.asarray(after, float)
    if before.shape != after.shape or not np.isfinite([before, after]).all() or np.any(before<=0) or np.any(after<=0):
        raise ValueError('gas energy must be positive and finite')
    delta = after-before
    log_change = np.log1p(delta/before)
    factor = np.empty_like(delta)
    np.divide(log_change, delta, out=factor, where=delta!=0)
    factor[delta==0] = 1/before[delta==0]  # exact analytic limit, no floor
    return log_change, factor


def main():
    records = {}
    for label, stem, directory in (
        ('old', '20260928-refreshed-directions-complete-review', 'refreshed-directions-78950-complete-received'),
        ('new', '20260928-late-direction-complete-review', 'late-direction-79151-complete-received')):
        ap = ROOT/'handoff/evidence'/f'{stem}.json'; rec = audit.read(ap)
        assert rec['final_summary_present'] and rec['new_material_steps']==0
        archive = ROOT/'outputs/review-20260925'/Path(rec['archive']['path']).name
        assert archive.stat().st_size==rec['archive']['size_bytes'] and audit.digest(archive)==rec['archive']['sha256']
        folder = ROOT/'outputs/review-20260925'/directory
        with tarfile.open(archive) as tar:
            manifest = json.load(tar.extractfile('ARCHIVE_MANIFEST.json'))
        assert manifest==audit.read(folder/'ARCHIVE_MANIFEST.json')
        records[label] = dict(root=folder, audit=rec, inv={c['path']:c for c in manifest['files']}, pair=16 if label=='old' else 8)
    claims = {}
    def read_array(label, rel):
        rec=records[label]; claim=rec['inv'][rel]; path=rec['root']/rel
        assert path.stat().st_size==claim['size_bytes'] and audit.digest(path)==claim['sha256']
        claims[f'{label}/{rel}']=claim
        data=audit.arrays(path)
        assert all(np.isfinite(v).all() for v in data.values())
        return data
    def pair_array(label, case, suffix):
        return read_array(label, f"{case}/pair{records[label]['pair']:02d}/{suffix}")
    old_path=ROOT/'outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'
    protocol=audit.read(records['new']['root']/'population/pair08/feedback_protocol.json')
    old_claim=protocol['sources']['physical_old_time_level']
    assert old_path.stat().st_size==old_claim['size_bytes'] and audit.digest(old_path)==old_claim['sha256']
    mass=audit.arrays(old_path)['cell_mass_g_cm2']; weights=mass/math.fsum(mass)
    vectors={label:{case:{e:pair_array(label,case,f'{e}_response.npz')['residual'] for e in ENDS}
                    for case in ('population','control')} for label in records}
    for case in ('population','control'):
        assert audit.digest(records['old']['root']/case/'trial_material.npz')==audit.digest(records['new']['root']/case/'trial_material.npz')
    signal_min=np.min([audit.independent_norms(vectors['new']['population'][a]-vectors['new']['control'][b],mass)
                       for a,b in itertools.product(ENDS,repeat=2)],axis=0)
    assert np.all(signal_min>0)
    rows={}; signals={}
    for pn,cn,po,co in itertools.product(ENDS,repeat=4):
        key='/'.join((pn,cn,po,co))
        row, ds=split_change(vectors['new']['population'][pn],vectors['old']['population'][po],
                            vectors['new']['control'][cn],vectors['old']['control'][co],mass)
        row['signal_over_minimum']=(np.array(row['signal'])/signal_min).tolist()
        row['lower_over_minimum']=(np.array(row['triangle_lower'])/signal_min).tolist()
        rows[key]=row; signals[key]=ds
    worst={name:max(rows,key=lambda k:rows[k]['signal'][i]) for i,name in enumerate(audit.NAMES)}
    expected=records['new']['audit']['pairs']['population08']['response_measurement']['eight_map_signal_drift_over_signal']
    for i,name in enumerate(audit.NAMES):
        np.testing.assert_allclose(rows[worst[name]]['signal_over_minimum'][i],expected[name],rtol=1e-12)
    components={}
    for name,key in worst.items():
        v=signals[key].reshape(128,4)
        sq=v*v*(weights[:,None] if name=='mass_weighted' else 1.)
        if name=='maximum_cell':
            cell=int(np.argmax(sq.sum(1)));sq=sq[cell:cell+1]
        else:cell=None
        components[name]=dict(combination=key,squared_fraction_by_channel=(sq.sum(0)/sq.sum()).tolist(),maximum_cell_index=cell)

    # Worst mass combination: exact ledger secant apportions the log-gas change
    # into all 76 frequency contributions and ionization-energy subtraction.
    pn,cn,po,co=worst['mass_weighted'].split('/')
    terms={};ion_terms={};energy_checks={}
    for case,new_end,old_end in (('population',pn,po),('control',cn,co)):
        before=pair_array('old',case,f'{old_end}_energy_ledger.npz')
        after=pair_array('new',case,f'{new_end}_energy_ledger.npz')
        assert np.array_equal(before['total_old'],after['total_old'])
        log_change,factor=log_secant(before['remaining'],after['remaining'])
        delta_res=(vectors['new'][case][new_end]-vectors['old'][case][old_end]).reshape(128,4)[:,0]
        np.testing.assert_allclose(log_change,delta_res,rtol=1e-8,atol=5e-14)
        trial=read_array('new',f'{case}/trial_material.npz'); parts=[]
        for b in range(76):
            def heating(label,end):
                a=pair_array(label,case,f'feedback/{end}/block{b:02d}.npz')
                return a['atomic_rate_heating_erg_s_cm3'].reshape(256,16).mean(axis=1)[:128]
            dq=heating('new',new_end)-heating('old',old_end)
            parts.append(dq*float(trial['step_duration_s'])/trial['density_g_cm3']*factor)
        terms[case]=np.array(parts);ion_terms[case]=-(after['ion_new']-before['ion_new'])*factor
        residual=terms[case].sum(0)+ion_terms[case]-log_change
        np.testing.assert_allclose(residual,0,rtol=0,atol=5e-13)
        energy_checks[case]=dict(maximum_log_closure_error=float(np.max(np.abs(residual))),
                                minimum_gas_before=float(before['remaining'].min()),minimum_gas_after=float(after['remaining'].min()))
    block_terms=terms['population']-terms['control']; ion=ion_terms['population']-ion_terms['control']
    total=signals[worst['mass_weighted']].reshape(128,4)[:,0]
    np.testing.assert_allclose(block_terms.sum(0)+ion,total,rtol=1e-8,atol=5e-13)
    mass_norm=lambda a: math.sqrt(math.fsum(float(w)*float(x)**2 for w,x in zip(weights,a)))
    block_norms=np.array([mass_norm(a) for a in block_terms]);total_norm=mass_norm(total)
    assert total_norm>0
    ranked=sorted(range(76),key=lambda b:block_norms[b],reverse=True)
    result=dict(source_archives={k:r['audit']['archive'] for k,r in records.items()},used_claims=list(claims.items()),
        physical_old_claim=old_claim,channel_order=CHANNELS,signal_minimum=dict(zip(audit.NAMES,signal_min.tolist())),
        combination_order='new population/new control/old population/old control',combinations=rows,worst_combinations=worst,
        channel_decomposition=components,energy_ledger_checks=energy_checks,
        thermal_signal_mass_norm=total_norm,ionization_term_mass_norm=mass_norm(ion),
        sum_of_block_mass_norms=float(block_norms.sum()),
        high_frequency_blocks56_75_norm_sum_upper_bound=float(block_norms[56:].sum()),
        ranked_blocks=[dict(block=b,mass_norm=float(block_norms[b])) for b in ranked],
        mass_squared_fraction_by_cell=(weights*total*total/total_norm**2).tolist(),
        new_maps=0,new_material_steps=0,accepted_outer_steps=20,strict_error_bound=False,
        microscopic_causal_attribution_proven=False,baseline_replaced=False)
    prefix=ROOT/'handoff/evidence/20260928-late-population-drift-decomposition'
    prefix.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for j,(field,label) in enumerate((('candidate','candidate drift'),('control','control drift'),('signal','signal drift'))):
        ax[0].bar(np.arange(3)+(j-1)*.24,[rows[worst[k]][field][i]/signal_min[i] for i,k in enumerate(audit.NAMES)],width=.24,label=label)
    ax[0].axhline(.1,color='black',ls='--');ax[0].set(xticks=range(3),xticklabels=('L2','mass','max cell'),ylabel='Norm / current minimum signal');ax[0].legend(fontsize=8)
    ax[1].bar(range(76),block_norms);ax[1].set(xlabel='Frequency block',ylabel='Mass norm of log-gas contribution')
    ax[2].plot(range(128),total);ax[2].set(xlabel='Material cell index (no depth ordering claim)',ylabel='Signal drift: log gas energy')
    fig.suptitle('Population signal 16 to 24: measured decomposition, no extrapolation')
    fig.savefig(prefix.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps({k:result[k] for k in ('signal_minimum','worst_combinations','channel_decomposition','energy_ledger_checks','thermal_signal_mass_norm','ionization_term_mass_norm')},indent=2))


if __name__=='__main__':main()
