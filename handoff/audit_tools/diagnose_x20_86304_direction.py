"""Finite response direction only; no production imports, dat, ODE, or scheduler."""
import argparse
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import stat
import subprocess
import zipfile

import numpy as np

ROOT = Path('outputs/review-20260925')
ENDS = ('previous', 'final')
KEYS = tuple(itertools.product(('old', 'new'), ('historical', 'accelerated'), ENDS))
EPS = np.finfo(np.float64).eps
ETA = np.nextafter(0., 1.)
PINS = (
    (85889, 16, 'x20-85875-matched-85889-received', 'complete-1791262858167332668',
     '9555a78a77b9025e30405684dee2669d9e43baee',
     'handoff/evidence/20261006-x20-85889-final-review.json', 87194,
     '61eaea4db3ba0fb87adce29c13ab42bc1f158068e634e9798b67ddc3d16c2729',
     'ed219eef3121dea9cd23e3e328bdd2de72811e7a51ec4af897855046b82cf99f'),
    (86304, 8, 'x20-relaxed-feedback-86304-final-received', 'complete-1791311963190402946',
     'fbfe81fb7ec4e9714e256ec460b483130db5c254',
     'handoff/evidence/20261007-x20-86304-final-review.json', 57263,
     '7e680adf4f4f0908f51f8a88b690731955a6493319f795b0e653e5902dadf840',
     'cd05603f84054c987f73270cc23f32076e41c2d9b8e8f9f0c8645f458faf96ae'),
)
OLD = Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
REFERENCE = ROOT/'common-step21-76808-received/inputs'
EXTERNAL = {
    'physical_old_time_level.npz': (OLD, 17159976, '33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455'),
    'outer_base_material.npz': (REFERENCE/'outer_base_material.npz', 27774, '36434a29123e2387195b77713baffaecd046f7d6c0297a5d0d95a74319e22eda'),
    'base_residual.npy': (REFERENCE/'base_residual.npy', 4224, 'b6f337ce30d323acada31ea9f3e1772ccb2be1075753f432ab13a8e299ee2a45'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_identity(era, job, pair, commit):
    expected = {'old': (85889,16,PINS[0][4]), 'new': (86304,8,PINS[1][4])}
    require(era in expected and (job,pair,commit) == expected[era], 'job/map/commit identity')


def read_bound(path, size, digest, limit=8*1024**2):
    """Authenticate exactly the bytes subsequently parsed; reject links and changes."""
    p = Path(path)
    require(p.suffix != '.dat' and 0 <= size <= limit, 'read scope/size')
    require(not any(q.is_symlink() for q in (p, *p.parents)), 'symlink source')
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == size, 'file size/type')
        data = f.read(size+1)
        signature = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        require(signature(before) == signature(os.fstat(f.fileno())) == signature(p.stat()), 'source changed')
    require(len(data) == size and sha(data) == digest, 'source SHA')
    return data


def unique(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, 'duplicate key')
        out[k] = v
    return out


def parse(data):
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def unpack(data, limit=1024**2):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        require(len({x.filename for x in infos}) == len(infos), 'duplicate NPZ member')
        require(sum(x.file_size for x in infos) <= limit, 'NPZ expansion')
        require(all(x.filename.endswith('.npy') and '/' not in x.filename for x in infos), 'NPZ member')
    with np.load(io.BytesIO(data), allow_pickle=False) as z:
        result = {k: z[k].copy() for k in z.files}
    require(all(x.dtype.kind in 'biufUS' for x in result.values()), 'NPZ dtype')
    require(all(np.isfinite(x).all() for x in result.values() if x.dtype.kind in 'biuf'), 'nonfinite NPZ')
    return result


def validate(v, mass):
    require(v.dtype == np.dtype('float64') and v.shape == (512,) and np.isfinite(v).all(), 'vector shape/dtype/finite')
    require(mass.dtype == np.dtype('float64') and mass.shape == (128,) and np.isfinite(mass).all() and np.all(mass > 0), 'mass domain')


def product(a, b):
    c = a*b
    require(np.isfinite(c).all(), 'nonfinite product')
    require(not np.any((a != 0) & (b != 0) & (c == 0)), 'product underflow')
    return c


def norms(v, mass):
    validate(v, mass)
    x = v.reshape(128, 4)
    square = product(x, x)
    weighted = product(product(mass[:, None], x), x)
    ans = np.array([np.sqrt(np.sum(square)), np.sqrt(np.sum(weighted)/mass.sum()),
                    np.sqrt(np.max(np.sum(square, axis=1)))])
    require(np.isfinite(ans).all(), 'nonfinite norm')
    return ans


def inner(x, y, mass):
    validate(x, mass); validate(y, mass)
    result = float(np.sum(product(product(mass[:, None], x.reshape(128, 4)), y.reshape(128, 4)))/mass.sum())
    require(np.isfinite(result), 'nonfinite inner')
    return result


def identity(d, alt, endpoints):
    scale = sum(np.abs(x) for x in endpoints)
    bound = 32*EPS*scale + 8*ETA
    require(np.isfinite(scale).all() and np.isfinite(d).all() and np.isfinite(alt).all(), 'identity finite')
    error = np.abs(d-alt)
    require(np.all(error <= bound), 'four-difference identity')
    return dict(max_abs_error=float(error.max()), max_bound=float(bound.max()),
                maximum_fraction_of_bound=float(np.max(np.divide(error, bound, out=np.zeros_like(error), where=bound != 0))))


def calculate(states, mass):
    require(set(states) == set(KEYS), 'eight endpoint keys')
    for v in states.values():
        validate(v, mass)
    rows = {}
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        for ho, ao, hn, an in itertools.product(ENDS, repeat=4):
            h0, a0, h1, a1 = [states[k] for k in [('old','historical',ho), ('old','accelerated',ao), ('new','historical',hn), ('new','accelerated',an)]]
            cold, cnew, wh, wa = h0-a0, h1-a1, h1-h0, a1-a0
            d, alt = cnew-cold, wh-wa
            check = identity(d, alt, [h0,a0,h1,a1])
            vectors = dict(C_old=cold, C_new=cnew, W_H=wh, W_A=wa, D=d, D_alternative=alt)
            nn = {k: norms(v, mass).tolist() for k,v in vectors.items()}
            ii = {k: inner(v, cold, mass) for k,v in vectors.items()}
            denominator = ii['C_old']
            projections = {k: ii[k]/denominator if denominator else None for k in ('D','W_H','W_A')}
            cosine_den = nn['C_old'][1]*nn['C_new'][1]
            rows['__'.join((ho,ao,hn,an))] = dict(endpoints=[ho,ao,hn,an], vectors={k:v.tolist() for k,v in vectors.items()},
                norms=nn, mass_inner_with_C_old=ii, projections=projections,
                mass_norm_ratio=nn['C_new'][1]/nn['C_old'][1] if nn['C_old'][1] else None,
                mass_cosine=ii['C_new']/cosine_den if cosine_den else None, identity=check)
    return rows


def claim_map(manifest):
    claims = unique((c['path'],c) for c in manifest['files'])
    require(all(Path(k).as_posix() == k and not Path(k).is_absolute() and '..' not in Path(k).parts for k in claims), 'manifest paths')
    return claims


def run(target):
    require(not target.exists(), 'output exists')
    sources, states, audits, declarations, trials = [], {}, {}, {}, []
    def bound(p, n, digest, limit=8*1024**2):
        b = read_bound(p,n,digest,limit)
        sources.append(dict(path=str(p),size_bytes=n,sha256=digest))
        return b
    for era, pin in zip(('old','new'), PINS):
        job, pair, directory, stem, commit, audit_path, audit_size, audit_sha, manifest_sha = pin
        source_identity(era,job,pair,commit)
        audit = parse(bound(audit_path,audit_size,audit_sha))
        require(audit['job_id'] == job and audit['numerical_commit'] == commit and audit['scheduler_terminal_verified'] and audit['numerical_artifacts_complete'], 'audit identity')
        require(not audit['reference_calibration_eligible'] and audit['accepted_outer_steps'] == 20, 'audit scope')
        folder = ROOT/directory
        n = 1623461 if era == 'old' else 813404
        external = bound(ROOT/(stem+'.json'),n,manifest_sha)
        archived = bound(folder/'ARCHIVE_MANIFEST.json',n,manifest_sha)
        require(external == archived, 'manifest mismatch')
        claims = claim_map(parse(archived))
        def load(rel, npz=False):
            c = claims[rel]
            b = bound(folder/rel,c['size_bytes'],c['sha256'],1024**2-1 if npz else 8*1024**2)
            return unpack(b) if npz else parse(b)
        declaration = load('declaration.json')
        require(declaration['git_commit'] == commit and declaration['both_branches_identical_x20'] and not declaration['physical_dt_changed'], 'declaration identity')
        declarations[era] = declaration; audits[era] = audit
        trial = load('inputs/trial_material.npz',True); trials.append(trial)
        require(claims['inputs/trial_material.npz']['sha256'] == EXTERNAL['outer_base_material.npz'][2], 'trial SHA')
        for branch,end in itertools.product(('historical','accelerated'), ENDS):
            response = load(f'{branch}/pair{pair:02d}/{end}_response.npz',True)
            states[era,branch,end] = response['residual']
    external_arrays = {}
    for name,(p,n,digest) in EXTERNAL.items():
        for declaration in declarations.values():
            matches = [c for c in declaration['claims'] if Path(c['path']).name == name]
            require(len(matches) == 1 and matches[0]['size_bytes'] == n and matches[0]['sha256'] == digest, 'external binding')
        data = bound(p,n,digest,n if name == 'physical_old_time_level.npz' else 1024**2-1)
        external_arrays[name] = unpack(data,32*1024**2 if name == 'physical_old_time_level.npz' else 1024**2) if name.endswith('.npz') else np.load(io.BytesIO(data),allow_pickle=False)
    base = external_arrays['outer_base_material.npz']; old = external_arrays['physical_old_time_level.npz']
    for trial in trials:
        require(set(trial) == set(base) and all(trial[k].dtype == base[k].dtype and trial[k].shape == base[k].shape and trial[k].tobytes() == base[k].tobytes() for k in base), 'trial arrays')
    require(int(base['phase_index']) == 1367 and float(base['step_duration_s']) == 889.419892762322 == float(old['step_duration_s'][1367]), 'phase/dt')
    require(np.array_equal(base['density_g_cm3'],old['density_g_cm3'][1367]), 'old density')
    mass = old['cell_mass_g_cm2']; r20 = external_arrays['base_residual.npy']
    require(np.array_equal(r20,base['base_residual']), 'r20 array')
    rn = norms(r20,mass)
    np.testing.assert_allclose(rn,[8.172006557889262,.2619104204778557,2.705001116611826],rtol=2e-12,atol=0)
    signal = np.array([declarations['old']['frozen_signal_scale'][k] for k in ('l2','mass_weighted','maximum_cell')])
    require(declarations['old']['frozen_signal_scale'] == declarations['new']['frozen_signal_scale'] and np.all(signal > 0), 'signal identity')
    comparisons = {}
    groups = [('old_cross',('old','historical'),('old','accelerated'),audits['old']['cross_history']['16']['residual_comparison']),
              ('new_cross',('new','historical'),('new','accelerated'),audits['new']['cross_history']['8']['residual_comparison'])]
    groups += [(b+'_window',('new',b),('old',b),audits['new']['pairs'][b+'8']['eight_map_window']) for b in ('historical','accelerated')]
    for name,b,a,saved in groups:
        comparisons[name] = {}
        for be,ae in itertools.product(ENDS,repeat=2):
            nn = norms(states[(*b,be)]-states[(*a,ae)],mass); key = be+'_vs_'+ae
            np.testing.assert_allclose(nn/rn,saved['frozen_r20']['vector_difference_over_frozen_r20_norms'][key],rtol=2e-12,atol=0)
            np.testing.assert_allclose(nn/signal,saved['vector_difference_over_frozen_80195_signal'][key],rtol=2e-12,atol=0)
            comparisons[name][key] = dict(norms=nn.tolist(),over_r20=(nn/rn).tolist(),over_signal=(nn/signal).tolist())
    code = []
    for rel in ('handoff/audit_tools/diagnose_x20_85889_energy.py','handoff/audit_tools/review_step21_control_windows.py'):
        actual = Path(rel).read_bytes()
        frozen = subprocess.check_output(['git','show','ccf6763a86e5eda294fe7ddd2d83273145f7a7ec:'+rel])
        require(actual == frozen, 'original norm code changed')
        code.append(dict(path=rel,sha256=sha(actual),size_bytes=len(actual)))
    result = dict(scope='finite stored response direction; no radiation Gram or error/ETA bound',
        endpoint_order=['old_H','old_A','new_H','new_A'],sources=sources,original_norm_code=code,
        input_vectors={'__'.join(k):v.tolist() for k,v in states.items()},mass=mass.tolist(),r20_norms=rn.tolist(),signal_norms=signal.tolist(),
        comparisons=comparisons,quadruples=calculate(states,mass),identity_coefficient=32,reduction_coefficient=64,
        accepted_outer_steps=20,new_material_steps=0,new_maps=0,new_feedback_pairs=0,new_production_authorized=False,
        reference_calibration_eligible=False,baseline_replaced=False,strict_error_bound=False)
    # All input bytes unchanged through the read-only diagnostic; no archive/dat reread.
    for s in sources:
        read_bound(s['path'],s['size_bytes'],s['sha256'],max(8*1024**2,s['size_bytes']))
    with target.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False); f.write('\n')
    print(json.dumps(dict(target=str(target),quadruples=len(result['quadruples']),sources=len(sources))))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True)
    run(p.parse_args().target)
