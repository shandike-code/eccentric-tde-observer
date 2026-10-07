"""Seven-cell mixed-sign synthetic decode, without scientific file access."""
import json,platform,time
import numpy as np
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from operations.x20_86304_preparation_codec import decode
from operations.x20_86304_preparation_inflate import PayloadLedger


def exercise():
    a=np.array([[29.+i/16.,(i%3-1)*.5,i/32.,-i/64.] for i in range(7)]).reshape(-1)
    c=GroundStateLogSimplexCodec(7);ledger=PayloadLedger();checks=0
    def check():
        nonlocal checks
        checks+=1
    started=time.monotonic();result=decode(c,a,ledger,check);elapsed=time.monotonic()-started
    return dict(schema='86304-codec-synthetic-v1',platform=platform.system(),elapsed_s=elapsed,
        checkpoints=checks,entries=ledger.entries,reserved_bytes=ledger.budget.used,
        arrays={k:dict(dtype=v.dtype.str,shape=list(v.shape),hex=v.tobytes().hex()) for k,v in result.__dict__.items()},
        exact_trial_integrated=False,configuration_integrated=False,
        all_scientific_temporaries_metered=False,whole_lifecycle_guard_verified=False,production_authorized=False)

if __name__=='__main__':print(json.dumps(exercise(),sort_keys=True))
