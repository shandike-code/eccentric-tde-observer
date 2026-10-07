"""86304 receipt identity and bounded files. Standard library only."""
import hashlib, json, math, os, stat
from pathlib import Path
SCHEMA='86304-radiation-resource-v1'
STATUS='86304_resource_complete_requires_review'
SOURCE_JOB=86304
SHAPE=[9632,32,4096]
RUN='outputs/hpc/x20-85889-relaxed-feedback-20261007'
KERNEL='operations/x20_85889_chord_scan_diagonal.py'
KERNEL_SHA='a3737320592fac5511d5f8c979524919b5fd9229e36634b64b7e8437cc0b0896'
ERRSTATE=dict(divide='warn',over='warn',under='ignore',invalid='warn')
ARITHMETIC=dict(rounding_mode_code=0,nmant=63,maxexp=16384,numpy='2.5.2')
PROBE_PHASES=['field-hash-before']+[f'{k}-{i}' for i in range(6) for k in ('slice-read','slice-hash')]+['slab']+[f'slice-reread-{i}' for i in range(6)]+['field-hash-after']
ALL_PHASES=['allocation-code','source-before']+PROBE_PHASES+['source-after','code-after']
PREFIX='operations/x20_86304_radiation_'
REQUIRED=[PREFIX+x for x in ('resource.py','resource.sbatch','contract.py','live.py','receipt.py')]+['handoff/audit_tools/review_x20_86304_radiation_resource.py',KERNEL,'operations/x20_85889_chord_scan_square.py','operations/x20_85889_chord_scan.py']
IDENTITY_REQUIRED=[KERNEL,'operations/x20_85889_chord_scan_square.py','operations/x20_85889_chord_scan.py',PREFIX+'resource.py',PREFIX+'contract.py']
def loads(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError('duplicate JSON key')
            out[key] = value
        return out
    def constant(value): raise ValueError('nonfinite JSON constant: ' + value)
    out = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    def finite(x):
        if type(x) is float and not math.isfinite(x): raise ValueError('nonfinite JSON number')
        if isinstance(x, dict):
            for v in x.values(): finite(v)
        elif isinstance(x, list):
            for v in x: finite(v)
    finite(out)
    return out

def bounded_bytes(path, limit):
    path = Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)): raise ValueError('ancestor link')
    before = path.lstat()
    signature = lambda x:(x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit: raise ValueError('ordinary bounded file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if signature(os.fstat(stream.fileno())) != signature(before): raise ValueError('small source replaced')
        raw = stream.read(before.st_size+1)
        if (len(raw) != before.st_size or signature(os.fstat(stream.fileno())) != signature(before) or
            signature(path.lstat()) != signature(before)): raise ValueError('small source changed')
    return raw

def read(path):
    return loads(bounded_bytes(path, 32*1024**2))

def scheduler_tokens(text):
    result = {}
    for item in text.split():
        if '=' in item:
            key, value = item.split('=', 1)
            if key in result: raise ValueError('duplicate scheduler key')
            result[key] = value
    return result

def exact(a, b):
    """Type-aware recursive equality; decimal strings and signed float zero survive."""
    if type(a) is not type(b): return False
    if isinstance(a, dict): return list(a) == list(b) and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if type(a) is float: return math.isfinite(a) and math.isfinite(b) and a.hex() == b.hex()
    return a == b

def check_errstate(value):
    # 键序不属于 NumPy 策略语义；值与键集合均固定，不调用 seterr 修正。
    if type(value) is not dict or value != ERRSTATE: raise ValueError('unapproved NumPy errstate')

def document_sha(value):
    """External ticket hashes canonical JSON content, never a claimed file SHA."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()

def check_identity(identity, code, production=False):
    check_errstate(identity['errstate'])
    root = Path(identity['checkout'])
    if not root.is_absolute() or '..' in root.parts: raise ValueError('identity checkout')
    modules = identity['modules']; paths = set()
    if type(modules) is not dict or not modules: raise ValueError('module origins missing')
    for name, row in modules.items():
        relative = row['relative_path']; p = Path(relative)
        if p.is_absolute() or '..' in p.parts or relative not in code: raise ValueError('unfrozen imported module')
        if (row['file'] != str(root/p) or row['origin'] != row['file'] or
            not exact(row['fingerprint'], code[relative])): raise ValueError('import origin/SHA')
        paths.add(relative)
    required = IDENTITY_REQUIRED + ([PREFIX+'live.py'] if production else [])
    if any(p not in paths for p in required): raise ValueError('missing actual imported dependency')
    environment = identity['environment']
    for k in ('executable', 'numpy_file', 'numpy_origin'):
        if not Path(environment[k]).is_absolute(): raise ValueError('environment path')
    if (environment['numpy_file'] != environment['numpy_origin'] or
        environment['numpy_version'] != '2.5.2' or not environment['python_version']):
        raise ValueError('environment identity')

def check_identity_pair(before, after, code, production=False):
    for identity in (before, after): check_identity(identity, code, production)
    if (before['checkout'] != after['checkout'] or
        not exact(before['environment'], after['environment'])): raise ValueError('runtime changed')
    for name, row in before['modules'].items():
        if not exact(row, after['modules'].get(name)): raise ValueError('imported dependency changed')

def reviewer_origins(repo, code):
    """CLI审阅进程自身的项目导入来源；仅标准库，不导入数值核。"""
    import sys
    repo = Path(repo).resolve(); result = {}
    stems = {Path(p).stem for p in code}
    for name, module in sorted(list(sys.modules.items())):
        file = getattr(module, '__file__', None)
        if not file: continue
        path = Path(file).absolute(); resolved = path.resolve()
        local = resolved.is_relative_to(repo) and not any(x.startswith('.venv') for x in resolved.relative_to(repo).parts)
        expected = name.split('.')[0] in ('operations','handoff','hpc','scripts','eccentric_tde_observer') or name in stems
        if not local and not expected: continue
        if path != resolved or not resolved.is_relative_to(repo): raise ValueError('foreign reviewer import')
        relative = str(resolved.relative_to(repo)); origin = getattr(getattr(module,'__spec__',None),'origin',None) or file
        if Path(origin).absolute() != resolved or relative not in code: raise ValueError('reviewer origin')
        raw = bounded_bytes(resolved,32*1024**2)
        fingerprint = dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if not exact(fingerprint,code[relative]): raise ValueError('reviewer code SHA')
        result[name] = dict(relative_path=relative,file=str(resolved),origin=str(resolved),fingerprint=fingerprint)
    required = ['handoff/audit_tools/review_x20_86304_radiation_resource.py',
        PREFIX+'contract.py','handoff/audit_tools/review_x20_85889_chord_scan.py']
    if any(p not in [row['relative_path'] for row in result.values()] for p in required):
        raise ValueError('reviewer dependency missing')
    return result

def check_code(manifest,expected):
    if not exact(manifest,expected) or any(p not in manifest for p in REQUIRED): raise ValueError('external complete code freeze')
    pins={KERNEL:KERNEL_SHA,'operations/x20_85889_chord_scan_square.py':'61e6c6d559975f7f863282209eb1ad016c4594f7f898f0c7e0a5d515878c862b','operations/x20_85889_chord_scan.py':'9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643'}
    if any(manifest[p]['sha256']!=s for p,s in pins.items()): raise ValueError('frozen numerical dependency')

def new_job(job):
    if type(job) is not str or not job.isdigit() or job in ('85889','86061','86191','86290','86304'): raise ValueError('new execution job required')
    return job

def fields(binding):
    if type(binding['job_id']) is not int or binding['job_id']!=86304 or binding['version']!='86304-json-binding-v1': raise ValueError('source job/version')
    if binding['numerical_commit']!='fbfe81fb7ec4e9714e256ec460b483130db5c254': raise ValueError('source numerical commit')
    hashes=['a934ab2420789bdd11642507ecdea73c7912e7df6cc9a4701ca7fdadc99e3bdc','bc12757f0601fa901f04e6672088d5c7b865283781fd1debe611dee735ef69b8','b1477a001886ed9a408e6e01baab4c4d2f1154a73a04d81d5a98bd1773991f72','d75e2bff1afaab2f069d89749d391b73ec8de5cd4be0d5c171cef03efd4b75e7','ae93ac67bdd73469636ddc5e66ae40792e2ee81f976d56f3e5562cd3d3ac2245','2c1ebffb2e13f170dc0dafdfaf379dfd21760b77c2fbe4c9b87dcbc4e2cacf6d']
    out=[]
    for branch in ('accelerated','historical'):
        for endpoint in ('previous','final','mapped_final'):
            row=binding['fields'][branch][endpoint]
            expected=dict(path=f'{RUN}/{branch}/endpoints-map08/{endpoint}.dat',size_bytes=10099884032,sha256=hashes[len(out)])
            if not exact(row,expected): raise ValueError('fixed 86304 field')
            out.append(row)
    return out
def check_submission(ticket, commit, code, binding, job, run, started, allocation, terminal):
    """Independent launch receipt + raw scheduler association; no authenticity claim."""
    script = 'operations/x20_86304_radiation_resource.sbatch'
    root = ticket['workdir']; command = str(Path(root)/script)
    expected = dict(job_id=str(job), expected_commit=commit, run=run,
        sbatch_file=command, sbatch_fingerprint=code[script],
        code_content_sha256=document_sha(code), binding_content_sha256=document_sha(binding),
        digest_encoding='json-ascii-compact-insertion-order-v1')
    for key, value in expected.items():
        if not exact(ticket[key], value): raise ValueError('external submission binding: '+key)
    if not Path(root).is_absolute() or not Path(run).is_relative_to(Path(root)/'outputs/hpc'):
        raise ValueError('submission workdir/run')
    if (type(ticket['argv']) is not list or ticket['argv'] != ['sbatch', '--parsable', command] or
        ticket['stdout'].strip().split(';')[0] != str(job) or type(ticket['returncode']) is not int or
        ticket['returncode'] != 0): raise ValueError('submission command/return')
    exports = ticket['exports']
    for key, value in dict(RADIATION_EXPECTED_COMMIT=commit, RADIATION_RUN=run).items():
        if exports[key] != value: raise ValueError('submission environment')
    for key in ('RADIATION_SOURCES','RADIATION_CODE_FREEZE'):
        if not Path(exports[key]).is_absolute(): raise ValueError('submission parameter path')
    expected_arguments = {key:exports['RADIATION_'+key.upper()] for key in ('expected_commit','run','sources','code_freeze')}
    if not exact(started['arguments'], expected_arguments): raise ValueError('executed arguments differ from submission')
    a, b = ticket['request_unix'], ticket['returned_unix']
    if (type(a) not in (int,float) or type(b) not in (int,float) or not math.isfinite(a) or
        not math.isfinite(b) or not 0 <= a <= b <= terminal['observed_unix'] or
        a > started['started_unix']): raise ValueError('submission times')
    for receipt in (allocation, terminal):
        tokens = scheduler_tokens(receipt['scontrol'])
        if any(tokens.get(k) != v for k,v in dict(JobId=str(job),Command=command,WorkDir=root).items()):
            raise ValueError('scheduler submission association')
        if 'SubmitTime' in tokens and tokens['SubmitTime'] != ticket['submit_time']:
            raise ValueError('scheduler submit time')
    if started['execution'] != dict(job_id=str(job),workdir=root,run=run,driver=str(Path(root)/'operations/x20_86304_radiation_resource.py')):
        raise ValueError('started submission association')

BINDING_CONTENT_SHA='bc2597332898c2a5e3f0f86b64242af32f20f01959191d3fdeee7c3c9e3c0d8a'
def check_binding(binding):
    fields(binding)
    if document_sha(binding)!=BINDING_CONTENT_SHA: raise ValueError('independent fixed 86304 JSON binding')
