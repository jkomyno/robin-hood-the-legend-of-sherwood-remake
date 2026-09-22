"""Measured rural geometry recipes. Projection must be refreshed after refine()."""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

TAG = 'nottingham_village_recipe'
SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))


def _geometry_hash(obj):
    payload = {'vertices': [list(v.co) for v in obj.data.vertices],
               'faces': [list(p.vertices) for p in obj.data.polygons]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _mesh(name, vertices, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bad = {'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
           'degenerate_faces': sum(f.calc_area() < 1e-7 for f in bm.faces)}
    if any(bad.values()):
        bm.free()
        raise ValueError(f'{name}: {bad}')
    bm.to_mesh(mesh); bm.free()
    uv = mesh.uv_layers.new(name='Source projection')
    for p in mesh.polygons:
        for li in p.loop_indices:
            v = mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv = (v.x/2304, 1-(-v.y*SIN-v.z*COS)/3520)
    return mesh, bad


def _attach(source, label, mesh):
    obj = bpy.data.objects.new(label, mesh)
    source.users_collection[0].objects.link(obj)
    for key in source.keys(): obj[key] = source[key]
    obj[TAG] = 1
    obj['projection_component'] = label
    # All new coordinates are measured in world space. Keep the asset parent
    # while compensating its matrix, preserving source transforms exactly.
    obj.parent = source.parent
    if obj.parent: obj.matrix_parent_inverse = obj.parent.matrix_world.inverted()
    material = bpy.data.materials.get('Nottingham unobserved neutral')
    if material is None:
        material = bpy.data.materials.new('Nottingham unobserved neutral')
        material.diffuse_color = (.45,.45,.45,1)
    mesh.materials.append(material)
    return obj


def _owned_components(mesh, sources, selector, label):
    """Retain every canonical receiver while splitting a watertight assembly."""
    buckets={node:[] for node in sources}
    for polygon in mesh.polygons: buckets[selector(polygon)].append(polygon.index)
    output=[]
    for node,indices in buckets.items():
        if not indices: raise ValueError(f'Canonical receiver has no replacement faces: {node}')
        copy=mesh.copy();bm=bmesh.new();bm.from_mesh(copy);bm.faces.ensure_lookup_table()
        wanted=set(indices)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in wanted],context='FACES')
        bm.to_mesh(copy);bm.free();copy.update()
        obj=_attach(sources[node],label+' / '+node,copy)
        obj['canonical_source_nodes']=','.join(sorted(sources))
        obj['shared_seams']='Coincident boundary vertices form a closed aggregate shell across canonical receivers.'
        output.append(obj.name)
        sources[node].hide_render=True;sources[node].hide_set(True)
    return output


