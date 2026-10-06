"""Fixed tiny synthetic fixture only; accepts no production field inputs."""
import hashlib
import json
from pathlib import Path
from types import FunctionType
import numpy as np
from operations import x20_85889_chord_scan as old
from operations import x20_85889_chord_scan_reuse as new
from handoff.audit_tools.review_x20_85889_chord_scan import review


def exercise(output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    source = Path(old.__file__)
    if hashlib.sha256(source.read_bytes()).hexdigest() != '9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643':
        raise ValueError('frozen scanner changed')
    shape = (129,2,3)
    x = np.arange(np.prod(shape), dtype='<f8').reshape(shape) % 11 + 2
    y = np.flip(x, axis=0) + 3
    fields = [x,.5*x+4,.25*x+6,y,.5*y+4,.25*y+6]
    claims=[]
    for i, a in enumerate(fields):
        p=output/f'synthetic-{i}.bin';raw=a.tobytes()
        with p.open('xb') as f:f.write(raw)
        claims.append(dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    # 只在这个固定129×2×3合成夹具中替换函数绑定，不修改旧模块或生产入口。
    fixture_scan=FunctionType(old.scan.__code__,dict(vars(old),slab_statistics=new.slab_statistics),
                              'fixture_scan',old.scan.__defaults__)
    reference=old.scan(claims,list(shape),lambda r:None)
    candidate=fixture_scan(claims,list(shape),lambda r:None)
    if reference['slabs']!=candidate['slabs']:
        raise AssertionError('numeric slab mismatch')
    reports=[]
    for name, data in (('original',reference),('reuse',candidate)):
        p=output/(name+'-scan.json')
        with p.open('x') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
        checked=review(json.loads(p.read_text()))
        with (output/(name+'-review.json')).open('x') as f:json.dump(checked,f,indent=2,allow_nan=False);f.write('\n')
        reports.append(checked)
    if reports[0]!=reports[1]:raise AssertionError('independent review mismatch')
    for pair in reports[1]['total']['pairs']:
        from decimal import Decimal
        assert Decimal(pair['mapped_difference_l2_ratio'])==Decimal('.5')
        assert Decimal(pair['direction_projection'])==Decimal('.5')
    metadata=dict(shape=list(shape),slabs=5,blocks=2,statistical_arrays_identical=True,
        independent_reviews_identical=True,each_scan_fixture_bytes_read=reference['field_bytes_read'],
        total_fixture_bytes_read=reference['field_bytes_read']+candidate['field_bytes_read'],
        production_io_driver=False,production_resource_verified=False,full_scan_authorized=False,
        peak_rss_bytes=old.peak_rss_bytes(),arithmetic=candidate['arithmetic'],
        sources=[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in (Path(old.__file__),Path(new.__file__),Path(__file__))])
    with (output/'metadata.json').open('x') as f:json.dump(metadata,f,indent=2);f.write('\n')
    return metadata


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    print(json.dumps(exercise(p.parse_args().output),sort_keys=True))
