"""Explicit view selection policies for unknown texture texels."""
DEFAULT='near-tie-blend'
SINGLE='best-facing-single'
def policy(manifest):
    value=manifest.get('texture_view_selection',DEFAULT)
    if value not in (DEFAULT,SINGLE):raise ValueError('Unknown texture view selection: '+str(value))
    return value

def preferred_views(manifest, face_counts):
    """Validate an explicit polygon-to-camera map within the receiver scope.

    ``texture_preferred_face_views`` maps exact receiver names to polygon-index
    strings and camera indices. Preference only reorders single-view sampling;
    the projector still checks facing, tile bounds, the unknown mask and first
    hit before accepting a texel. Unavailable preferred samples use the normal
    ranked fallback. Polygon indices refer to the approved mesh, not triangles.
    """
    mapping=manifest.get('texture_preferred_face_views',{})
    if not isinstance(mapping,dict):raise ValueError('Preferred face views must be an object map')
    if mapping and policy(manifest)!=SINGLE:raise ValueError('Preferred face views require best-facing-single')
    views={v['index'] for v in manifest['views']}
    result={}
    for name,faces in mapping.items():
        if name not in face_counts or not isinstance(faces,dict) or not faces:
            raise ValueError('Preferred face views require a nonempty receiver polygon map')
        for key,view in faces.items():
            if not isinstance(key,str) or not key.isdigit() or str(int(key))!=key or int(key)>=face_counts[name]:
                raise ValueError('Preferred face view references an absent polygon')
            scope=manifest.get('texture_receiver_face_indices')
            if scope is not None and int(key) not in scope.get(name,[]):
                raise ValueError('Preferred face view is outside the receiver polygon scope')
            if type(view) is not int or view not in views:raise ValueError('Preferred face view references an absent camera')
            result[(name,int(key))]=view
    return result

def ordered(candidates,selection,preferred=None):
    if selection==DEFAULT:return sorted(candidates,key=lambda item:item[0],reverse=True)
    if selection!=SINGLE:raise ValueError('Unknown texture view selection')
    # Round only floating point noise in identical camera-facing directions.
    # Highest projected pixel density wins a tie; lower view index is stable.
    return sorted(candidates,key=lambda item:(item[1]['index']==preferred,round(item[0],6),item[1]['crop']['height']/item[1]['ortho_scale'],-item[1]['index']),reverse=True)

def eligible(accepted,remaining,score,best_scores,selection):
    return (~accepted & remaining) if selection==SINGLE else (~accepted & (score>=best_scores-.12))
