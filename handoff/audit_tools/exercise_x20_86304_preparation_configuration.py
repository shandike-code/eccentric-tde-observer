"""Synthetic configuration fixture; never accepts scientific input paths."""
import hashlib
import io
import json


def fixture(groups=129):
    import numpy as np
    from operations.common_step21_directions import GroundStateLogSimplexCodec
    codec = GroundStateLogSimplexCodec(128)
    encoded = np.tile(np.array([30., -.5, -.25, .125]), 128)
    decoded = codec.decode(encoded)
    base = {k:np.array(getattr(decoded,k),copy=True) for k in (
        'temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    residual = np.zeros(512)
    base.update(density_g_cm3=np.full(128,1e-10),phase_index=np.array(0),
        step_duration_s=np.array(1.),relaxation=np.array(0.),encoded_state=encoded,
        base_encoded_state=encoded.copy(),base_residual=residual.copy(),finite_direction=residual.copy())
    old={k:np.stack((base[k],base[k])) for k in (
        'density_g_cm3','temperature_k','hydrogen_fraction','helium_fraction')}
    old.update(cell_mass_g_cm2=np.full(128,1e-10),step_duration_s=np.ones(2))
    master=dict(active_edge_hz=np.arange(1.,groups+2.),maximum_beta=np.array(0.))
    blobs={};claims={}
    def add(role,raw,suffix):
        blobs[role]=raw
        claims[role]=dict(path='synthetic/'+role+suffix,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    for role,arrays in [('trial',base),('base',base),('old',old),('master',master)]:
        stream=io.BytesIO();np.savez_compressed(stream,**arrays);add(role,stream.getvalue(),'.npz')
    stream=io.BytesIO();np.save(stream,residual,allow_pickle=False);add('residual',stream.getvalue(),'.npy')
    cfg=dict(physical_frequency_groups=groups,angular_direction_count=32,
             radiation_depth_cell_count=4096,phase_index=0)
    template=dict(configuration=cfg,sources=dict(phase7b4r_material=claims['old'],
        phase7b5p_master_input=claims['master'],initial_radiation_state={'path':'unused.dat'},
        second_material_iterate={'path':'unused.npz'}))
    add('template',json.dumps(template).encode(),'.json')
    fixed=dict(configuration=cfg,sources=dict(phase7b7i_template_protocol=claims['template'],
                                               current_material_state={'path':'unused.npz'}))
    add('fixed',json.dumps(fixed).encode(),'.json')
    warm=dict(path='synthetic/never-opened.dat',size_bytes=groups*32*4096*8,sha256='0'*64)
    expected=dict(phase=0,duration_s=1.,shape=[groups,32,4096])
    return blobs,claims,warm,expected


def facts(result, blobs, claims):
    import base64
    import numpy as np
    c=result['context']
    def array(a):
        raw=a.tobytes()
        return dict(dtype=a.dtype.str,shape=list(a.shape),sha256=hashlib.sha256(raw).hexdigest(),
                    data_base64=base64.b64encode(raw).decode())
    return dict(synthetic=True,production_authorized=False,whole_lifecycle_guard_verified=False,
        complete_native_context_verified=False,
        fixed=result['fixed'],template=result['template'],warm_seed=result['warm_seed'],
        claims=claims,source_bytes={k:base64.b64encode(v).decode() for k,v in blobs.items()},
        material={k:array(v) for k,v in result['material'].items()},
        context=dict(phase=c['phase'],following=c['following'],duration_s=c['duration_s'],
            shape=[c['stencil'].physical_group_count,len(c['mu']),len(c['beta'])],
            blocks=[[b.core_group_start,b.core_group_stop] for b in c['blocks']],
            edge_cm=array(c['full']['edge_cm']),beta=array(c['beta']),mu=array(c['mu']),weight=array(c['weight'])),
        meter=result['meter'],authenticated_input_bytes=result['authenticated_input_bytes'],
        residual_view_bytes=result['residual_view_bytes'])
