"""Fixed tiny synthetic fixture; explicit slab calls, no production input option."""
import copy
import hashlib
import json
from pathlib import Path
from decimal import Decimal
import numpy as np
from operations import x20_85889_chord_scan as original
from operations import x20_85889_chord_scan_reuse as reuse
from operations import x20_85889_chord_scan_square as square
from handoff.audit_tools.review_x20_85889_chord_scan import review


def exercise(output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    shape = (129, 2, 3)
    x = np.arange(np.prod(shape), dtype='<f8').reshape(shape) % 11 + 2
    y = np.flip(x, axis=0) + 3
    fields = [x, .5*x+4, .25*x+6, y, .5*y+4, .25*y+6]
    claims = []
    for i, a in enumerate(fields):
        p = output/f'synthetic-{i}.bin'
        raw = a.tobytes()
        with p.open('xb') as f:
            f.write(raw)
        claims.append(dict(path=str(p), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    reference = original.scan(claims, list(shape), lambda row: None)
    # 旧scan负责这个小夹具的文件证据。候选仅显式消费以下同一组只读bytes，
    # 复用其审阅外壳不声称候选执行过生产hash/I/O生命周期。
    buffers = [Path(c['path']).read_bytes() for c in claims]
    for c, raw in zip(claims, buffers):
        assert hashlib.sha256(raw).hexdigest() == c['sha256']
    arrays = [np.frombuffer(raw, dtype='<f8').reshape(shape) for raw in buffers]
    reports = []
    for name, kernel in (('reuse', reuse.slab_statistics), ('square', square.slab_statistics)):
        candidate = copy.deepcopy(reference)
        rows = []
        for start in range(0, shape[0], 32):
            n = min(32, shape[0]-start)
            row = kernel([a[start:start+n] for a in arrays])
            row.update(first_group=start, group_count=n, block=start//128)
            rows.append(row)
        assert rows == reference['slabs']
        candidate['slabs'] = rows
        candidate['synthetic_explicit_slab_wiring'] = True
        candidate['file_evidence_from_original_scan'] = True
        with (output/f'{name}-scan.json').open('x') as f:
            json.dump(candidate, f, indent=2, allow_nan=False)
        checked = review(json.loads((output/f'{name}-scan.json').read_text()))
        assert checked == review(reference)
        with (output/f'{name}-review.json').open('x') as f:
            json.dump(checked, f, indent=2, allow_nan=False)
        reports.append(checked)
    assert reports[0] == reports[1]
    for pair in reports[1]['total']['pairs']:
        assert Decimal(pair['mapped_difference_l2_ratio']) == Decimal('.5')
        assert Decimal(pair['direction_projection']) == Decimal('.5')
    forged = copy.deepcopy(candidate)
    forged['slabs'][0]['pairs'][0]['reconstruction_error_square'][0] = '1e40'
    try:
        review(forged)
    except ValueError:
        pass
    else:
        raise AssertionError('forged reconstruction accepted')
    metadata = dict(shape=list(shape), slabs=5, blocks=2, independent_reviews_identical=True,
        complete_slabs_equal=True, input_arrays_readonly=all(not a.flags.writeable for a in arrays),
        synthetic_original_scan_bytes_read=reference['field_bytes_read'],
        synthetic_shared_buffer_bytes_read=sum(map(len,buffers)),
        total_fixture_bytes_read=reference['field_bytes_read']+sum(map(len,buffers)),
        arithmetic=reference['arithmetic'], peak_rss_bytes=original.peak_rss_bytes(),
        production_io_driver=False, production_resource_verified=False,
        controlled_speedup_measured=False, full_scan_authorized=False)
    with (output/'metadata.json').open('x') as f:
        json.dump(metadata, f, indent=2, allow_nan=False)
    return metadata


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('output', type=Path)
    print(json.dumps(exercise(p.parse_args().output), sort_keys=True))
