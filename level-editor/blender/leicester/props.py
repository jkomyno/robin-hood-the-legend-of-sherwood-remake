"""Measured prop profiles, preserving stable receivers and object transforms.

The imported footprint and elevation are anchors, not evidence for hidden
surfaces. Circular cross-sections, vessel wall thickness, and cavity depth are
explicit hypotheses for review. Run twice to verify idempotence before baking.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

VERSION = 'leicester-props-v2'
KINDS = {19: 'trough', 48: 'barrel', 52: 'trough',
         72: 'bucket', 88: 'trunk', 89: 'trunk', 90: 'trunk',
         91: 'trunk', 92: 'trunk', 102: 'barrel'}


def signature(obj):
    return hashlib.sha256(json.dumps({'v': [list(v.co) for v in obj.data.vertices],
        'f': [list(p.vertices) for p in obj.data.polygons]}, sort_keys=True).encode()).hexdigest()


def footprint(obj):
    """Minimum oriented rectangle of the inherited world-space footprint."""
    vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
    points = sorted({(round(v.x, 3), round(v.y, 3)) for v in vertices})
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    candidates = []
    for a, b in zip(hull, hull[1:]+hull[:1]):
        angle = math.atan2(b[1]-a[1], b[0]-a[0])
        c, s = math.cos(angle), math.sin(angle)
        xs = [x*c+y*s for x,y in points]
        ys = [-x*s+y*c for x,y in points]
        x0,x1,y0,y1 = min(xs),max(xs),min(ys),max(ys)
        candidates.append(((x1-x0)*(y1-y0), angle, x0,x1,y0,y1))
    _,angle,x0,x1,y0,y1 = min(candidates)
    return {'angle':angle, 'center':[(x0+x1)/2,(y0+y1)/2],
            'radii':[(x1-x0)/2,(y1-y0)/2],
            'bottom':min(v.z for v in vertices),'top':max(v.z for v in vertices)}


def make_profile(anchor, kind):
    cx,cy=anchor['center'];rx,ry=anchor['radii']
    bottom,top=anchor['bottom'],anchor['top'];height=top-bottom
    if min(rx,ry,height) <= 0:
        raise ValueError('A volumetric prop requires positive footprint and height')
    c,s=math.cos(anchor['angle']),math.sin(anchor['angle'])
    def world(x,y,z):
        return ((cx+x)*c-(cy+y)*s,(cx+x)*s+(cy+y)*c,bottom+z*height)
    if kind == 'trough':
        # Four outer walls, a rim, four inner walls, and two hidden closures.
        thickness=max(0.8,min(rx,ry)*0.22)
        innerx,innery=rx-thickness,ry-thickness
        if min(innerx,innery)<=0:
            raise ValueError('Trough wall thickness exceeds its footprint')
        rings=[(rx,ry,0),(rx,ry,1),(innerx,innery,1),(innerx,innery,0.2)]
        vertices=[world(x,y,z) for a,b,z in rings for x,y in [(-a,-b),(a,-b),(a,b),(-a,b)]]
        faces=[]
        for i in range(4):
            j=(i+1)%4
            faces.extend([(i,j,4+j,4+i),(4+i,4+j,8+j,8+i),(8+i,8+j,12+j,12+i)])
        faces.extend([(3,2,1,0),(12,13,14,15)])
        return vertices,faces,{'corners':4,'inferred_wall_thickness':thickness,'inferred_cavity_floor_fraction':0.2}
    n=16 if kind in ('barrel','bucket') else 12
    if kind=='barrel':rings=[(0,.87),(.12,.94),(.5,1),(.88,.94),(1,.87)]
    elif kind=='bucket':rings=[(0,.76),(.88,1),(1,1),(1,.78),(.18,.60)]
    elif kind=='stump':rings=[(0,1),(.2,.95),(1,.86)]
    elif kind=='trunk':rings=[(0,1),(.08,.88),(.4,.77),(1,.60)]
    elif kind=='rock':rings=[(0,1),(.45,.98),(.82,.7),(1,.25)]
    else:raise ValueError(kind)
    vertices=[world(rx*r*math.cos(2*math.pi*i/n),ry*r*math.sin(2*math.pi*i/n),z)
              for z,r in rings for i in range(n)]
    faces=[tuple(reversed(range(n)))]
    for ring in range(len(rings)-1):
        for i in range(n):
            j=(i+1)%n;a=ring*n;b=(ring+1)*n
            faces.append((a+i,a+j,b+j,b+i))
    faces.append(tuple(range((len(rings)-1)*n,len(rings)*n)))
    return vertices,faces,{'radial_segments':n,'profile_rings':rings}


def refine(obj):
    node=obj['source_node'];index=int(node.rsplit('-',1)[1]);kind=KINDS[index]
    before=signature(obj);transform=[list(row) for row in obj.matrix_world]
    if obj.get('leicester_prop_anchor'):
        anchor=json.loads(obj['leicester_prop_anchor'])
    else:
        anchor=footprint(obj);obj['leicester_prop_anchor']=json.dumps(anchor,sort_keys=True)
    vertices,faces,details=make_profile(anchor,kind)
    mesh=bpy.data.meshes.new(obj.name+' profile')
    inverse=obj.matrix_world.inverted()
    mesh.from_pydata([inverse@Vector(v) for v in vertices],[],faces);mesh.update()
    mesh.uv_layers.new(name='UVMap')
    for material in obj.data.materials:mesh.materials.append(material)
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology={'vertices':len(bm.verts),'faces':len(bm.faces),
              'boundary_edges':sum(e.is_boundary for e in bm.edges),
              'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
              'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    bm.to_mesh(mesh);bm.free();obj.data=mesh;obj['leicester_prop_recipe']=VERSION
    assert transform==[list(row) for row in obj.matrix_world]
    return {'object':obj.name,'source_node':node,'kind':kind,'anchor':anchor,
            'before_geometry_sha256':before,'after_geometry_sha256':signature(obj),
            'world_transform_drift':0,'topology':topology,'profile':details}


def run(workspace):
    workspace=Path(workspace).resolve()
    config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':
        raise ValueError('Open the isolated worker model.blend')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import validate
    validate(workspace)
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects
             if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    if not targets or any(int(o['source_node'].rsplit('-',1)[1]) not in KINDS for o in targets):
        raise ValueError('Recipe only supports measured freestanding vessels/stump/rocks')
    result=[refine(o) for o in targets]
    first=[signature(o) for o in targets]
    for o in targets:refine(o)
    if first!=[signature(o) for o in targets]:raise ValueError('Recipe is not idempotent')
    report={'recipe':VERSION,'asset_id':config['asset_id'],'objects':result,
        'idempotence':'PASS','projection_status':'STALE; run modified packet',
        'source_supported':'Visible round vessel/trunk silhouettes and rectangular trough opening; footprint/elevation inherited from authored receiver.',
        'limitations':['Hidden vessel depth, circular cross-section and wall thickness are hypotheses.',
                      'Small handles, hoops, woodgrain and stone chips remain texture detail; no unseen detail is asserted exact.',
                      'Source masks and fixed-camera review determine which rebuilt surfaces receive known pixels.',
                      *(['Tree receiver covers the visible trunk only; canopy and branches remain on the flat map source and need a separate foliage reconstruction.'] if any(r['kind']=='trunk' for r in result) else [])],
        'approval_status':'refinement-in-progress','texture_generation':'not-started'}
    validate(workspace)
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection'/'props-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
