"""Opt-in, face-scoped finite ray origins for generated texture visibility."""
import numpy as np


def bounded_faces(manifest, face_counts):
    scope=manifest.get('texture_generated_bounded_visibility',{})
    if not isinstance(scope,dict) or not set(scope)<=set(face_counts):
        raise ValueError('Bounded visibility names a foreign receiver')
    result=set()
    for name,faces in scope.items():
        if (not isinstance(faces,list) or not faces or len(set(faces))!=len(faces)
                or any(type(f) is not int or not 0<=f<face_counts[name] for f in faces)):
            raise ValueError('Bounded visibility requires exact existing face indices')
        receiver_scope=manifest.get('texture_receiver_face_indices')
        if receiver_scope is not None and not set(faces)<=set(receiver_scope.get(name,[])):
            raise ValueError('Bounded visibility exceeds receiver face scope')
        result.update((name,f) for f in faces)
    return result


def far_plane(vertices,direction):
    vertices=np.asarray(vertices,dtype=np.float64);direction=np.asarray(direction,dtype=np.float64)
    if (vertices.ndim!=2 or vertices.shape[1]!=3 or not len(vertices) or direction.shape!=(3,)
            or not np.isfinite(vertices).all() or not np.isfinite(direction).all()
            or abs(np.linalg.norm(direction)-1)>1e-5):
        raise ValueError('Finite normalized generated visibility bounds required')
    return float((vertices@direction).max()+1.)


def bounded_origin(point,direction,plane):
    point=np.asarray(point,dtype=np.float64);direction=np.asarray(direction,dtype=np.float64)
    distance=float(plane-np.dot(point,direction))
    if not np.isfinite(distance) or distance<=0:
        raise ValueError('Generated sample lies outside the bound visibility plane')
    return point+direction*distance


def visible_sample(hit, point, hit_owner, expected_owner):
    return (hit is not None and hit_owner==expected_owner and
            float(np.linalg.norm(np.asarray(hit,dtype=np.float64)-np.asarray(point,dtype=np.float64)))<=.02)


def background_faces(manifest, face_counts):
    key='texture_generated_background_face_indices'
    if key not in manifest:return None
    if manifest.get('texture_generated_background_max_rgb') is None:
        raise ValueError('Face-scoped background filtering requires an explicit threshold')
    proxy=dict(manifest,texture_generated_bounded_visibility=manifest[key])
    scope=bounded_faces(proxy,face_counts)
    if not scope:raise ValueError('Face-scoped background filtering requires nonempty scope')
    return scope
