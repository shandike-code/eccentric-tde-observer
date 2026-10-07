"""Standard-library receipt review without decoder imports."""
import hashlib
import struct


def review(doc,expected_platform):
    if doc['schema']!='86304-inflate-synthetic-v1' or doc['platform']!=expected_platform:raise ValueError('identity')
    if doc['synthetic'] is not True:raise ValueError('synthetic')
    for k in ('production_authorized','whole_lifecycle_guard_verified','all_scientific_temporaries_metered'):
        if doc[k] is not False:raise ValueError('qualification')
    expected=b''.join(struct.pack('<d',float(i%17)) for i in range(257*32))
    if len(doc['results'])!=2:raise ValueError('missing case')
    for r,method in zip(doc['results'],(0,8)):
        if type(r['method']) is not int or r['method']!=method:raise ValueError('method')
        if r['array_bytes']!=len(expected) or r['array_sha256']!=hashlib.sha256(expected).hexdigest():raise ValueError('array')
        meter=r['meter']
        for k in ('private_zlib_workspace_metered','all_scientific_temporaries_metered','total_rss_bound_claimed','production_authorized'):
            if meter[k] is not False:raise ValueError('meter scope')
        reserved=meter['explicit_payload_capacity_reserved_bytes']
        if type(reserved) is not int or not 2*len(expected)<reserved<512*1024**2:raise ValueError('reservation')
        if len(meter['events'])!=1:raise ValueError('events')
        e=meter['events'][0]
        if e['decompressed_payload_bytes']!=len(expected)+128:raise ValueError('NPY bytes')
        for k in ('max_input_bytes','max_output_bytes'):
            if type(e[k]) is not int or not 0<e[k]<=65536:raise ValueError('chunk ceiling')
        if type(e['calls']) is not int or e['calls']<2:raise ValueError('chunk count')
    return dict(independent_expected_bytes=True,platform=expected_platform,production_authorized=False)
