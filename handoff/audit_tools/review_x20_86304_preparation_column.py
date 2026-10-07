"""Independent standard-library oracle; does not import component or NumPy."""
import json
import math
import struct
import sys


def review(value):
    if value['schema'] != '86304-column-synthetic-v1': raise ValueError('schema')
    for key in ('header_configuration_integrated','all_scientific_temporaries_metered',
                'whole_lifecycle_guard_verified','production_authorized'):
        if value[key] is not False: raise ValueError('qualification')
    if type(value['checkpoints']) is not int or value['checkpoints'] != 32: raise ValueError('checkpoints')
    expected = {}; edges = []
    for phase in range(3):
        widths = [(1 + (i % 4) / 4) / (2 ** phase) for i in range(128)]
        edge = [-sum(widths)]
        for width in widths + widths[::-1]: edge.append(edge[-1] + width)
        edges.extend(edge)
    expected['edge_cm'] = ([3,257], edges)
    expected['density_g_cm3'] = ([3,256], [float(2 ** p) for p in range(3) for _ in range(256)])
    expected['temperature_k'] = ([3,256], [8192.] * 768)
    expected['hydrogen_fraction'] = ([3,256,2], [.75,.25] * 768)
    expected['helium_fraction'] = ([3,256,3], [.5,.25,.25] * 768)
    if set(value['arrays']) != set(expected): raise ValueError('arrays')
    for key, (shape, numbers) in expected.items():
        a = value['arrays'][key]
        if a['shape'] != shape or any(type(n) is not int for n in a['shape']) or a['dtype'] != '<f8': raise ValueError('layout')
        if a['hex'] != struct.pack('<' + 'd' * len(numbers), *numbers).hex(): raise ValueError('array bytes')
    entries=[]
    for key,n in [('cell_mass_g_cm2',128),('density_g_cm3',384),('temperature_k',384),('hydrogen_fraction',768),('helium_fraction',1152)]:
        entries.extend([['column:'+key+':finite-mask', n],['column:'+key+':lower-mask', n]])
        if key.endswith('fraction'): entries.append(['column:'+key+':upper-mask',n])
    for label,n in [('half-width',3072),('full-width',6144),('half-thickness',24),('left-negative',24),('right-negative',24),('cumulative-width',6144),('shifted-edge',6144),('edge',6168),('midplane-absolute',24)]:
        entries.append(['column:'+label,n])
    for key,n in [('density_g_cm3',6144),('temperature_k',6144),('hydrogen_fraction',12288),('helium_fraction',18432)]:
        entries.append(['column:'+key+':mirror',n])
    for key,(shape,_) in expected.items(): entries.append(['column:'+key+':output-finite-mask',math.prod(shape)])
    if any(type(n) is not int for _,n in value['entries']) or value['entries'] != entries: raise ValueError('ledger')
    total=sum(n for _,n in entries)
    if type(value['reserved_bytes']) is not int or value['reserved_bytes'] != total: raise ValueError('total')
    return dict(verified=True, reserved_bytes=total, entries=len(entries), scalar_values=sum(len(v[1]) for v in expected.values()), production_authorized=False)


if __name__ == '__main__': print(json.dumps(review(json.load(open(sys.argv[1]))), sort_keys=True))
