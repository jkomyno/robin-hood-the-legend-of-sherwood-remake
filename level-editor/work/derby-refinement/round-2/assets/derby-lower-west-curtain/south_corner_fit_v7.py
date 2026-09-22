"""Fit explicitly corresponding south parapet corners, retaining full wall bodies."""
import sys, json, math, hashlib
from pathlib import Path
sys.path[:0] = ['/usr/lib/python3.14', '/usr/lib/python3.14/lib-dynload', '/usr/lib/python3.14/site-packages']
import bpy, bmesh
from mathutils import Vector

root = Path(__file__).resolve().parent
out = root / 'inspection/south-corner-fit-v7'
out.mkdir(parents=True, exist_ok=True)
s, c = math.sin(math.radians(35)), math.cos(math.radians(35))
records = json.loads((root/'inspection/complete-wall-candidate-v5/corners/points.json').read_text())['records']
working = bpy.data.collections['Derby Working']

def fingerprint(o):
    return hashlib.sha256(json.dumps([[tuple(o.matrix_world@v.co) for v in o.data.vertices],
        [list(p.vertices) for p in o.data.polygons]]).encode()).hexdigest()

protected = {o.name: fingerprint(o) for o in working.objects if o.type == 'MESH' and
             o.get('source_node') not in ('building-023', 'building-042')}

def interp(t, samples):
    samples = sorted(samples)
    if t <= samples[0][0]: return samples[0][1]
    for (a, x), (b, y) in zip(samples, samples[1:]):
        if t <= b: return x + (y-x)*(t-a)/(b-a)
    return samples[-1][1]

reports = []
for node, record_id, span_ids in [('building-023', 'south-023-visible-long-run', [76,66,67]),
                                  ('building-042', 'south-042-six-gaps', [35,36])]:
    obj = next(o for o in working.objects if o.type == 'MESH' and o.get('source_node') == node and not o.hide_render)
    source = next(o for o in working.objects if o.type == 'MESH' and o.get('source_node') == node and o.hide_render and 'modeled battlements' not in o.name)
    source_points = [source.matrix_world@source.data.vertices[i].co for i in span_ids]
    top = max(p.z for p in source_points)
    crown = sorted([(-p.y*s-top*c, p.x) for p in source_points])
    x_to_y = sorted([(p.x, -p.y*s-top*c) for p in source_points])
    points = next(r['points'] for r in records if r['id'] == record_id)
    # Insert a support loop before changing the crown. Without it, the large
    # ground-to-crown polygons would bend throughout the entire wall height.
    band = bmesh.new(); band.from_mesh(obj.data)
    inv = obj.matrix_world.inverted()
    bmesh.ops.bisect_plane(band, geom=list(band.verts)+list(band.edges)+list(band.faces),
        plane_co=inv@Vector((0,0,190)),
        plane_no=obj.matrix_world.to_3x3().transposed()@Vector((0,0,1)),
        clear_inner=False, clear_outer=False, dist=1e-6)
    band.to_mesh(obj.data); band.free()
    world = [obj.matrix_world@v.co for v in obj.data.vertices]
    before_floor = sorted(tuple(p) for p in world if p.z < 190)
    dx, dz_top, dz_bottom, pairs = [], [], [], []
    for i in range(0, len(points), 4):
        for upper, lower in [(i, i+1), (i+3, i+2)]:
            tx, ty = points[upper]
            bx, by = points[lower]
            if node == 'building-023':
                q = ty
                px = interp(q, crown)
                dx.append((q, tx-px))
                dz_top.append((q, 0.0))
                dz_bottom.append((q, 23.5-(by-ty)/c))
            else:
                q = tx
                py = interp(q, x_to_y)
                dx.append((q, 0.0))
                dz_top.append((q, (py-ty)/c))
                dz_bottom.append((q, (py+23.5*c-by)/c))
            for k, z in [(upper,top), (lower,top-23.5)]:
                ex = interp(ty,crown) if node == 'building-023' else tx
                ey = ty if node == 'building-023' else interp(tx,x_to_y)
                expected = Vector((ex, -(ey+top*c)/s, z))
                index = min(range(len(world)), key=lambda j:(world[j]-expected).length)
                distance = (world[index]-expected).length
                if distance > .035:
                    raise ValueError(f'{node} corner {k+1}: expected construction vertex absent, distance {distance}')
                pairs.append({'id':k+1, 'vertex':index, 'observed':points[k],
                              'construction_vertex_distance':distance,
                              'before':[world[index].x,-world[index].y*s-world[index].z*c]})
    if node == 'building-023':
        dx = [(crown[0][0]-1,0)] + dx + [(1985,0)]
        dz_bottom = [(crown[0][0]-1,0)] + dz_bottom + [(1985,0)]
    inverse = obj.matrix_world.inverted()
    for v, p in zip(obj.data.vertices, world):
        if p.z <= 190: continue
        weight = min(1.0, (p.z-190)/(top-23.5-190))
        q = -p.y*s-top*c if node == 'building-023' else p.x
        cap_weight = min(1.0,max(0.0,(p.z-(top-23.5))/23.5))
        shift_z = interp(q,dz_bottom)*(1-cap_weight)+interp(q,dz_top)*cap_weight
        p.x += interp(q,dx)*weight
        p.z += shift_z*weight
        v.co = inverse@p
    obj.data.update()
    for pair in pairs:
        p = obj.matrix_world@obj.data.vertices[pair['vertex']].co
        pair['after'] = [p.x,-p.y*s-p.z*c]
        pair['error_pixels'] = math.dist(pair['after'],pair['observed'])
    assert max(p['error_pixels'] for p in pairs) < .002
    # Slightly uneven masonry shoulders produce nonplanar quads. Make their
    # triangulation explicit while preserving the shared edges and closed body.
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    validation = {'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                  'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces),
                  'volume':bm.calc_volume(signed=True)}
    assert validation['nonmanifold_edges']==0 and validation['degenerate_faces']==0 and validation['volume']>0
    bm.to_mesh(obj.data); bm.free()
    after_floor = sorted(tuple(obj.matrix_world@v.co) for v in obj.data.vertices if (obj.matrix_world@v.co).z<190)
    assert before_floor == after_floor
    reports.append({'node':node,'source_trace':record_id,'correspondences':sorted(pairs,key=lambda p:p['id']),
                    'unchanged_below_world_z':190,'validation':validation})
assert protected == {o.name:fingerprint(o) for o in working.objects if o.type=='MESH' and o.get('source_node') not in ('building-023','building-042')}
(out/'geometry.json').write_text(json.dumps({'status':'REQUIRES_VISUAL_REVIEW','source_pick_uncertainty_px':3,
    'method':'Explicit construction endpoints matched before deformation; exact corner residual is a construction check, not independent source-label validation.',
    'protected_meshes_unchanged':len(protected),'walls':reports},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