def _bridge(sources):
    front = sources['building-290']
    # Source-visible spring/crown landmarks, in full-resolution artwork pixels.
    # Each arch remains a true opening; the unobserved reverse follows the same
    # opening profile and is explicitly an inferred structural continuation.
    arches = [((1418,3197),(1422,3173),(1432,3158),(1445,3154),(1460,3161),(1475,3178),(1480,3202)),
              ((1500,3215),(1503,3196),(1512,3181),(1523,3179),(1538,3185),(1550,3199),(1555,3218))]
    ax, ay = 1347.75, -5432.77
    bx, by = 1586.61, -5573.47
    def plane(x): return ay+(by-ay)*(x-ax)/(bx-ax)
    def from_pixel(p):
        x,y=p; wy=plane(x)
        return Vector((x,wy,(-y-SIN*wy)/COS))
    # Vegetation conceals the pier bases; stop at the last visible masonry.
    lower = [Vector((ax,plane(ax),-27)), Vector((1406,plane(1406),-102))]
    lower.extend(from_pixel(p) for p in arches[0])
    lower += [Vector((1485,plane(1485),-106)), Vector((1495,plane(1495),-102))]
    lower.extend(from_pixel(p) for p in arches[1])
    lower += [Vector((1564,plane(1564),-37)), Vector((bx,plane(bx),-20))]
    outline = [Vector((ax,plane(ax),8)), Vector((bx,plane(bx),8))]+list(reversed(lower))
    depth = Vector((39.0,86.0,0))
    n=len(outline)
    vertices=outline+[p+depth for p in outline]
    faces=[tuple(range(n)), tuple(reversed(range(n,2*n)))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh, validation=_mesh('Two-arch bridge masonry',vertices,faces)
    obj=_attach(front,'Two-arch bridge / arch masonry and deck',mesh)
    return {'component':obj.name,'source_node':'building-290','arches':2,
            'arch_landmarks_source_pixels':arches,'validation':validation,
            'inference':['Bridge depth follows parapet separation; rear arch continuation is inferred.',
                         'Pier bases stop at visible masonry above concealing plants; underwater foundations are unknown.'],
            'geometry_sha256':_geometry_hash(obj)}


def _barn(sources):
    source = sources['building-261']
    # Eaves and ridge endpoints coincide with the artwork-supported footprint.
    # Smooth shoulders replace colliding independent triangular prisms.
    a=Vector((1086.12,-5218.19,64.8)); b=Vector((1014.73,-5100.11,64.8))
    c=Vector((830.13,-5211.81,64.8)); d=Vector((901.46,-5329.68,64.8))
    r=Vector((1006.07,-5180.78,144.54)); t=Vector((891.42,-5249.97,144.51))
    verts=[]; faces=[]
    def face(points):
        start=len(verts); verts.extend(points); faces.append(tuple(range(start,len(verts))))
    front=[]; rear=[]
    for k in range(5):
        f=k/4
        bulge=3.0*4*f*(1-f)
        front.append([t.lerp(d,f)+Vector((0,0,bulge)),r.lerp(a,f)+Vector((0,0,bulge))])
        rear.append([t.lerp(c,f)+Vector((0,0,bulge)),r.lerp(b,f)+Vector((0,0,bulge))])
    for rows in (front,rear):
        for k in range(4): face([rows[k][0],rows[k][1],rows[k+1][1],rows[k+1][0]])
    face([row[1] for row in front]+[row[1] for row in reversed(rear[1:])])
    face([row[0] for row in front]+[row[0] for row in reversed(rear[1:])])
    ring=[a,b,c,d]
    for k,p in enumerate(ring):
        q=ring[(k+1)%4]; face([p,q,Vector((q.x,q.y,0)),Vector((p.x,p.y,0))])
    face([Vector((p.x,p.y,0)) for p in reversed(ring)])
    # Weld only exact shared construction vertices, avoiding any silhouette drift.
    compact=[]; remap={}; lookup={}
    for k,p in enumerate(verts):
        key=tuple(round(v,5) for v in p)
        if key not in lookup: lookup[key]=len(compact);compact.append(p)
        remap[k]=lookup[key]
    clean=[]
    for f in faces:
        ids=list(dict.fromkeys(remap[k] for k in f))
        if len(ids)>=3:clean.append(ids)
    mesh,validation=_mesh('Low barn / closed rounded thatch shell',compact,clean)
    def owner(p):
        if p.center.z < 65: return 'building-261'
        if p.center.x < 898: return 'building-263'
        return 'building-262'
    names=_owned_components(mesh,{n:sources[n] for n in ('building-261','building-262','building-263')},
                            owner,'Low barn / closed rounded thatch shell')
    geometry_hash=hashlib.sha256(str([(tuple(v.co)) for v in mesh.vertices]).encode()).hexdigest()
    return {'components':names,'source_nodes':['building-261','building-262','building-263'],
            'validation':validation,'rounding_world_units':3,
            'inference':['Hidden rear thatch uses the observed roof form; no concealed windows or doors are invented.',
                         'Roof shoulder curvature is inferred between measured ridge and eave anchors.'],
            'geometry_sha256':geometry_hash}


def _dovecote_steps(sources):
    a=Vector((2139.54,-5519.25,0));run=Vector((18.52,13.12,0));width=Vector((-13.97,19.73,0))
    profile=[(0,0),(0,6.25),(1/3,6.25),(1/3,12.5),(2/3,12.5),(2/3,18.75),(1,18.75),(1,0)]
    front=[a+run*t+Vector((0,0,z)) for t,z in profile];n=len(front)
    vertices=front+[p+width for p in front]
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh,validation=_mesh('Dovecote / three stair treads',vertices,faces)
    obj=_attach(sources['building-301'],'Dovecote / three stair treads',mesh)
    sources['building-301'].hide_render=True;sources['building-301'].hide_set(True)
    return {'component':obj.name,'source_node':'building-301','treads':3,'top_landing_source_node':'building-300',
            'riser_world_units':6.25,'validation':validation,
            'evidence':'village-audit/dovecote-stairs.png: three exposed stair treads below the top landing',
            'inference':['Hidden stair underside is closed; equal riser height is a structural interpolation.']}


def _dovecote(sources):
    body=sources['building-293']
    world=[body.matrix_world@v.co for v in body.data.vertices]
    ring=[world[i].copy() for i in (32,33,34,35,36,37,38)]
    apex=Vector((2113.12,-5380.54,240.67))
    verts=[apex];faces=[]
    for k in range(1,6):
        f=k/5
        for p in ring: verts.append(apex.lerp(p,f)+Vector((0,0,3*4*f*(1-f))))
    n=len(ring)
    for j in range(n):faces.append((0,1+j,1+(j+1)%n))
    for k in range(4):
        for j in range(n):
            a=1+k*n+j;b=1+k*n+(j+1)%n
            faces.append((a,b,b+n,a+n))
    start=len(verts);verts += [p-Vector((0,0,3)) for p in ring]
    for j in range(n): faces.append((1+4*n+j,1+4*n+(j+1)%n,start+(j+1)%n,start+j))
    faces.append(tuple(reversed(range(start,start+n))))
    mesh,validation=_mesh('Dovecote / continuous thatch roof',verts,faces)
    nodes=[f'building-{i:03}' for i in range(294,300)]
    anchors={node:sources[node].matrix_world@sources[node].data.polygons[-1].center for node in nodes}
    def owner(p):
        return min(nodes,key=lambda node:(p.center.x-anchors[node].x)**2+(p.center.y-anchors[node].y)**2)
    names=_owned_components(mesh,{n:sources[n] for n in nodes},owner,'Dovecote / continuous thatch roof')
    geometry_hash=hashlib.sha256(str([(tuple(v.co)) for v in mesh.vertices]).encode()).hexdigest()
    return {'components':names,'source_nodes':nodes,'validation':validation,
            'thatch_shoulder_world_units':3,'eave_thickness_world_units':3,
            'inference':['The concealed northern roof sector closes the observed roof perimeter.',
                         'Intermediate convex roof curvature is inferred from thatch shading; eave anchors remain measured.',
                         'Stone wall, doorway and stair baseline remain unchanged; revealed interior is not modeled.'],
            'geometry_sha256':geometry_hash}


def refine(asset_id=None):
    sources={o.get('source_node'):o for o in bpy.context.scene.objects
             if o.type=='MESH' and not o.hide_render and not o.get(TAG)
             and (not asset_id or asset_id=='bridge-audit' or o.get('asset_group')==asset_id)}
    existing=[o for o in bpy.context.scene.objects if o.get(TAG) and (not asset_id or o.get('asset_group')==asset_id)]
    if existing:
        if asset_id=='nottingham-village-dovecote' and not any(o.get('source_node')=='building-301' for o in existing):
            return {'status':'extended','objects':[_dovecote_steps(sources)]}
        return {'status':'existing','objects':[o.name for o in existing]}
    if {'building-290','building-291'} <= sources.keys():
        result=_bridge(sources)
    elif {'building-261','building-262','building-263'} <= sources.keys():
        result=_barn(sources)
    elif all(f'building-{i:03}' in sources for i in range(293,300)):
        result=_dovecote(sources)
        result['stairs']=_dovecote_steps(sources)
    else:
        raise ValueError('No supported village recipe in this isolated asset')
    bpy.context.view_layer.update()
    return {'status':'created','asset_id':asset_id,'objects':[result],
            'transform_drift':0,'projection_status':'stale: rerun modified packet before review'}


def main():
    import argparse
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    workspace=args.workspace.resolve()
    config=json.loads((workspace/'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    before={o.name:([list(r) for r in o.matrix_world],_geometry_hash(o))
            for o in bpy.context.scene.objects if o.type=='MESH'
            and o.get('asset_group')!=config['asset_id']}
    report=refine(config['asset_id'])
    after={o.name:([list(r) for r in o.matrix_world],_geometry_hash(o))
           for o in bpy.context.scene.objects if o.type=='MESH'
           and o.get('asset_group')!=config['asset_id']}
    if before!=after:raise ValueError('Recipe changed an outside asset')
    report['outside_objects_preserved']=len(before)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    report_path=workspace/'geometry-recipe.json'
    if report_path.exists() and report['status'] in ('existing','extended'):
        old=json.loads(report_path.read_text())
        old.setdefault('subsequent_runs',[]).append(report)
        report=old
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
