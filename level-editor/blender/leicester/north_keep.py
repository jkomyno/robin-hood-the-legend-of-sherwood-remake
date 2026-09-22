"""Native camera-prism room cutaways and independently owned keep floor receivers."""
import argparse
import collections
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import convex_hull_2d

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from south_cutaway import boundary
from north_keep_furniture import refine as refine_seating

ASSET = 'leicester-great-keep'
PATCHES = ('patch-005', 'patch-006')
COVERS = (*range(282, 292), *range(295, 301))
INTERIORS = {'patch-005': (292,), 'patch-006': (293, 294)}
TAG = 'leicester-keep-native-room-cutaway-v1'


def remove(obj):
    bpy.data.objects.remove(obj, do_unlink=True)


def finish(mesh, weld=.001, close=False, convex=False):
    bm=bmesh.new();bm.from_mesh(mesh)
    if not convex and weld == .001 and all(e.is_manifold for e in bm.edges):
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-8)
    if not convex and weld == .001 and all(e.is_manifold for e in bm.edges) and all(f.calc_area() > 0 for f in bm.faces):
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(mesh)
        counts={'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':0,'degenerate_faces':0}
        bm.free()
        if not mesh.uv_layers:mesh.uv_layers.new(name='UVMap')
        return counts
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=weld)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6)
    if convex:
        bmesh.ops.delete(bm,geom=list(bm.faces),context='FACES_ONLY')
        bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
        loose=[e for e in bm.edges if not e.link_faces]
        if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
        loose=[v for v in bm.verts if not v.link_edges]
        if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.verts.index_update();seen=set();duplicates=[]
    for face in bm.faces:
        key=tuple(sorted(v.index for v in face.verts))
        if key in seen:duplicates.append(face)
        seen.add(key)
    if duplicates:bmesh.ops.delete(bm,geom=duplicates,context='FACES_ONLY')
    edges=[e for e in bm.edges if e.is_boundary]
    if close and edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces)
    kinds=collections.Counter(len(e.link_faces) for e in bm.edges if not e.is_manifold)
    bm.to_mesh(mesh);bm.free()
    if bad or deg:raise RuntimeError(f'{mesh.name}: topology invalid {bad} edges/{deg} faces; edge fans {dict(kinds)}')
    if not mesh.uv_layers:mesh.uv_layers.new(name='UVMap')
    return {'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':bad,'degenerate_faces':deg}


def cutter(collection,patch):
    from PIL import Image,ImageFilter
    import tempfile
    # Retain a one-pixel roof rim inside the native boundary. This keeps adjacent
    # room prisms separate and avoids coincident Boolean boundaries.
    with tempfile.NamedTemporaryFile(suffix='.png') as temporary:
        eroded=Image.open(patch['graphic']['alpha']).convert('L').filter(ImageFilter.MinFilter(3))
        remaining={(x,y) for y in range(eroded.height) for x in range(eroded.width) if eroded.getpixel((x,y))}
        regions=[]
        while remaining:
            queue=[remaining.pop()];region=set(queue)
            while queue:
                x,y=queue.pop()
                for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if p in remaining:remaining.remove(p);region.add(p);queue.append(p)
            regions.append(region)
        clean=Image.new('L',eroded.size)
        for p in max(regions,key=len):clean.putpixel(p,255)
        clean.save(temporary.name)
        contour=boundary(Path(temporary.name),patch['graphic']['bbox'][:2])
    si,co=math.sin(math.radians(35)),math.cos(math.radians(35))
    verts=[(x,-y/si-depth*co,depth*si) for depth in (-1000.,1000.) for x,y in contour]
    n=len(contour);faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    mesh=bpy.data.meshes.new(patch['id']+' native cut prism');mesh.from_pydata(verts,[],faces)
    finish(mesh)
    obj=bpy.data.objects.new(mesh.name,mesh);collection.objects.link(obj);obj.hide_render=True
    return obj,contour


