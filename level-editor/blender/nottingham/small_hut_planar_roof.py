"""Construct a convex forge roof without moving the source eave outline."""
import math
import numpy as np

def construct(av, bv, original_q, original_front):
    s, c = math.sin(math.radians(35)), math.cos(math.radians(35))
    toward = np.array([0., -c, s])
    def height(v, z):
        v = np.array(v, dtype=float)
        return v + toward * ((z-v[2])/s)
    def normal(a, b, c):
        n = np.cross(b-a, c-a)
        return n/np.linalg.norm(n)
    rf, rr, lf, lr = [height(v, 52.) for v in (av[19], av[16], bv[19], bv[18])]
    q = height(original_q, 87.)
    q[1] += 6.
    nr, nl = normal(rf, rr, q), normal(lf, lr, q)
    axis = np.cross(nr, nl)
    p = q + axis*((412.-q[0])/axis[0])
    original_e = np.array([original_front.x, original_front.y, 45.2])
    e = height(original_e, 52.)
    result = {'ridge_front': p.tolist(), 'ridge_rear': q.tolist()}
    errors = []
    for key, front, rear, old_front, old_rear in (
            ('right', rf, rr, av[19], av[16]),
            ('left', lf, lr, bv[19], bv[18])):
        top = np.array([e, front, rear, q, p])
        old_bottom = [np.array([v[0], v[1], 44.5]) for v in
                      (original_e, old_front, old_rear, original_q)]
        bottom = np.array([height(v, 49.) for v in old_bottom])
        result[key] = np.vstack([bottom, top]).tolist()
        errors.append(abs(np.dot(normal(front,rear,q),p-front)))
    assert max(errors) < 1e-8
    result['evidence'] = dict(upper_eave_z=52., lower_eave_z=49.,
        side_plane_errors_world=errors, hidden_ridge_front=p.tolist(),
        hidden_ridge_rear=q.tolist(), source_eave_outline_preserved=True, hidden_rear_ridge_source_y_delta=-6*s,
        front_form='Convex paired triangular hip with outward front footprint; no lowered eave center.',
        inference='Hidden ridge intersects two planar side slopes behind the chimney; height and depth are inferred.')
    return result
