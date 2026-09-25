"""Bounded, opt-in RGB extrapolation within one physical receiver face."""
import numpy as np
from scipy.ndimage import distance_transform_edt, label, binary_dilation


def validate_policy(policy, receiver_names=None, receiver_face_counts=None):
    keys={'version','receiver_objects','max_distance_texels','max_distance_world','bottom_band_world',
          'max_face_fraction','max_total_texels','max_abs_normal_z'}
    if not isinstance(policy,dict) or not keys<=set(policy) or set(policy)-keys-{'face_bottom_bands','receiver_faces','physical_gutter_texels','face_distance_limits','face_component_limits','physical_donors_only'} or policy['version']!=1:
        raise ValueError('Invalid inferred-gap repair policy')
    gutter=policy.get('physical_gutter_texels')
    if gutter is not None and (type(gutter) is not int or not 0<=gutter<=2):
        raise ValueError('Physical repair gutter must be an explicit 0..2 texels')
    if 'physical_donors_only' in policy and (policy['physical_donors_only'] is not True or 'physical_gutter_texels' not in policy):
        raise ValueError('Physical-only donors require explicit physical domain and true opt-in')
    names=policy['receiver_objects']
    if not isinstance(names,list) or not names or any(not isinstance(n,str) or not n for n in names) or len(set(names))!=len(names):
        raise ValueError('Repair requires explicit unique receiver names')
    if receiver_names is not None and not set(names)<=set(receiver_names):
        raise ValueError('Gap repair names a foreign or excluded receiver')
    selected=policy.get('receiver_faces')
    if selected is not None:
        if not isinstance(selected,dict) or set(selected)!=set(names):
            raise ValueError('Explicit face scope must cover exactly the named receivers')
        for name,faces in selected.items():
            if (not isinstance(faces,list) or not faces or any(type(i) is not int or i<0 for i in faces)
                    or len(set(faces))!=len(faces)):
                raise ValueError('Explicit face scope requires unique nonnegative indices')
            if receiver_face_counts is not None and (name not in receiver_face_counts or any(i>=receiver_face_counts[name] for i in faces)):
                raise ValueError('Explicit repair face is absent from saved receiver')
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
    distances=policy.get('face_distance_limits',{})
    if not isinstance(distances,dict) or not set(distances)<=set(names):
        raise ValueError('Distance override names a foreign receiver')
    for name,faces in distances.items():
        if not isinstance(faces,dict) or not faces:
            raise ValueError('Distance override requires explicit faces')
        for face,bounds in faces.items():
            if (not isinstance(face,str) or not face.isdigit() or str(int(face))!=face or
                selected is None or int(face) not in selected.get(name,[])):
                raise ValueError('Distance override requires a selected face')
            validate_distance_limits(bounds)
    rules=policy.get('face_component_limits',{})
    if not isinstance(rules,dict) or not set(rules)<=set(names):
        raise ValueError('Component limit names a foreign receiver')
    fields={'max_physical_texels','max_physical_area_world2','max_face_fraction','max_distance_texels','max_distance_world'}
    for name,faces in rules.items():
        if not isinstance(faces,dict) or not faces or 'physical_gutter_texels' not in policy:
            raise ValueError('Component limits require explicit faces and physical domain')
        for face,limits in faces.items():
            if (not isinstance(face,str) or not face.isdigit() or str(int(face))!=face or
                    not isinstance(limits,dict) or set(limits)!=fields):
                raise ValueError('Invalid per-face component limits')
            if selected is not None and int(face) not in selected[name]:
                raise ValueError('Component limit face is outside explicit scope')
            if receiver_face_counts is not None and int(face)>=receiver_face_counts[name]:
                raise ValueError('Component limit face is absent')
            caps={'max_physical_texels':150,'max_physical_area_world2':36,'max_face_fraction':.2,
                  'max_distance_texels':16,'max_distance_world':8}
            for key,cap in caps.items():
                value=limits[key]
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not 0<value<=cap:
                    raise ValueError('Unsafe component limit: '+key)
            if type(limits['max_physical_texels']) is not int:
                raise ValueError('Component physical texel cap must be integer')
            if limits['max_face_fraction']>.05 and (limits['max_distance_texels']>6.4 or limits['max_distance_world']>3.2):
                raise ValueError('Small-face exception requires tighter donor limits')
    return policy


