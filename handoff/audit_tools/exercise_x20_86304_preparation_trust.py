"""New eleven-cell control/trust fixtures, no scientific source files."""
import json,platform,time
import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from operations.x20_86304_preparation_trust import exact_control_trial, within_trust_region
from operations.x20_86304_preparation_inflate import PayloadLedger

LIMITS=dict(maximum_relative_temperature_change=.5,
            maximum_absolute_material_energy_increment_fraction=.25,
            maximum_population_fraction_change=.05)


def fixture(n=11):
    a=np.array([[28.+i/64., (i%4-2)/8., i/128., -i/256.] for i in range(n)]).reshape(-1)
    decoded=GroundStateLogSimplexCodec(n).decode(a)
    residual=np.array([(i%5-2)/16. for i in range(4*n)])
    base={k:np.array(v,copy=True) for k,v in decoded.__dict__.items()}
    base.update(encoded_state=a.copy(),base_encoded_state=a.copy(),base_residual=residual.copy(),
                finite_direction=residual.copy(),density_g_cm3=np.full(n,2.**-32),
                phase_index=np.array(1,dtype='i8'),step_duration_s=np.array(2.),relaxation=np.array(0.))
    trial={k:v.copy() for k,v in base.items()}
    old=dict(density_g_cm3=np.full((3,n),2.**-32),step_duration_s=np.full(3,2.))
    return trial,base,residual,old


def exercise():
    trial,base,r,old=fixture();results=[]
    for mode in ('control','small','large'):
        ledger=PayloadLedger();checks=0
        def check():
            nonlocal checks
            checks+=1
        a=base['encoded_state'];b=a.copy()
        if mode!='control':b.reshape(11,4)[:,0]+=.03125 if mode=='small' else 1.
        t=time.monotonic()
        if mode=='control':
            exact_control_trial(trial,base,r,old,ledger,check);accepted=True
        else:accepted=within_trust_region(GroundStateLogSimplexCodec(11),a,b,ledger,check,**LIMITS)
        results.append(dict(mode=mode,accepted=accepted,checkpoints=checks,entries=ledger.entries,
                            reserved_bytes=ledger.budget.used,elapsed_s=time.monotonic()-t))
    return dict(schema='86304-trust-control-synthetic-v1',platform=platform.system(),cases=results,
                exact_control_component=True,configuration_integrated=False,
                all_scientific_temporaries_metered=False,whole_lifecycle_guard_verified=False,production_authorized=False)

if __name__=='__main__':print(json.dumps(exercise(),sort_keys=True))
