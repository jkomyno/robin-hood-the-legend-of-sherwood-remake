"""Round-2 (integrated-context) fixes for the great_hall lane.

The round-2 baseline already holds the round-1 geometry, so these edits are applied on
top of it and must be idempotent (clipping an already clipped mesh is a no-op).
"""
import great_hall_geom as G

# The hall-keep wall walk ends at the keep's door-tower face. In the covered art the walk,
# its parapets and mask 252 all stop at pixel x 1487. With the refined keep in place, the
# round-1 walls ran on to x 1503-1520 and showed 666 visible-but-rejected px of wall where
# the art paints the keep door tower (round-2 inspection/north-wall-east-end.png).
NORTH_WALL_END_X = 1487.0


# Ramp walkway 288 (round 2, corrected in round 3). The paving runs under the terrace and
# hall wall feet (cut at z 400-420), so the slab's back (terrace-side) edge is extended to
# reach under them. Round 2 moved only the top back corner north, which skewed every
# constant-t riser line relative to the painted steps (user, round 3: "those steps are
# wrong see texture projection"). Now the back edge is extended along the P->Q direction by
# a factor growing with t (Q'(t) = P(t) + (1 + LAMBDA*t) * (Q - P)), so every riser stays a
# straight line parallel to P->Q, where the painted riser shadows lie.
# Riser positions come from round-3 inspection/step-trace.json (fitted painted lines).
WALKWAY_BACK_LAMBDA = 1.11     # ~60 native y units at the top landing, 0 at the lower end
STEP_TRACE = ('/home/phire/data/dev/2026/robin-hood-the-legend-of-sherwood/level-editor/work/'
              'lincoln-refinement/round-3/assets/lincoln-hall-approach-ramp/inspection/step-trace.json')


def riser_ts():
    import json
    trace = json.loads(open(STEP_TRACE).read())
    if trace.get('source_sha256') != __import__('hashlib').sha256(G.SOURCE.read_bytes()).hexdigest():
        raise ValueError('step trace bound to a different source image')
    ts = [ln['t'] for ln in trace['lines']
          if 0.0 < ln['t'] < 0.95 and ln['w_covered'][1] - ln['w_covered'][0] >= 0.3]
    if len(ts) != 5:
        raise ValueError(f'expected 5 traced risers, got {ts}')
    return ts


def _ramp_walkway(by_node):
    import great_hall_ramp as RMP
    (p0, p1), (q0, q1) = RMP.P288, RMP.Q288
    q1n = (p1[0] + (1 + WALKWAY_BACK_LAMBDA) * (q1[0] - p1[0]),
           p1[1] + (1 + WALKWAY_BACK_LAMBDA) * (q1[1] - p1[1]))
    ts = riser_ts()
    trace = {'runs': [{'id': 'walkway-steps-288', 'corners': [{'t': t} for t in ts]}]}
    saved = (RMP.Q288, RMP.WEDGE)
    try:
        RMP.Q288 = (q0, q1n)
        RMP.WEDGE = [(q1n, RMP.WEDGE[0][1])] + RMP.WEDGE[1:]
        (v, f), info = RMP.walkway(trace)
    finally:
        RMP.Q288, RMP.WEDGE = saved
    stats = G.replace_mesh(by_node['building-288'], v, f, weld=0.3)
    return {'back_edge_lambda': WALKWAY_BACK_LAMBDA, 'back_edge_top': [round(c, 2) for c in q1n], **info, **stats}


def apply(asset, by_node):
    out = {}
    if asset == 'lincoln-hall-approach-ramp':
        out['building-288'] = _ramp_walkway(by_node)
    if asset == 'lincoln-hall-keep-north-wall':
        for node in ('building-229', 'building-231', 'building-232'):
            if node not in by_node:
                raise ValueError(f'round-2 fix: missing owned node {node}')
            stats = G.clip_above_plane(by_node[node], (NORTH_WALL_END_X, 1200.0, 500.0), (1.0, 0.0, 0.0))
            stats['chain_caps'] = _cap_open_end(by_node[node], NORTH_WALL_END_X)
            out[node] = {'clip_east_x': NORTH_WALL_END_X, **stats}
    return out


def _cap_open_end(obj, x_end):
    """Cap an open cut outline at x = x_end whose native seams leave gapped chains."""
    import bmesh
    from refine_great_hall import _cap_from_chains
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    on = {v for v in bm.verts if abs((mw @ v.co).x - x_end) < 1e-3}
    bmesh.ops.remove_doubles(bm, verts=list(on), dist=1.5)
    on = {v for v in bm.verts if abs((mw @ v.co).x - x_end) < 1e-3}
    edges = [e for e in bm.edges if e.is_boundary and all(v in on for v in e.verts)]
    faces = _cap_from_chains(bm, edges) if edges else []
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return len(faces)
