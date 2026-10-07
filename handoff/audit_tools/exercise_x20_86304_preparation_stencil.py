"""New tiny frequency-only fixture; no real files or configuration entry."""
import base64
from dataclasses import fields,is_dataclass
import hashlib
import json
import sys
import time
import numpy as np
from operations.x20_86304_preparation_inflate import PayloadLedger
from operations import x20_86304_preparation_stencil as component


def fact(x):
    if isinstance(x,np.ndarray):
        raw=x.tobytes();return dict(dtype=x.dtype.str,shape=list(x.shape),bytes=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest(),readonly=not x.flags.writeable)
    if is_dataclass(x):return {f.name:fact(getattr(x,f.name)) for f in fields(x)}
    if isinstance(x,tuple):return [fact(v) for v in x]
    return x


def exercise():
    started=time.monotonic();l=PayloadLedger();checks=0
    def check():
        nonlocal checks
        checks+=1
    edge=np.array([2.**i for i in range(10)]);mu=np.array([-.75,-.25,.25,.75]);w=np.full(4,.5);beta=np.array([-.125,0.,.125])
    grid=component.stencil(edge,.25,l,check)
    ray=component.rays(mu,w,beta,l,check)
    blocks=component.plan(grid,mu,w,beta,4,l,check)
    return dict(schema='frequency-preparation-synthetic-v1',synthetic=True,production_authorized=False,
        all_scientific_temporaries_metered=False,whole_lifecycle_guard_verified=False,configuration_integrated=False,
        platform=sys.platform,elapsed_s=time.monotonic()-started,checks=checks,
        input=fact((edge,mu,w,beta)),stencil=fact(grid),rays=fact(ray),blocks=fact(blocks),entries=l.entries,
        explicit_payload_capacity_reserved_bytes=sum(n for _,n in l.entries))


if __name__=='__main__':print(json.dumps(exercise(),allow_nan=False))