def piece(source,tool,operation,collection):
    obj=source.copy();obj.data=source.data.copy();collection.objects.link(obj)
    obj.hide_render=False;obj.hide_set(False)
    modifier=obj.modifiers.new('Native camera boundary','BOOLEAN');modifier.operation=operation
    modifier.solver='MANIFOLD';modifier.object=tool
    bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name);obj.select_set(False)
    if not obj.data.polygons:remove(obj);return None
    check=bmesh.new();check.from_mesh(obj.data)
    print('BOOLEAN RAW',source.name,operation,len(check.verts),len(check.faces),dict(collections.Counter(len(e.link_faces) for e in check.edges if not e.is_manifold)),flush=True);check.free()
    finish(obj.data,close=True)
    return obj


def selector(obj):
    return {'source_node':obj['source_node'],'projection_component':obj['projection_component'],
            'patch_id':obj['reveal_component_patch_id']}


def receivers(objects,patch):
    result=[]
    for node in sorted({o['source_node'] for o in objects}):
        result.append({'source_node':node,'projection_components':[o['projection_component'] for o in objects if o['source_node']==node],
                       'patch_id':patch})
    return result


def floor(source,roof_objects,patch,collection):
    points=[o.matrix_world@v.co for o in roof_objects for v in o.data.vertices]
    points2=[Vector((p.x,p.y)) for p in points];hull=convex_hull_2d(points2)
    xy=[points2[i] for i in hull];n=len(xy)
    verts=[Vector((p.x,p.y,z)) for z in (170.92,171.04) for p in xy]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    mesh=bpy.data.meshes.new(patch+' dedicated room floor')
    mesh.from_pydata([source.matrix_world.inverted()@v for v in verts],[],faces);mesh.update();finish(mesh)
    for material in source.data.materials:mesh.materials.append(material)
    obj=source.copy();obj.data=mesh;collection.objects.link(obj)
    obj.name='Great Keep / '+patch+' dedicated floor';obj['projection_component']=patch+'-room-floor'
    obj['reveal_component_patch_id']=patch;obj['reveal_component_role']='interior-floor';obj['north_keep_recipe']=TAG
    obj['todo']='Floor footprint follows measured roof footprint; unsupported hidden boundary remains inferred.'
    return obj


