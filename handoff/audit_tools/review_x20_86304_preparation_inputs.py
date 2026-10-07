"""Independent NumPy oracle for synthetic component fingerprints; no live import."""
import hashlib
import io
import zipfile
import numpy as np


def fingerprint(array):
    if array.dtype.hasobject or (array.dtype.kind in 'fc' and not np.isfinite(array).all()):
        raise ValueError('oracle finite dtype')
    return dict(dtype=array.dtype.str, shape=list(array.shape), sha256=hashlib.sha256(array.tobytes(order='C')).hexdigest())


def review_synthetic(raw, evidence):
    """Only caller-created tiny fixtures; never a production source acceptance."""
    if type(raw) is not bytes or len(raw) >= 65536: raise ValueError('tiny synthetic input')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if not 0 < len(members) <= 32 or len({x.filename for x in members}) != len(members):
            raise ValueError('tiny unique oracle members')
        if sum(x.file_size for x in members) >= 65536: raise ValueError('tiny uncompressed oracle input')
        for member in members:
            with archive.open(member) as stream:
                version = np.lib.format.read_magic(stream)
                if version != (1, 0): raise ValueError('synthetic NPY version')
                shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
                if dtype.hasobject or any(type(n) is not int or n < 0 for n in shape):
                    raise ValueError('oracle header dtype/shape')
                import math
                if math.prod(shape)*dtype.itemsize + stream.tell() != member.file_size:
                    raise ValueError('oracle header length')
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        arrays = {k: archive[k] for k in archive.files}
    if sum(x.nbytes for x in arrays.values()) >= 65536: raise ValueError('tiny oracle arrays')
    expected = {k: fingerprint(v) for k, v in arrays.items()}
    if evidence['arrays'] != expected: raise ValueError('array fingerprint disagreement')
    mirrors = {}
    for field, parent in [('density_g_cm3', 'density_parent'), ('temperature_k', 'temperature_parent'),
                          ('hydrogen_fraction', 'hydrogen_parent'), ('helium_fraction', 'helium_parent')]:
        mirrors[parent] = fingerprint(np.concatenate([arrays[field], arrays[field][::-1]], axis=0))
    mirrors['specific_material_energy_erg_g'] = expected['specific_material_energy_erg_g']
    if evidence['mirrors'] != mirrors: raise ValueError('mirror fingerprint disagreement')
    for name in ('exact_trial_decode_verified', 'physical_old_r20_verified', 'process_guard_verified', 'live_native_recomputed'):
        if evidence[name] is not False: raise ValueError('unsupported qualification')
    return dict(synthetic_only=True, all_arrays_verified=len(arrays), mirrors_verified=4,
                actual_source_manifest_prepared=False, production_resource_verified=False)
