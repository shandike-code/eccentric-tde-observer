"""Standard-library oracle for the fixed synthetic context. No native imports."""
import ast
import base64
import hashlib
import io
import json
import math
import struct
import zipfile


def arrays(raw):
    result={}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())>12 or sum(i.file_size for i in z.infolist())>256*1024:
            raise ValueError('tiny fixture bound')
        for name in z.namelist():
            b=z.read(name)
            if b[:8]!=b'\x93NUMPY\x01\x00':raise ValueError('NPY version')
            end=10+int.from_bytes(b[8:10],'little');h=ast.literal_eval(b[10:end].decode())
            if h['descr']!='<f8' or h['fortran_order'] is not False:raise ValueError('dtype/order')
            if len(b[end:])!=math.prod(h['shape'])*8:raise ValueError('shape')
            result[name[:-4]]=(list(h['shape']),b[end:])
    return result


def fact(row,shape,raw):
    expected=dict(dtype='<f8',shape=shape,sha256=hashlib.sha256(raw).hexdigest(),data_base64=base64.b64encode(raw).decode())
    if row!=expected:raise ValueError('array does not match independent bytes')


def review(run,pack):
    if type(run['returncode']) is not int or run['returncode']!=0 or run['stderr'] or not 0<run['elapsed_s']<25:
        raise ValueError('child failed')
    r=json.loads(run['stdout'])
    for key in ('production_ready','whole_lifecycle_guard_verified','complete_native_context_verified'):
        if r[key] is not False:raise ValueError('qualification')
    for key in ('synthetic','startup_isolated_no_site','environment_preload_project_free'):
        if r[key] is not True:raise ValueError('scope')
    old=arrays(base64.b64decode(r['source_npz']['old'],validate=True)); master=arrays(base64.b64decode(r['source_npz']['master'],validate=True))
    # Independent fixture identity, not just output/source mutual consistency.
    if set(old)!={'density_g_cm3','temperature_k','hydrogen_fraction','helium_fraction','cell_mass_g_cm2','step_duration_s'} or set(master)!={'active_edge_hz','maximum_beta'}:raise ValueError('sources')
    def doubles(v):return struct.pack('<'+'d'*len(v),*v)
    expected={'density_g_cm3':([2,128],doubles([1.]*256)),
      'temperature_k':([2,128],doubles([10000.]*256)),
      'hydrogen_fraction':([2,128,2],doubles([.75,.25]*256)),
      'helium_fraction':([2,128,3],doubles([.5,.25,.25]*256)),
      'cell_mass_g_cm2':([128],doubles([1.]*128)),
      'step_duration_s':([2],doubles([1.,1.]))}
    if old!=expected or master!={'active_edge_hz':([9633],doubles([float(i) for i in range(1,9634)])),'maximum_beta':([],doubles([0.]))}:raise ValueError('fixture identity')
    c=r['context']
    for key,value in [('phase',0),('following',1),('selected_block_index',0)]:
        if type(c[key]) is not int or c[key]!=value:raise ValueError(key)
    if type(c['duration_s']) is not float or c['duration_s']!=1.:raise ValueError('duration')
    fact(c['full']['edge_cm'],[2,257],doubles([float(i) for i in range(-128,129)]*2))
    for k in ('density_g_cm3','temperature_k','hydrogen_fraction','helium_fraction'):
        shape,raw=old[k];width=math.prod(shape[2:])*8;half=128*width
        full=b''.join(raw[p*half:(p+1)*half]+b''.join(raw[p*half+i*width:p*half+(i+1)*width] for i in range(127,-1,-1)) for p in range(2))
        fact(c['full'][k],[2,256,*shape[2:]],full)
    for key,shape in [('face_beta',[2,257]),('parent_beta',[256]),('beta',[4096])]:
        # Subtraction of identical positive/negative edges gives positive zeros.
        fact(c['arrays'][key],shape,bytes(math.prod(shape)*8))
    mu=struct.unpack('<32d',base64.b64decode(c['arrays']['mu']['data_base64']))
    w=struct.unpack('<32d',base64.b64decode(c['arrays']['weight']['data_base64']))
    for key,values in [('mu',mu),('weight',w)]:fact(c['arrays'][key],[32],doubles(values))
    if not all(-1<x<1 for x in mu) or not all(x>0 for x in w) or any(mu[i]>=mu[i+1] for i in range(31)):raise ValueError('quadrature domain')
    for n,exact in [(0,2.),(1,0.),(2,2/3),(3,0.)]:
        if abs(math.fsum(a*x**n for a,x in zip(w,mu))-exact)>2e-14:raise ValueError('quadrature moments')
    edge=master['active_edge_hz'][1]
    def stencil(s,start,stop):
        for key in ('outer_lab_edge_hz','comoving_collision_edge_hz','active_lab_edge_hz'):
            fact(s[key],[stop-start+1],edge[start*8:(stop+1)*8])
        for key,value in [('active_outer_group_start',0),('active_outer_group_stop',stop-start),('physical_group_count',stop-start),('comoving_collision_group_count',stop-start),('outer_lab_group_count',stop-start)]:
            if type(s[key]) is not int or s[key]!=value:raise ValueError('stencil ownership')
        if s['groups_per_decade'] is not None or type(s['maximum_velocity_beta']) is not float or s['maximum_velocity_beta']!=0.:raise ValueError('stencil metadata')
    stencil(c['stencil'],0,9632)
    if len(c['blocks'])!=76:raise ValueError('block count')
    for i,b in enumerate(c['blocks']):
        start=i*128;stop=min(start+128,9632)
        for prefix in ('core','collision','outer'):
            if type(b[prefix+'_group_start']) is not int or b[prefix+'_group_start']!=start or type(b[prefix+'_group_stop']) is not int or b[prefix+'_group_stop']!=stop:raise ValueError('block range')
        stencil(b['local_stencil'],start,stop)
    identified=8*32*(5*128*4096+2*128*4096+128*4096+128*(4096+1))
    if type(c['identified_live_bytes']) is not int or c['identified_live_bytes']!=identified:raise ValueError('identified expression')
    origins=r['executed_project_origins'];required={'operations.x20_86304_preparation_context','scripts.phase7b5x_full_depth_block_probe','eccentric_tde_observer.mixed_frame_streaming','eccentric_tde_observer.mixed_frame_ale'}
    if not required<=set(origins):raise ValueError('missing original execution')
    for n,o in origins.items():
        row=pack['modules'][n];src=row['source'].encode()
        if len(src)!=row['size_bytes'] or hashlib.sha256(src).hexdigest()!=row['sha256']:raise ValueError('source SHA')
        expected_origin=pack['root']+'/'+row['path']
        if o!={'file':expected_origin,'spec_origin':expected_origin}:raise ValueError('origin')
    if r['resources']['elapsed_s']>=120 or r['resources']['peak_rss_bytes']>=1024**3:raise ValueError('resource')
    return dict(synthetic_context_reviewed=True,blocks=76,groups=9632,project_modules=len(origins),production_ready=False,whole_lifecycle_guard_verified=False)
