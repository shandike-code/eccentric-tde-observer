"""Attribute the audited eight-map response drift; no transfer/ODE solve or promotion."""
import csv
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'outputs/review-20260925/convex-joint-78032-complete-received'
AUDIT=ROOT/'handoff/evidence/20260927-convex-joint-complete-review.json'
OLD=ROOT/'outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'


def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()


def main():
    audit=json.loads(AUDIT.read_text());claim=audit['archive']
    archive=ROOT/'outputs/review-20260925'/Path(claim['path']).name
    assert digest(archive)==claim['sha256'] and archive.stat().st_size==claim['size_bytes']
    with tarfile.open(archive) as t:
        inv={x['path']:x for x in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
    used=[]
    def checked(name):
        p=SOURCE/name;c=inv[name]
        assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256'],name
        used.append(c);return p
    def arrays(name):
        with np.load(checked(name),allow_pickle=False) as z:
            d={k:z[k].copy() for k in z.files}
        assert all(np.isfinite(v).all() for v in d.values());return d
    protocol=json.loads(checked('control/pair10/feedback_protocol.json').read_text())
    assert digest(OLD)==protocol['sources']['physical_old_time_level']['sha256']
    with np.load(OLD,allow_pickle=False) as z:mass=z['cell_mass_g_cm2'].copy()
    assert mass.shape==(128,) and np.all(mass>0)
    weights=mass/mass.sum()
    trial=arrays('control/trial_material.npz')
    r20=trial['base_residual'].reshape(128,4)
    r20_mass_norm=float(np.sqrt(np.sum(weights[:,None]*r20*r20)))
    assert r20_mass_norm>0
    norm=lambda v:float(np.sqrt(np.sum(weights*np.asarray(v)**2)))
    vectors={n:{e:arrays(f'control/pair{n:02d}/{e}_response.npz')['residual'].reshape(128,4)
                for e in ('previous','final')} for n in (2,10)}
    component={}
    for a in ('previous','final'):
        for b in ('previous','final'):
            d=vectors[10][a]-vectors[2][b];sq=weights[:,None]*d*d
            fraction=sq.sum(0)/sq.sum()
            key=a+'_vs_'+b
            got=np.sqrt(sq.sum())/r20_mass_norm
            expected=audit['windows']['10']['window']['vector_difference_over_frozen_r20_norms'][key][1]
            np.testing.assert_allclose(got,expected,rtol=2e-13)
            component[key]={'mass_squared_fraction_by_channel':fraction.tolist(),'mass_norm_over_r20':float(got)}
    # Verify the selected pair really maximizes this run's mass-weighted drift.
    assert max(component, key=lambda k: component[k]['mass_norm_over_r20'])=='final_vs_previous'
    # Nonlinear log allocation uses its exact secant factor.
    before=arrays('control/pair02/previous_energy_ledger.npz')
    after=arrays('control/pair10/final_energy_ledger.npz')
    assert np.array_equal(before['total_old'],after['total_old'])
    assert np.all(before['remaining']>0) and np.all(after['remaining']>0)
    delta=after['remaining']-before['remaining']
    logchange=np.log1p(delta/before['remaining'])
    factor=np.empty(128)
    np.divide(logchange,delta,out=factor,where=delta!=0)
    factor[delta==0]=1/before['remaining'][delta==0]  # analytic limit, not an energy floor
    np.testing.assert_allclose(logchange,(vectors[10]['final']-vectors[2]['previous'])[:,0],rtol=1e-8,atol=3e-14)
    parts=[]
    for i in range(76):
        def heating(n,e):
            a=arrays(f'control/pair{n:02d}/feedback/{e}/block{i:02d}.npz')
            return a['atomic_rate_heating_erg_s_cm3'].reshape(256,16).mean(axis=1)[:128]
        dq=heating(10,'final')-heating(2,'previous')
        parts.append(dq*float(trial['step_duration_s'])/trial['density_g_cm3']*factor)
    parts=np.array(parts);ion=-(after['ion_new']-before['ion_new'])*factor
    closure=norm(parts.sum(0)+ion-logchange)
    assert closure < 1e-10*norm(logchange)
    norms=np.array([norm(x) for x in parts])
    # Exploratory scalar heating projection on two REAL map pairs x0->x1, x8->x9.
    # This is a linear sensitivity proxy, not a new transfer solution or material gate.
    early_final=arrays('control/pair02/final_energy_ledger.npz')
    late_previous=arrays('control/pair10/previous_energy_ledger.npz')
    sensitivity=float(trial['step_duration_s'])/trial['density_g_cm3']/after['remaining']
    r1=(early_final['q']-before['q'])*sensitivity
    r9=(after['q']-late_previous['q'])*sensitivity
    direction=r1-r9
    quadratic=float(np.sum(weights*direction*direction))
    assert quadratic>0 and norm(r1)>0 and norm(r9)>0
    alpha=-float(np.sum(weights*r9*direction))/quadratic
    projected={'alpha':alpha,'paired_inputs':['x0','x8'],'paired_outputs':['x1','x9'],
        'linear_heating_proxy_ratio':norm(r9+alpha*direction)/norm(r9),
        'weighted_cosine':float(np.sum(weights*r1*r9)/(norm(r1)*norm(r9))),
        'positivity_checked':False,'full_radiation_residual_checked':False,
        'actual_candidate_heating_computed':False,'new_trial_authorized':False}
    report={'source_archive':claim,'input_files_checked':len(used),'used_input_claims':used,
        'physical_old_claim':protocol['sources']['physical_old_time_level'],'r20_mass_norm':r20_mass_norm,
        'channel_order':['ln_gas_energy','ln_HII_HI','ln_HeII_HeI','ln_HeIII_HeI'],
        'component_comparisons':component,'decomposition_pair':'pair10 final minus pair02 previous',
        'thermal_log_change_mass_norm':norm(logchange),'ionization_term_mass_norm':norm(ion),
        'closure_mass_norm':closure,'sum_block_contribution_norms':float(norms.sum()),
        'block56_75_sum_norm_upper_bound':float(norms[56:].sum()),
        'block56_75_upper_bound_over_thermal_norm':float(norms[56:].sum()/norm(logchange)),
        'cells96_127_thermal_mass_squared_fraction':float(np.sum(weights[96:]*logchange[96:]**2)/norm(logchange)**2),
        'exploratory_heating_projection':projected,
        'ranked_blocks':[{'block':int(i),'mass_norm':float(norms[i])} for i in np.argsort(norms)[::-1]],
        'new_maps':0,'new_material_steps':0,'causal_attribution_proven':False,'strict_error_bound':False}
    out=ROOT/'handoff/evidence/20260927-convex-feedback-drift-localization'
    out.with_suffix('.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with out.with_suffix('.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['block','cell_index','thermal_log_contribution'])
        w.writerows((i,j,float(parts[i,j])) for i in range(76) for j in range(128))
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    ax[0].bar(range(76),norms);ax[0].set(xlabel='Frequency block',ylabel='Mass norm of thermal log contribution')
    ax[1].plot(range(128),logchange);ax[1].set(xlabel='Material cell index (no depth interpretation)',ylabel='Change in log gas energy')
    fig.suptitle('Audited eight-map window decomposition; no new material step')
    fig.savefig(out.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps({k:v for k,v in report.items() if k not in ('used_input_claims','ranked_blocks')},indent=2))


if __name__=='__main__':main()