def validate_distance_limits(bounds):
    limits={'max_distance_texels':20,'max_distance_world':10}
    if not isinstance(bounds,dict) or set(bounds)!=set(limits):
        raise ValueError('Invalid per-face distance limits')
    for key,cap in limits.items():
        value=bounds[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not 0<value<=cap:
            raise ValueError('Unsafe per-face distance limit')
    return bounds


def face_allowed(policy, object_name, face_index):
    selected=policy.get('receiver_faces')
    return selected is None or face_index in selected.get(object_name,[])


def repair_face(colors, protected, generated, positions, policy, object_min_z, bottom_band_override=None, physical_domain=None, distance_override=None, component_limits=None, physical_texel_area=None):
    """All samples belong to one face, including its clamped atlas gutter.

    No accepted source or existing generated color can become a destination;
    donors come only from the original generated mask, never repaired pixels.
    """
    validate_policy(policy)
    distances=policy if distance_override is None else validate_distance_limits(distance_override)
    shape=colors.shape[:2]
    if (colors.shape!=(*shape,4) or positions.shape!=(*shape,3) or
        protected.shape!=shape or generated.shape!=shape or protected.dtype!=bool or generated.dtype!=bool or
        np.any(protected & generated) or not np.isfinite(colors).all() or not np.isfinite(positions).all() or
        not np.isfinite(object_min_z)):
        raise ValueError('Invalid per-face repair buffers')
    if bottom_band_override is not None and (not np.isfinite(bottom_band_override) or
            not policy['bottom_band_world']<=bottom_band_override<=12):
        raise ValueError('Invalid per-face basal extent')
    eligible=np.ones(shape,dtype=bool)
    if 'physical_gutter_texels' in policy:
        if physical_domain is None or physical_domain.shape!=shape or physical_domain.dtype!=bool or not physical_domain.any():
            raise ValueError('Physical repair requires a nonempty boolean triangle domain')
        eligible=distance_transform_edt(~physical_domain)<=policy['physical_gutter_texels']
    elif physical_domain is not None:
        raise ValueError('Physical domain requires an explicit repair policy')
    result=colors.copy();selected=np.zeros(shape,dtype=bool)
    stats={'repaired_texels':0,'maximum_distance_texels':0.,'maximum_distance_world':0.}
    donor_mask=generated & physical_domain if policy.get('physical_donors_only') else generated
    stats['physical_donors_only']=bool(policy.get('physical_donors_only'))
    if not donor_mask.any():return result,selected,stats
    distance,nearest=distance_transform_edt(~donor_mask,return_indices=True)
    donor_positions=positions[tuple(nearest)]
    world_distance=np.linalg.norm(positions-donor_positions,axis=-1)
    z=positions[...,2]
    band=policy['bottom_band_world'] if bottom_band_override is None else bottom_band_override
    connected=np.ones(shape,dtype=bool)
    if bottom_band_override is not None:
        components,_=label(~protected & ~generated)
        seeds=np.unique(components[(z>=object_min_z-1e-6)&(z<=object_min_z+policy['bottom_band_world'])])
        connected=np.isin(components,seeds[seeds!=0])
    fraction_limit=policy['max_face_fraction']
    distance_limit=distances['max_distance_texels'];world_limit=distances['max_distance_world']
    if component_limits is not None:
        if physical_domain is None or physical_texel_area is None or not np.isfinite(physical_texel_area) or physical_texel_area<=0:
            raise ValueError('Component repair requires exact physical sampling area')
        validate_policy(dict(policy,face_component_limits={'own':{'0':component_limits}},receiver_objects=['own'],receiver_faces={'own':[0]},face_bottom_bands={},face_distance_limits={}))
        components,count_components=label(physical_domain & ~protected & ~generated)
        chosen=[];stats['components']=[]
        distance_limit=min(distance_limit,component_limits['max_distance_texels'])
        world_limit=min(world_limit,component_limits['max_distance_world'])
        fraction_limit=component_limits['max_face_fraction']
        for cid in range(1,count_components+1):
            component=components==cid;count_component=int(component.sum())
            edge=bool((binary_dilation(component)&~physical_domain).any())
            basal=bool((component & (z>=object_min_z-1e-6)&(z<=object_min_z+policy['bottom_band_world'])).any())
            valid=(edge and basal and count_component<=component_limits['max_physical_texels'] and
                   count_component*physical_texel_area<=component_limits['max_physical_area_world2'] and
                   count_component<=physical_domain.sum()*fraction_limit and
                   np.all(distance[component]<=distance_limit) and np.all(world_distance[component]<=world_limit) and
                   np.all(z[component]>=object_min_z-1e-6) and np.all(z[component]<=object_min_z+band))
            stats['components'].append(dict(component=cid,physical_texels=count_component,physical_area_world2=count_component*physical_texel_area,edge_connected=edge,basal_connected=basal,eligible=bool(valid)))
            if valid:chosen.append(cid)
        _,nearest_physical=distance_transform_edt(~physical_domain,return_indices=True)
        eligible &= np.isin(components[tuple(nearest_physical)],chosen)
    selected=(eligible & connected & ~protected & ~generated & (distance<=distance_limit) &
              (world_distance<=world_limit) & (z>=object_min_z-1e-6) &
              (z<=object_min_z+band))
    count=int(selected.sum())
    if count>policy['max_total_texels'] or count>colors.shape[0]*colors.shape[1]*fraction_limit:
        raise ValueError(f'Inferred-gap repair exceeds its narrow per-face/count budget: selected={count}, face_samples={colors.shape[0]*colors.shape[1]}, fraction={count/(colors.shape[0]*colors.shape[1]):.6f}, max_fraction={policy["max_face_fraction"]}, max_count={policy["max_total_texels"]}')
    if physical_domain is not None:
        physical_count=int(np.count_nonzero(selected & physical_domain))
        physical_samples=int(physical_domain.sum())
        if physical_count>physical_samples*fraction_limit:
            raise ValueError(f'Inferred-gap repair exceeds physical face budget: selected={physical_count}, physical_samples={physical_samples}')
        if component_limits is not None and (physical_count>component_limits['max_physical_texels'] or physical_count*physical_texel_area>component_limits['max_physical_area_world2']):
            raise ValueError(f'Combined physical components exceed explicit per-face cap: texels={physical_count}, area={physical_count*physical_texel_area:.6f}, limits={component_limits}, selected_components={[v for v in stats["components"] if v["eligible"]]}')
        stats.update(physical_repaired_texels=physical_count,physical_face_samples=physical_samples)
    donors=colors[tuple(nearest)]
    result[selected,:3]=donors[selected,:3]
    if not np.array_equal(result[~selected],colors[~selected]) or not np.array_equal(result[...,3],colors[...,3]):
        raise ValueError('Gap repair altered protected RGB or physical alpha')
    stats.update(distance_limit_texels=float(distance_limit),distance_limit_world=float(world_limit))
    stats.update(eligible_samples=int(eligible.sum()),face_samples=int(colors.shape[0]*colors.shape[1]),bottom_band_world=float(band),connected_basal_component=bottom_band_override is not None)
    if count:
        stats.update(repaired_texels=count,maximum_distance_texels=float(distance[selected].max()),
                     maximum_distance_world=float(world_distance[selected].max()))
    return result,selected,stats
