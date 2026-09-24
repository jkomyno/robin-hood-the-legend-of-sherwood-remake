"""Bounded, opt-in RGB extrapolation within one physical receiver face."""
import numpy as np
from scipy.ndimage import distance_transform_edt, label


def validate_policy(policy, receiver_names=None):
    keys={'version','receiver_objects','max_distance_texels','max_distance_world','bottom_band_world',
          'max_face_fraction','max_total_texels','max_abs_normal_z'}
    if not isinstance(policy,dict) or not keys<=set(policy) or set(policy)-keys-{'face_bottom_bands'} or policy['version']!=1:
        raise ValueError('Invalid inferred-gap repair policy')
    names=policy['receiver_objects']
    if not isinstance(names,list) or not names or any(not isinstance(n,str) or not n for n in names) or len(set(names))!=len(names):
        raise ValueError('Repair requires explicit unique receiver names')
    if receiver_names is not None and not set(names)<=set(receiver_names):
        raise ValueError('Gap repair names a foreign or excluded receiver')
    limits={'max_distance_texels':16,'max_distance_world':8,'bottom_band_world':4,
            'max_face_fraction':.05,'max_total_texels':10000,'max_abs_normal_z':.05}
    for key,limit in limits.items():
        value=policy[key]
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not np.isfinite(value) or not 0<value<=limit:
            raise ValueError('Unsafe inferred-gap repair limit: '+key)
    if type(policy['max_total_texels']) is not int:raise ValueError('Repair count cap must be an integer')
    overrides=policy.get('face_bottom_bands',{})
    if not isinstance(overrides,dict) or not set(overrides)<=set(names):
        raise ValueError('Face band override names a foreign receiver')
    for faces in overrides.values():
        if not isinstance(faces,dict) or not faces:
            raise ValueError('Face band override requires explicit face indices')
        for face,height in faces.items():
            if (not isinstance(face,str) or not face.isdigit() or str(int(face))!=face or
                isinstance(height,bool) or not isinstance(height,(int,float)) or not np.isfinite(height) or
                not policy['bottom_band_world']<=height<=12):
                raise ValueError('Invalid bounded per-face basal extent')
    return policy


def repair_face(colors, protected, generated, positions, policy, object_min_z, bottom_band_override=None):
    """All samples belong to one face, including its clamped atlas gutter.

    No accepted source or existing generated color can become a destination;
    donors come only from the original generated mask, never repaired pixels.
    """
    validate_policy(policy)
    shape=colors.shape[:2]
    if (colors.shape!=(*shape,4) or positions.shape!=(*shape,3) or
        protected.shape!=shape or generated.shape!=shape or protected.dtype!=bool or generated.dtype!=bool or
        np.any(protected & generated) or not np.isfinite(colors).all() or not np.isfinite(positions).all() or
        not np.isfinite(object_min_z)):
        raise ValueError('Invalid per-face repair buffers')
    if bottom_band_override is not None and (not np.isfinite(bottom_band_override) or
            not policy['bottom_band_world']<=bottom_band_override<=12):
        raise ValueError('Invalid per-face basal extent')
    result=colors.copy();selected=np.zeros(shape,dtype=bool)
    stats={'repaired_texels':0,'maximum_distance_texels':0.,'maximum_distance_world':0.}
    if not generated.any():return result,selected,stats
    distance,nearest=distance_transform_edt(~generated,return_indices=True)
    donor_positions=positions[tuple(nearest)]
    world_distance=np.linalg.norm(positions-donor_positions,axis=-1)
    z=positions[...,2]
    band=policy['bottom_band_world'] if bottom_band_override is None else bottom_band_override
    connected=np.ones(shape,dtype=bool)
    if bottom_band_override is not None:
        components,_=label(~protected & ~generated)
        seeds=np.unique(components[(z>=object_min_z-1e-6)&(z<=object_min_z+policy['bottom_band_world'])])
        connected=np.isin(components,seeds[seeds!=0])
    selected=(connected & ~protected & ~generated & (distance<=policy['max_distance_texels']) &
              (world_distance<=policy['max_distance_world']) & (z>=object_min_z-1e-6) &
              (z<=object_min_z+band))
    count=int(selected.sum())
    if count>policy['max_total_texels'] or count>colors.shape[0]*colors.shape[1]*policy['max_face_fraction']:
        raise ValueError('Inferred-gap repair exceeds its narrow per-face/count budget')
    donors=colors[tuple(nearest)]
    result[selected,:3]=donors[selected,:3]
    if not np.array_equal(result[~selected],colors[~selected]) or not np.array_equal(result[...,3],colors[...,3]):
        raise ValueError('Gap repair altered protected RGB or physical alpha')
    stats.update(face_samples=int(colors.shape[0]*colors.shape[1]),bottom_band_world=float(band),connected_basal_component=bottom_band_override is not None)
    if count:
        stats.update(repaired_texels=count,maximum_distance_texels=float(distance[selected].max()),
                     maximum_distance_world=float(world_distance[selected].max()))
    return result,selected,stats