def refine(workspace):
    from refinement_workspace import initialize_working_projection
    workspace=Path(workspace);config=json.loads((workspace/'workspace.json').read_text())
    manifest_path=Path(initialize_working_projection(workspace));manifest=json.loads(manifest_path.read_text())
    collection=bpy.data.collections[config['collection_name']]
    owned=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
    if any(o.get('north_keep_recipe')==TAG for o in owned):return {'tag':TAG,'reused':True}
    originals={int(o['source_node'][9:]):o for o in owned}
    floors={}
    for patch,node,roof in [('patch-005',281,range(282,287)),('patch-006',280,range(287,291))]:
        base=originals[node];base['projection_component']='source-envelope';base['reveal_component_patch_id']=patch
        floors[patch]=floor(base,[originals[i] for i in roof],patch,collection)
    tools={};contours={}
    for patch in PATCHES:
        record=next(p for p in manifest['patches'] if p['id']==patch)
        tools[patch],contours[patch]=cutter(collection,record)
    for patch in PATCHES:
        full=floors[patch]
        clipped=piece(full,tools[patch],'INTERSECT',collection)
        if clipped is None:raise RuntimeError('Room floor misses its native reveal boundary')
        clipped.name=full.name+' / native footprint'
        remove(full);floors[patch]=clipped
    covers={p:[] for p in PATCHES};inside={p:[floors[p]] for p in PATCHES};outside={p:[] for p in PATCHES};report=[]
    for node in (*COVERS,292,293,294):
        original=originals[node]
        remaining=original.copy();remaining.data=original.data.copy();collection.objects.link(remaining)
        cleanup=finish(remaining.data,weld=.75,close=True,convex=node in (*range(282,291), *range(295,301)))
        relevant=PATCHES if node in COVERS else tuple(p for p in PATCHES if node in INTERIORS[p])
        parts=[]
        for patch in relevant:
            if remaining is None:break
            intersection=piece(remaining,tools[patch],'INTERSECT',collection)
            difference=piece(remaining,tools[patch],'DIFFERENCE',collection)
            remove(remaining);remaining=difference
            if intersection is None:continue
            role='removable-cover' if node in COVERS else 'interior-wall'
            intersection.name=original.name+' / '+patch+' '+role
            intersection['projection_component']=patch+'-'+role
            intersection['reveal_component_patch_id']=patch;intersection['reveal_component_role']=role
            intersection['north_keep_recipe']=TAG
            (covers if node in COVERS else inside)[patch].append(intersection)
            parts.append({**selector(intersection),**finish(intersection.data)})
        if remaining:
            patch=relevant[0];remaining.name=original.name+' / retained shell'
            remaining['projection_component']='retained-shell';remaining['reveal_component_patch_id']=patch
            remaining['reveal_component_role']='retained-shell';remaining['north_keep_recipe']=TAG
            if node not in COVERS:outside[patch].append(remaining)
            parts.append({**selector(remaining),**finish(remaining.data)})
        original.hide_render=True;original.hide_set(True);original['north_keep_baseline']=TAG
        report.append({'source_node':original['source_node'],'cleanup':cleanup,'parts':parts})
    for tool in tools.values():remove(tool)
    for patch,node in [('patch-005',281),('patch-006',280)]:
        outside[patch].append(originals[node])
        review=manifest['projection_reviews'][patch]
        review['receiver_nodes']=sorted(set(review['receiver_nodes'])|{o['source_node'] for o in inside[patch]})
        review['partial_cover_nodes']=sorted({o['source_node'] for o in covers[patch]})
        review['exclude_occluder_components']=[selector(o) for o in covers[patch]]
        review['receiver_components']={'exterior':receivers(outside[patch],patch),
                                      'interior-'+patch:receivers(inside[patch],patch)}
        review['render_visibility']['revealed']['hidden_components']=[selector(o) for o in covers[patch]]
        review['render_visibility']['covered']['hidden_components']=[selector(floors[patch])]
        review['geometry_ready']=False
        review['evidence']='Native patch alpha camera prisms inset one pixel, retaining the largest connected interior and source roof rims; dedicated roof-footprint floor receivers. Candidate requires paired state inspection.'
        review['render_visibility']['evidence']=review['evidence']
        review['render_visibility']['limitations']=['Hidden Boolean caps, floor footprints and one-pixel retained boundary rims are inferred; paired state inspection pending.']
    seating=refine_seating(config['collection_name'])
    update_masks(workspace)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    bpy.context.view_layer.update()
    return {'tag':TAG,'contours':contours,'components':report,'furniture':seating,'status':'candidate requiring projection and paired state review'}


def update_masks(workspace):
    path=Path(workspace)/'source-masks.json';data=json.loads(path.read_text())
    rows=[('patch-005',281,'patch-005-room-floor',[381],[384,385,386,387,388,391,*range(409,418)]),
          ('patch-006',280,'patch-006-room-floor',[382],[385,389,390,392,393,394,395,*range(398,409)]),
          ('patch-005',292,'patch-005-interior-wall',[385,387,388],[414,415]),
          ('patch-006',293,'patch-006-interior-wall',[390],[395]),
          ('patch-006',294,'patch-006-interior-wall',[389],[393,420])]
    for patch,node,component,masks,excluded in rows:
        entries=data['projections']['interior-'+patch]['assignments']
        entries[:]=[a for a in entries if (a.get('source_node'),a.get('projection_component'))!=(f'building-{node}',component)]
        entries.append({'source_node':f'building-{node}','projection_component':component,'mask_indices':masks,
            'exclude_mask_indices':excluded,'reviewed':True,'exclusions_reviewed':True,
            'exclusion_reason':'Native furniture, parapet and retained roof masks exclude pixels from separate floor/wall receivers.',
            'evidence':'Visual patch005/006 source contours and native contact16/17; camera-prism components retain stable source ownership.'})
    path.write_text(json.dumps(data,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);workspace=args.workspace.resolve()
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise RuntimeError('Open owned worker model')
    result=refine(workspace)
    if result.get('reused'):
        print(json.dumps(result));return
    (workspace/'geometry-report.json').write_text(json.dumps(result,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));print(json.dumps({'tag':result['tag'],'components':len(result['components']),'status':result['status']}))

if __name__=='__main__':main()
