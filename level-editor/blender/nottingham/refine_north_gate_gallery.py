"""Reconstruct the open timber gallery from its upper-layer mask openings."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT/'level-editor/work/nottingham-refinement'


def geometry():
    from refine_fortifications import supplemental_geometry, prism_geometry
    native = json.loads((WORK/'source-states/level.json').read_text())['sight_obstacles']
    evidence = json.loads((WORK/'fortifications-audit/measurements.json').read_text())
    generated, notes, limits = supplemental_geometry('nottingham-north-gate-gallery', evidence)
    holes = json.loads((WORK/'fortifications-audit/gallery-openings-measured.json').read_text())['holes']
    points = native[185]['points']
    left, right = points[2], points[1]
    arch = [(left['x'],450),(1335,435),(1350,410),(1365,398),(1380,389),
            (1390,390),(1405,400),(1420,420),(right['x'],432)]
    def interpolate(x, points):
        for (a, v), (b, w) in zip(points, points[1:]):
            if a <= x <= b:
                return v+(w-v)*(x-a)/(b-a)
        raise ValueError(x)
    def y_at(x):
        return left['y']+(right['y']-left['y'])*(x-left['x'])/(right['x']-left['x'])
    cuts = sorted(set([x for x, y in arch]+[x for h in holes for x in h['source_x']]))
    vertices, faces = [], []
    def cell(a,b,lower,upper):
        # Separate closed wall cells meet at exact cut planes. Their internal
        # faces are retained rather than relying on a fragile polygon boolean.
        local=[]
        for back in [False,True]:
            for x,z in [(a,lower(a)),(b,lower(b)),(b,upper(b)),(a,upper(a))]:
                # Extend the aperture through the measured wall depth along
                # its source ray. A perpendicular box extrusion shifts the
                # far jamb into the narrow visible opening by several pixels.
                slope=(right['y']-left['y'])/(right['x']-left['x'])
                depth=points[3]['y']-left['y']-slope*(points[3]['x']-left['x'])
                dy=depth if back else 0
                dz=dy if back and abs(z-189.501)>1e-5 else 0
                local.append((x,y_at(x)+dy,z+dz))
        n=len(vertices);vertices.extend(local)
        faces.extend([[n+i for i in f] for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
    roof=189.501
    for a,b in zip(cuts,cuts[1:]):
        hole=next((h for h in holes if h['source_x'][0]<(a+b)/2<h['source_x'][1]),None)
        bottom=lambda x:y_at(x)-interpolate(x,arch)
        if hole:
            low=lambda x:y_at(x)-(hole['bottom_line'][0]*x+hole['bottom_line'][1])
            high=lambda x:min(roof-.05,y_at(x)-(hole['top_line'][0]*x+hole['top_line'][1]))
            cell(a,b,bottom,low)
            cell(a,b,high,lambda x:roof)
        else:
            cell(a,b,bottom,lambda x:roof)
    generated[185]=(vertices,faces)
    for number in [184,187,188,198]:
        generated[number]=prism_geometry(native[number]['points'])
    return generated,holes


def refine():
    import bpy
    import bmesh
    from mathutils import Vector
    from refine_church import fingerprint
    asset='nottingham-north-gate-gallery'
    objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH']
    selected={int(o['source_node'].split('-')[1]):o for o in objects if o.get('asset_group')==asset}
    if set(selected)!={184,185,186,187,188,198}:raise ValueError('Unexpected gallery ownership')
    outside={o.name:fingerprint(o)for o in objects if o not in selected.values()}
    generated,holes=geometry();records=[]
    for number,(vertices,faces) in generated.items():
        obj=selected[number];inverse=obj.matrix_world.inverted();mesh=bpy.data.meshes.new(f'Gallery {number} open timber')
        mesh.from_pydata([inverse@Vector((x,-y/math.sin(math.radians(35)),z/math.cos(math.radians(35))))for x,y,z in vertices],[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);degenerate=sum(f.calc_area()<1e-9 for f in bm.faces)
        if bad or degenerate:raise ValueError(f'Invalid gallery topology {number}: {bad}/{degenerate}')
        bm.to_mesh(mesh);bm.free();mat=bpy.data.materials.get('Gallery unsupported neutral')or bpy.data.materials.new('Gallery unsupported neutral');mat.diffuse_color=(.5,.5,.5,1);mesh.materials.append(mat);mesh.uv_layers.new(name='UnprojectedUV');obj.data=mesh
        obj['refinement_recipe']='nottingham/refine_north_gate_gallery.py';obj['geometry_approval']='pending';records.append({'source_node':f'building-{number}','vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':bad,'degenerate_faces':degenerate})
    drift=[name for name,value in outside.items()if fingerprint(bpy.data.objects[name])!=value]
    if drift:raise ValueError(drift)
    return {'asset_id':asset,'recipe':str(Path(__file__).resolve()),'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'opening_mask':120,'opening_count':4,'measured_openings':holes,'objects':records,'outside_object_changes':drift,'changes':['Replace solid upper front wall with four native-mask measured openings and timber posts.','Retain lower planking and arched masonry beneath the railing, measured walkway deck184, and rear masonry186 visible through the openings.','Reconstruct deck, roof and piers as closed native-coordinate prisms with outward normals, removing imported face seams and inverted surfaces.'],'limitations':['Opening edge fits smooth the raster mask staircase; roof underside clips the uppermost two-pixel fringe of the left aperture.','Concealed jamb tunnels follow source rays through the native wall-depth offset, avoiding unsupported obstruction of narrow mask openings.','Rear masonry and passage depth remain measured volume hypotheses.'],'approval':'pending'}
