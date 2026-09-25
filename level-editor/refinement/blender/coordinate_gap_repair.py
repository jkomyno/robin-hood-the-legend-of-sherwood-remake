"""Exact, measured physical texel band repairs; never infer an entire hidden face."""
import hashlib
import json
import numpy as np
from scipy.ndimage import distance_transform_edt


def validate_band(rule):
    keys={'z_min','z_max','max_physical_texels','max_physical_area_world2','max_distance_texels','max_distance_world','atlas_pixels','atlas_pixels_sha256','reference_model_sha256'}
    if not isinstance(rule,dict) or set(rule)!=keys:raise ValueError('Coordinate repair requires exact measured bounds')
    for key in ('z_min','z_max'):
        if isinstance(rule[key],bool) or not isinstance(rule[key],(int,float)) or not np.isfinite(rule[key]):raise ValueError('Invalid coordinate band')
    if not 0<rule['z_max']-rule['z_min']<=4:raise ValueError('Coordinate band must be narrow')
    for key,cap in [('max_physical_texels',64),('max_physical_area_world2',16),('max_distance_texels',4),('max_distance_world',2)]:
        v=rule[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or not 0<v<=cap:raise ValueError('Unsafe coordinate repair cap')
    if type(rule['max_physical_texels']) is not int:raise ValueError('Integer texel cap required')
    points=rule['atlas_pixels']
    if not isinstance(points,list) or not points or len(points)>rule['max_physical_texels'] or any(not isinstance(p,list) or len(p)!=2 or any(type(v) is not int or v<0 for v in p) for p in points) or len({tuple(p) for p in points})!=len(points):raise ValueError('Unique exact atlas pixels required')
    if hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()!=rule['atlas_pixels_sha256']:raise ValueError('Atlas pixel list drift')
    if not isinstance(rule['reference_model_sha256'],str) or len(rule['reference_model_sha256'])!=64 or any(c not in '0123456789abcdef' for c in rule['reference_model_sha256']):raise ValueError('Reference model hash required')
    return rule


def repair_coordinate_band(colors,protected,generated,positions,physical,atlas_origin,texel_area,rule):
    validate_band(rule)
    shape=colors.shape[:2]
    if colors.shape!=(*shape,4) or positions.shape!=(*shape,3) or any(a.shape!=shape or a.dtype!=bool for a in (protected,generated,physical)) or np.any(protected&generated) or not physical.any() or not np.isfinite(texel_area) or texel_area<=0:raise ValueError('Invalid coordinate repair domain')
    selected=np.zeros(shape,bool)
    for x,y in rule['atlas_pixels']:
        x-=atlas_origin[0];y-=atlas_origin[1]
        if not 0<=x<shape[1] or not 0<=y<shape[0]:raise ValueError('Measured pixel outside receiver island')
        selected[y,x]=True
    if np.any(selected & (~physical|protected|generated)):raise ValueError('Measured destination is not unknown physical face')
    z=positions[...,2]
    if np.any(selected & ((z<rule['z_min'])|(z>rule['z_max']))):raise ValueError('Measured destination outside explicit coordinate band')
    donors=generated&physical
    if not donors.any():raise ValueError('No original generated physical donors')
    distance,nearest=distance_transform_edt(~donors,return_indices=True)
    world_distance=np.linalg.norm(positions-positions[tuple(nearest)],axis=-1)
    if np.any(selected & ((distance>rule['max_distance_texels'])|(world_distance>rule['max_distance_world']))):raise ValueError('Coordinate donor beyond measured distance')
    count=int(selected.sum());area=count*texel_area
    if count>rule['max_physical_texels'] or area>rule['max_physical_area_world2'] or count>physical.sum()*.05:raise ValueError('Coordinate repair exceeds physical budget')
    result=colors.copy();result[selected,:3]=colors[tuple(nearest)][selected,:3]
    if not np.array_equal(result[~selected],colors[~selected]) or not np.array_equal(result[...,3],colors[...,3]):raise ValueError('Coordinate repair changed outside RGBA or alpha')
    stats={'coordinate_band_repaired_texels':count,'coordinate_band_area_world2':float(area),'coordinate_band_world':[rule['z_min'],rule['z_max']],'coordinate_band_atlas_pixels_sha256':rule['atlas_pixels_sha256'],'coordinate_band_reference_model_sha256':rule['reference_model_sha256'],'coordinate_band_maximum_distance_texels':float(distance[selected].max()),'coordinate_band_maximum_distance_world':float(world_distance[selected].max())}
    return result,selected,stats
