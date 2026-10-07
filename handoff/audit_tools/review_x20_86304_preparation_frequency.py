"""Standard-library synthetic receipt review, without importing the adapter."""
import ast
import base64
import hashlib
import io
import json
import math
import struct
import zipfile


def review(directory,pack,root,platform):
    outcome=json.loads((directory/'outcome.json').read_text())
    if (type(outcome['returncode']) is not int or outcome['returncode']!=0 or
            outcome['success'] is not True or outcome['reason'] is not None or
            outcome['kill_sent'] is not False or outcome['outer_limit_s']!=150. or
            not 0<outcome['elapsed_s']<150):raise ValueError('supervised completion')
    for k in ('whole_lifecycle_guard_verified','production_authorized'):
        if outcome[k] is not False:raise ValueError('qualification')
    for name in ('stdout','stderr'):
        raw=(directory/(name+'.log')).read_bytes()
        if outcome['outputs'][name]!=dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()):raise ValueError('log integrity')
    if (directory/'stderr.log').read_bytes():raise ValueError('stderr')
    r=json.loads((directory/'stdout.log').read_bytes())
    for k in ('production_authorized','whole_lifecycle_guard_verified','complete_native_context_verified'):
        if r[k] is not False:raise ValueError('qualification')
    for k in ('synthetic','startup_isolated_no_site','environment_preload_project_free'):
        if r[k] is not True:raise ValueError('fixture scope')
    if platform not in ('linux','darwin'):raise ValueError('external platform')
    if platform=='linux' and r['seal']!='linux-seccomp-tsync-allowlist-v1':raise ValueError('Linux seal')
    raw={k:base64.b64decode(v,validate=True) for k,v in r['source_bytes'].items()}
    if set(raw)!={'fixed','template','trial','base','residual','old','master'}:raise ValueError('roles')
    for k,v in raw.items():
        c=r['claims'][k]
        if c!=dict(path='synthetic/'+k+('.json' if k in ('fixed','template') else '.npy' if k=='residual' else '.npz'),size_bytes=len(v),sha256=hashlib.sha256(v).hexdigest()):raise ValueError('source bytes')
    def npy(data):
        if data[:8]!=b'\x93NUMPY\x01\x00':raise ValueError('fixture NPY version')
        offset=10+int.from_bytes(data[8:10],'little');h=ast.literal_eval(data[10:offset].decode().strip());v=data[offset:]
        if h['fortran_order'] is not False or h['descr'] not in ('<f8','<i8') or len(v)!=math.prod(h['shape'])*8:raise ValueError('NPY layout')
        return h,v
    arrays={};decoded_bytes=0
    for role in ('trial','base','old','master'):
        with zipfile.ZipFile(io.BytesIO(raw[role])) as z:
            if len(set(z.namelist()))!=len(z.namelist()):raise ValueError('ZIP duplicate')
            arrays[role]={}
            for name in z.namelist():
                v=z.read(name);decoded_bytes+=len(v);arrays[role][name[:-4]]=npy(v)
    if arrays['trial']!=arrays['base']:raise ValueError('trial/base byte identity')
    h,residual=npy(raw['residual'])
    if h['shape']!=(512,) or h['descr']!='<f8' or residual!=b'\0'*4096:raise ValueError('zero residual fixture')
    def array_fact(f,payload,shape):
        if f!=dict(dtype='<f8',shape=shape,sha256=hashlib.sha256(payload).hexdigest(),data_base64=base64.b64encode(payload).decode()):raise ValueError('independent array bytes')
    for field,parent in [('density_g_cm3','density_parent'),('temperature_k','temperature_parent'),('hydrogen_fraction','hydrogen_parent'),('helium_fraction','helium_parent')]:
        h,v=arrays['trial'][field];shape=list(h['shape']);width=len(v)//128
        if shape[0]!=128:raise ValueError('half cells')
        mirrored=v+b''.join(v[i*width:(i+1)*width] for i in reversed(range(128)))
        array_fact(r['material'][parent],mirrored,[256,*shape[1:]])
        if arrays['old'][field][1]!=v+v:raise ValueError('old two phases')
    if struct.unpack('<128d',arrays['old']['cell_mass_g_cm2'][1])!=(1e-10,)*128:raise ValueError('fixture mass')
    if struct.unpack('<128d',arrays['trial']['density_g_cm3'][1])!=(1e-10,)*128:raise ValueError('fixture density')
    if struct.unpack('<2d',arrays['old']['step_duration_s'][1])!=(1.,1.):raise ValueError('fixture duration')
    if struct.unpack('<98d',arrays['master']['active_edge_hz'][1])!=tuple(float(i) for i in range(1,99)):raise ValueError('master edges')
    if r['leggauss_internals_metered'] is not False:raise ValueError('leggauss scope')
    if type(r['frequency_grids']) is not list or len(r['frequency_grids'])!=2:raise ValueError('frequency grid count')
    for grid in r['frequency_grids']:
        if set(grid)!={'active_lab_edge_hz','comoving_collision_edge_hz','outer_lab_edge_hz'}:raise ValueError('frequency grid fields')
        for value in grid.values():array_fact(value,arrays['master']['active_edge_hz'][1],[98])
    indices=r['frequency_indices']
    if indices!=[[0,97,0,97,0,97]] or any(type(n) is not int for row in indices for n in row):raise ValueError('frequency indices')
    f=json.loads(raw['fixed']);t=json.loads(raw['template'])
    if f['sources']['phase7b7i_template_protocol']!=r['claims']['template']:raise ValueError('template claim')
    for role,key in [('old','phase7b4r_material'),('master','phase7b5p_master_input')]:
        if t['sources'][key]!=r['claims'][role]:raise ValueError('physical source claim')
    f['sources']['current_material_state']=r['claims']['trial']
    t['sources']['initial_radiation_state']['path']='synthetic/never-opened.dat'
    t['sources']['second_material_iterate']=r['claims']['trial']
    if r['fixed']!=f or r['template']!=t:raise ValueError('configuration composition')
    if r['warm_seed']!=dict(path='synthetic/never-opened.dat',size_bytes=97*32*4096*8,sha256='0'*64):raise ValueError('warm declaration')
    c=r['context']
    if type(c['phase']) is not int or (c['phase'],c['following'],c['duration_s'],c['shape'])!=(0,1,1.,[97,32,4096]):raise ValueError('geometry')
    if any(type(n) is not int for block in c['blocks'] for n in block):raise ValueError('integer ownership')
    if c['blocks']!=[[i,min(i+128,97)] for i in range(0,97,128)]:raise ValueError('ownership')
    array_fact(c['edge_cm'],struct.pack('<514d',*(list(range(-128,129))*2)),[2,257])
    array_fact(c['beta'],b'\0'*(4096*8),[4096])
    for key in ('mu','weight'):
        payload=base64.b64decode(c[key]['data_base64'],validate=True)
        array_fact(c[key],payload,[32])
    mu=struct.unpack('<32d',base64.b64decode(c['mu']['data_base64']));w=struct.unpack('<32d',base64.b64decode(c['weight']['data_base64']))
    if any(not math.isfinite(x) for x in mu+w) or any(x<=0 for x in w):raise ValueError('quadrature domain')
    for order in range(4):
        if abs(math.fsum(a*b**order for a,b in zip(w,mu))-(0 if order%2 else 2/(order+1)))>2e-14:raise ValueError('fixed angular moment')
    required={'operations.x20_86304_preparation_frequency_configuration','operations.x20_86304_preparation_frequency_context','operations.x20_86304_preparation_quadrature','operations.x20_86304_preparation_stencil','operations.x20_86304_preparation_motion','operations.x20_86304_preparation_column','operations.x20_86304_preparation_headers','operations.x20_86304_preparation_inflate','operations.common_step21_directions','scripts.phase7b5x_full_depth_block_probe'}
    seen=r['executed_project_origins']
    if not required<=seen.keys():raise ValueError('original modules')
    for name,fact in seen.items():
        row=pack['modules'][name];v=row['source'].encode()
        if len(v)!=row['size_bytes'] or hashlib.sha256(v).hexdigest()!=row['sha256'] or fact!=dict(file=root+'/'+row['path'],spec_origin=root+'/'+row['path']):raise ValueError('memory origin')
    if sum(e['decompressed_payload_bytes'] for e in r['meter']['events'])!=decoded_bytes or r['authenticated_input_bytes']!=sum(map(len,raw.values())) or r['residual_view_bytes']!=4096:raise ValueError('meter')
    meter=r['meter']
    for key in ('header_ast_created','python_object_overhead_metered','all_scientific_temporaries_metered','whole_lifecycle_guard_verified','production_authorized'):
        if meter[key] is not False:raise ValueError('meter scope')
    if type(meter['header_payload_copy_bytes']) is not int or meter['header_payload_copy_bytes']!=0:raise ValueError('header copy')
    for label,size in meter['entries']:
        if type(label) is not str or type(size) is not int or size<0:raise ValueError('ledger entry')
    reserved=meter['explicit_payload_capacity_reserved_bytes']
    if type(reserved) is not int or reserved!=sum(n for _,n in meter['entries']) or not 0<reserved<512*1024**2:raise ValueError('reservation ledger')
    # Independent exact named capacities for this two-phase/97-group fixture.
    validation=[]
    for key,n in [('density_g_cm3',256),('temperature_k',256),('hydrogen_fraction',512),('helium_fraction',768),('cell_mass_g_cm2',128),('step_duration_s',2)]:
        validation.extend([['motion:'+key+':finite-mask',n],['motion:'+key+':lower-mask',n]])
        if key.endswith('_fraction'):validation.append(['motion:'+key+':upper-mask',n])
    validation.extend([['motion:edge-finite-mask',98],['motion:edge-positive-mask',98],['motion:edge-diff',776],['motion:edge-increasing-mask',97]])
    expected_motion=validation+validation+[['motion:'+k,n] for k,n in [
        ('following-edge',4112),('edge-displacement',4112),('duration-light-distance',16),
        ('face-beta',4112),('face-beta-absolute',4112),('argmax-contiguous-capacity',4112),
        ('adjacent-face-sum',2048),('parent-beta',2048),('subcell-beta',32768),
        ('face-beta:finite-mask',514),('parent-beta:finite-mask',256),('beta:finite-mask',4096),
        ('active-edge-copy',784)]]
    if [row for row in meter['entries'] if row[0].startswith('motion:')]!=expected_motion:raise ValueError('motion expression ledger')
    expected_column=[]
    for key,n in [('cell_mass_g_cm2',128),('density_g_cm3',256),('temperature_k',256),('hydrogen_fraction',512),('helium_fraction',768)]:
        expected_column.extend([['column:'+key+':finite-mask',n],['column:'+key+':lower-mask',n]])
        if key.endswith('fraction'):expected_column.append(['column:'+key+':upper-mask',n])
    expected_column += [['column:'+k,n] for k,n in [('half-width',2048),('full-width',4096),('half-thickness',16),('left-negative',16),('right-negative',16),('cumulative-width',4096),('shifted-edge',4096),('edge',4112),('midplane-absolute',16),('density_g_cm3:mirror',4096),('temperature_k:mirror',4096),('hydrogen_fraction:mirror',8192),('helium_fraction:mirror',12288),('edge_cm:output-finite-mask',514),('density_g_cm3:output-finite-mask',512),('temperature_k:output-finite-mask',512),('hydrogen_fraction:output-finite-mask',1024),('helium_fraction:output-finite-mask',1536)]]
    if [row for row in meter['entries'] if row[0].startswith('column:')]!=expected_column:raise ValueError('column expression ledger')
    # Independent shape-derived tables for this zero-beta 97-group case.
    quadrature=[['quadrature:leggauss-return-capacity',256]]
    quadrature += [['quadrature:'+k,128] for k in ('left-product','left-add','left-subtract','left-mu','left-weight','right-product','right-add','right-add-one','right-mu','right-weight')]
    quadrature += [['quadrature:'+k,256] for k in ('mu-concatenate','weight-concatenate')]
    if [x for x in meter['entries'] if x[0].startswith('quadrature:')]!=quadrature:raise ValueError('quadrature expression ledger')
    freq=[('active:finite',98),('active:diff',776),('active:increasing',97),('active:positive',98),('collision-copy',784),('outer-copy',784),('collision:diff',776),('collision:increasing',97),('outer:diff',776),('outer:increasing',97),('collision-output:finite',98),('outer-output:finite',98),('outer-return',784),('collision-return',784),('active-return',784)]
    freq += [('mu:finite',32),('weight:finite',32),('mu-low',32),('mu-high',32),('weight-positive',32),('beta:finite',4096),('beta-abs',32768),('beta-domain',4096)]
    freq += [(k,32768) for k in ('beta-square','gamma-radicand','gamma-root','gamma')]
    freq += [(k,1048576) for k in ('doppler-product','doppler-difference','doppler','denominator-product','denominator','aberration-numerator','comoving-mu','doppler-square','comoving-weight')]
    freq += [(k,32768) for k in ('weight-sum','measure','measure-difference','measure-error')]
    freq += [('doppler:finite',131072),('comoving-mu:finite',131072),('comoving-weight:finite',131072),('measure-error:finite',4096),('doppler-positive',131072),('comoving-mu-abs',1048576),('comoving-mu-domain',131072)]
    freq += [(k,1048576) for k in ('doppler-return','comoving-mu-return','comoving-weight-return')]+[('measure-error-return',32768)]
    freq += [(k,784) for k in ('block-outer','block-collision','block-active')]
    if [x for x in meter['entries'] if x[0].startswith('frequency:')]!=[['frequency:'+k,n] for k,n in freq]:raise ValueError('frequency expression ledger')
    for event in meter['events']:
        for key in ('calls','max_input_bytes','max_output_bytes'):
            if type(event[key]) is not int or not 0<event[key]:raise ValueError('decoder counters')
        if max(event['max_input_bytes'],event['max_output_bytes'])>65536:raise ValueError('decoder chunk ceiling')
    if type(outcome['elapsed_s']) not in (int,float) or type(r['resources']['elapsed_s']) not in (int,float) or type(r['resources']['peak_rss_bytes']) is not int:raise ValueError('resource types')
    if not 0<r['resources']['elapsed_s']<120 or not 0<r['resources']['peak_rss_bytes']<1024**3:raise ValueError('child resources')
    return dict(synthetic_frequency_configuration_verified=True,original_modules=len(seen),blocks=1,
        source_bytes=sum(map(len,raw.values())),meter=r['meter'],resources=r['resources'],outer_seconds=outcome['elapsed_s'],
        whole_lifecycle_guard_verified=False,complete_native_context_verified=False,production_authorized=False)
