"""Independent small receipt/raw-NPY review. Does not import native or adapter."""
import ast
import base64
import hashlib
import io
import json
import math
import zipfile


def review(record, pack, root, linux):
    if type(record['returncode']) is not int or record['returncode'] != 0 or record['stderr']:
        raise ValueError('worker failed')
    if not 0 < record['elapsed_s'] < 20:
        raise ValueError('outer synthetic deadline')
    result = json.loads(record['stdout'])
    for k in ('synthetic','startup_isolated_no_site','environment_preload_project_free',
              'exact_trial_original_passed','original_column_passed'):
        if result[k] is not True: raise ValueError('missing success: '+k)
    for k in ('production_ready','whole_lifecycle_guard_verified','complete_native_context_verified'):
        if result[k] is not False: raise ValueError('unsupported qualification')
    raw = base64.b64decode(result['synthetic_npz_base64'],validate=True)
    if len(raw) != result['npz_bytes'] or not 0 < len(raw) < 65536:
        raise ValueError('tiny NPZ')
    arrays, payloads = {}, {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(x.file_size for x in archive.infolist()) >= 65536:
            raise ValueError('tiny decoded source')
        for info in archive.infolist():
            data = archive.read(info)
            if data[:8] != b'\x93NUMPY\x01\x00': raise ValueError('fixture NPY version')
            offset = 10 + int.from_bytes(data[8:10],'little')
            h = ast.literal_eval(data[10:offset].decode().strip())
            if h['fortran_order'] is not False or h['descr'] not in ('<f8','<i8'):
                raise ValueError('fixture dtype/order')
            payload = data[offset:]
            if len(payload) != math.prod(h['shape'])*8: raise ValueError('array length')
            key = info.filename[:-4]
            if key in arrays: raise ValueError('duplicate')
            arrays[key] = dict(dtype=h['descr'],shape=list(h['shape']),sha256=hashlib.sha256(payload).hexdigest())
            payloads[key] = payload
    expected = result['independent_raw_fingerprints']
    if expected['arrays'] != arrays: raise ValueError('raw arrays')
    for field,parent in [('density_g_cm3','density_parent'),('temperature_k','temperature_parent'),
                         ('hydrogen_fraction','hydrogen_parent'),('helium_fraction','helium_parent')]:
        row=arrays[field]; payload=payloads[field]; count=row['shape'][0]; width=len(payload)//count
        mirror=payload+b''.join(payload[i*width:(i+1)*width] for i in reversed(range(count)))
        sha=hashlib.sha256(mirror).hexdigest()
        if result['mirror_sha256'][parent] != sha or expected['mirrors'][parent] != dict(dtype=row['dtype'],shape=[count*2,*row['shape'][1:]],sha256=sha):
            raise ValueError('mirror bytes')
    seen=result['executed_project_origins']
    if not {'operations.common_step21_directions','scripts.phase7b5x_full_depth_block_probe'} <= seen.keys():
        raise ValueError('missing original modules')
    for name,facts in seen.items():
        row=pack['modules'][name];source=row['source'].encode()
        if hashlib.sha256(source).hexdigest()!=row['sha256'] or len(source)!=row['size_bytes']:
            raise ValueError('code source digest')
        path=root+'/'+row['path']
        if facts != dict(file=path,spec_origin=path):raise ValueError('actual memory origin')
    if result['frozen_project_module_count'] != len(pack['modules'])-1:
        raise ValueError('closure count')
    failures=result['failures']
    if set(failures)!= {'encoded_state','temperature_k','density_g_cm3','step_duration_s','path:stat','path:open','path:readlink'}:
        raise ValueError('missing failure case')
    if linux:
        if result['seal']!='linux-seccomp-tsync-allowlist-v1' or any(type(failures['path:'+k]) is not int or failures['path:'+k]!=1 for k in ('stat','open','readlink')):
            raise ValueError('Linux path denial')
    meter=result['meter']
    if meter['decompressed_member_returned_bytes'] != sum(len(v)+128 for v in payloads.values()):
        raise ValueError('fixture decompression accounting')
    if meter['all_native_temporaries_bounded'] is not False or meter['device_io_measured'] is not False:
        raise ValueError('unsupported metering claim')
    if not 0<result['resources']['peak_rss_bytes']<1024**3 or not 0<result['resources']['elapsed_s']<120:
        raise ValueError('resource gate')
    return dict(synthetic_verified=True,original_project_modules=len(seen),raw_arrays=len(arrays),
                mirror_arrays=4,linux_post_environment_denial_verified=linux,
                whole_lifecycle_guard_verified=False,production_ready=False)
