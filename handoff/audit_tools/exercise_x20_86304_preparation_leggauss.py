"""Synthetic degrees 1..16 only, no source inputs or production configuration."""
import hashlib,json,pathlib,sys,time
import numpy as np
from operations.x20_86304_preparation_leggauss import nodes_weights

class Ledger:
    def __init__(self):self.entries=[];self.total=0
    def reserve(self,label,size):
        if type(size) is not int or size<0 or self.total+size>1000000:raise ValueError('capacity')
        self.entries.append([label,size]);self.total+=size

def exercise():
    cases=[];start=time.monotonic()
    for n in range(1,17):
        ledger=Ledger();checks=[0]
        def check():checks[0]+=1
        x,w=nodes_weights(n,ledger,check)
        arrays=[]
        for a in (x,w):
            raw=a.tobytes()
            arrays.append(dict(shape=list(a.shape),dtype=a.dtype.str,hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest()))
        cases.append(dict(degree=n,arrays=arrays,ledger=ledger.entries,total=ledger.total,checks=checks[0]))
    return dict(schema='leggauss-explicit-arrays-v1',numpy=np.__version__,cases=cases,
                elapsed_seconds=time.monotonic()-start,private_workspace_metered=False,
                configuration_integrated=False,production_authorized=False)

if __name__=='__main__':
    with pathlib.Path(sys.argv[1]).open('x') as f:json.dump(exercise(),f)
