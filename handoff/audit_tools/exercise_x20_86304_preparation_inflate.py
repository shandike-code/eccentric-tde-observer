"""Tiny bounded decoder fixture; independent expected NPY bytes, no native call."""
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import time
import zipfile
from operations.x20_86304_preparation_inflate import BoundedArrayLoader


def run():
    started=time.monotonic()
    header=repr(dict(descr='<f8',fortran_order=False,shape=(257,32)))
    padding=(-(10+len(header)+1))%64
    h=(header+' '*padding+'\n').encode('ascii')
    payload=b''.join(struct.pack('<d',float(i%17)) for i in range(257*32))
    npy=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(h))+h+payload
    results=[]
    for method in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=method) as z:
            info=zipfile.ZipInfo('value.npy',date_time=(2020,1,1,0,0,0));info.compress_type=method
            z.writestr(info,npy)
        raw=output.getvalue();loader=BoundedArrayLoader()
        checks=0
        def check():
            nonlocal checks
            checks+=1
            if time.monotonic()-started>=10:raise TimeoutError('fixture deadline')
        arrays=loader.npz(raw,hashlib.sha256(raw).hexdigest(),'synthetic',check)
        a=arrays['value']
        assert a.shape==(257,32) and a.dtype.str=='<f8' and not a.flags.writeable
        assert a.tobytes()==payload
        results.append(dict(method=method,source_bytes=len(raw),source_sha256=hashlib.sha256(raw).hexdigest(),
            array_bytes=a.nbytes,array_sha256=hashlib.sha256(a.tobytes()).hexdigest(),checks=checks,meter=loader.facts()))
    return dict(schema='86304-inflate-synthetic-v1',platform=sys.platform,results=results,
        elapsed_seconds=time.monotonic()-started,synthetic=True,production_authorized=False,
        whole_lifecycle_guard_verified=False,all_scientific_temporaries_metered=False)

if __name__=='__main__':
    p=Path(sys.argv[1]);p.mkdir()
    with (p/'result.json').open('x') as f:json.dump(run(),f,indent=2)
