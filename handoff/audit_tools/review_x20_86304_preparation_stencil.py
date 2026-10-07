"""Independent scalar/struct review; imports neither NumPy nor the component."""
import base64
import bisect
import hashlib
import math
import struct


def review(r):
    if r['schema']!='frequency-preparation-synthetic-v1' or r['synthetic'] is not True:raise ValueError('fixture')
    for key in ('production_authorized','all_scientific_temporaries_metered','whole_lifecycle_guard_verified','configuration_integrated'):
        if r[key] is not False:raise ValueError('qualification')
    if r['platform'] not in ('darwin','linux') or type(r['elapsed_s']) not in (float,int) or not 0<r['elapsed_s']<30:raise ValueError('environment')
    checked=0
    def array(f,values,shape,readonly=True,approx=False):
        nonlocal checked
        if f['dtype']!='<f8' or type(f['shape']) is not list or any(type(n) is not int for n in f['shape']) or f['shape']!=shape or f['readonly'] is not readonly:raise ValueError('array layout')
        raw=base64.b64decode(f['bytes'],validate=True)
        if len(raw)!=8*math.prod(shape) or hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('array integrity')
        if approx:
            actual=struct.unpack('<'+'d'*len(values),raw)
            if any(not math.isfinite(a) or abs(a-b)>2e-14 for a,b in zip(actual,values)):raise ValueError('scalar oracle')
        elif raw!=struct.pack('<'+'d'*len(values),*values):raise ValueError('scalar bytes')
        checked+=len(values)
    edge=[2.**i for i in range(10)];mu=[-.75,-.25,.25,.75];w=[.5]*4;beta=[-.125,0.,.125]
    if len(r['input'])!=4:raise ValueError('input count')
    for f,v in zip(r['input'],(edge,mu,w,beta)):array(f,v,[len(v)],False)
    margin=128*2.**-52;gamma=1/math.sqrt(1-.25**2);lo=gamma*(1-.25);hi=gamma*(1+.25)
    cl=lo*edge[0]*(1-margin);ch=hi*edge[-1]*(1+margin)
    collision=[cl]+edge+[ch];outer=[cl/hi*(1-margin),cl]+edge+[ch,ch/lo*(1+margin)]
    def grid(g,active,c,o,start):
        if set(g)!={'outer_lab_edge_hz','comoving_collision_edge_hz','active_lab_edge_hz','active_outer_group_start','active_outer_group_stop','physical_group_count','comoving_collision_group_count','outer_lab_group_count','groups_per_decade','maximum_velocity_beta'}:raise ValueError('grid keys')
        for key,val in [('active_outer_group_start',start),('active_outer_group_stop',start+len(active)-1),('physical_group_count',len(active)-1),('comoving_collision_group_count',len(c)-1),('outer_lab_group_count',len(o)-1)]:
            if type(g[key]) is not int or g[key]!=val:raise ValueError('grid count')
        if g['groups_per_decade'] is not None or g['maximum_velocity_beta']!=.25:raise ValueError('grid metadata')
        for key,v in [('active_lab_edge_hz',active),('comoving_collision_edge_hz',c),('outer_lab_edge_hz',o)]:array(g[key],v,[len(v)])
    grid(r['stencil'],edge,collision,outer,2)
    doppler=[];aberration=[];weights=[]
    for m,weight in zip(mu,w):
        for b in beta:
            g=1/math.sqrt(1-b**2);d=g*(1-m*b);doppler.append(d);aberration.append((m-b)/(1-m*b));weights.append(weight/d**2)
    error=[abs(.5*sum(weights[i*3+j] for i in range(4))-1) for j in range(3)]
    for key,v,shape in [('doppler_lab_to_comoving',doppler,[4,3]),('comoving_direction_cosine',aberration,[4,3]),('comoving_angular_weight',weights,[4,3]),('angular_measure_relative_error',error,[3])]:array(r['rays'][key],v,shape,approx=True)
    if len(r['blocks'])!=3:raise ValueError('block count')
    expected_blocks=[]
    for block,start in zip(r['blocks'],(0,4,8)):
        stop=min(start+4,9);cs=bisect.bisect_right(collision,edge[start]*min(doppler))-1;ce=bisect.bisect_left(collision,edge[stop]*max(doppler))
        os=bisect.bisect_right(outer,collision[cs]/max(doppler))-1;oe=bisect.bisect_left(outer,collision[ce]/min(doppler))
        for key,val in [('core_group_start',start),('core_group_stop',stop),('collision_group_start',cs),('collision_group_stop',ce),('outer_group_start',os),('outer_group_stop',oe)]:
            if type(block[key]) is not int or block[key]!=val:raise ValueError('block ownership')
        grid(block['local_stencil'],edge[start:stop+1],collision[cs:ce+1],outer[os:oe+1],2+start-os)
        expected_blocks.extend([('block-outer',(oe-os+1)*8),('block-collision',(ce-cs+1)*8),('block-active',(stop-start+1)*8)])
    # Independent named expression capacities for fixed 10 edges/4 rays/3 cells.
    stencil=[('active:finite',10),('active:diff',72),('active:increasing',9),('active:positive',10),('collision-active-copy',80),('collision-list-coercion-capacity',16),('collision-concatenate',96),('outer-active-copy',80),('outer-list-coercion-capacity',32),('outer-concatenate',112),('collision:diff',88),('collision:increasing',11),('outer:diff',104),('outer:increasing',13),('collision-output:finite',12),('outer-output:finite',14),('outer-return',112),('collision-return',96),('active-return',80)]
    ray=[('mu:finite',4),('weight:finite',4),('mu-low',4),('mu-high',4),('weight-positive',4),('beta:finite',3),('beta-abs',24),('beta-domain',3)]
    ray += [(k,24) for k in ('beta-square','gamma-radicand','gamma-root','gamma')]
    ray += [(k,96) for k in ('doppler-product','doppler-difference','doppler','denominator-product','denominator','aberration-numerator','comoving-mu','doppler-square','comoving-weight')]
    ray += [(k,24) for k in ('weight-sum','measure','measure-difference','measure-error')]
    ray += [('doppler:finite',12),('comoving-mu:finite',12),('comoving-weight:finite',12),('measure-error:finite',3),('doppler-positive',12),('comoving-mu-abs',96),('comoving-mu-domain',12),('doppler-return',96),('comoving-mu-return',96),('comoving-weight-return',96),('measure-error-return',24)]
    expected=[['frequency:'+k,n] for k,n in stencil+ray+ray+expected_blocks]
    entries=r['entries']
    if any(type(k) is not str or type(n) is not int for k,n in entries) or entries!=expected:raise ValueError('expression ledger')
    if type(r['explicit_payload_capacity_reserved_bytes']) is not int or r['explicit_payload_capacity_reserved_bytes']!=sum(n for _,n in expected):raise ValueError('capacity sum')
    # Per ray one quadrature check; per plan extrema/2 queries per block/final.
    if type(r['checks']) is not int or r['checks']!=len(expected)+2+1+2*3+1:raise ValueError('checkpoints')
    return dict(synthetic_frequency_component_verified=True,scalar_values_checked=checked,ledger_entries=len(entries),capacity_bytes=sum(n for _,n in expected),checks=r['checks'],production_authorized=False,configuration_integrated=False)
