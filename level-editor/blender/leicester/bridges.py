"""Source-counted Leicester timber bridge recipes; regenerate projection afterward."""
import argparse
import json
import hashlib
from pathlib import Path
import sys
import math
import bpy
import bmesh
from mathutils import Vector

TAG = 'leicester-footbridges-v1'
SINE, COSINE = math.sin(math.radians(35)), math.cos(math.radians(35))
FACES = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]


def object_mesh(name, vertices, faces, template, collection):
    mesh = bpy.data.meshes.new(name)
    inverse = template.matrix_world.inverted()
    mesh.from_pydata([inverse @ Vector(vertex) for vertex in vertices], [], faces)
    mesh.update()
    mesh.uv_layers.new(name='UVMap')
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh); collection.objects.link(obj)
    obj.parent = template.parent; obj.matrix_world = template.matrix_world.copy()
    for key in template.keys(): obj[key] = template[key]
    for material in template.data.materials: mesh.materials.append(material)
    obj['bridge_recipe'] = TAG
    obj['projection_component'] = name.rsplit(' / ',1)[-1]
    return obj


def beam(name, start, end, template, collection, width=2.5):
    start, end = Vector(start), Vector(end)
    direction = (end-start).normalized()
    reference = Vector((0,0,1)) if abs(direction.z)<0.9 else Vector((1,0,0))
    right = direction.cross(reference).normalized() * width/2
    up = direction.cross(right).normalized() * width/2
    return object_mesh(name, [p+r*right+u*up for p in (start,end) for r,u in [(-1,-1),(1,-1),(1,1),(-1,1)]], FACES, template, collection)


def world(point, height=None):
    return Vector((point['x'], -point['y']/SINE, (point['z_top'] if height is None else height)/COSINE))


def refine(workspace, native_path):
    config = json.loads((workspace/'workspace.json').read_text())
    ids = {'leicester-south-footbridge':386, 'leicester-east-village-footbridge':385, 'leicester-west-tower-footbridge':226}
    index = ids[config['asset_id']]
    level = json.loads(native_path.read_text())
    points = level['sight_obstacles'][index]['points']
    collection = bpy.data.collections[config['collection_name']]
    targets = [o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    original = next(o for o in targets if o.get('source_node')==f'building-{index:03}' and not o.get('bridge_added_component'))
    for obj in targets:
        if obj.get('bridge_added_component') == TAG: bpy.data.objects.remove(obj, do_unlink=True)
    additions=[]; n=len(points)
    if index in (385,386):
        vertices = [world(p,p['z_top']-7) for p in points]+[world(p) for p in points]
        faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        replacement=object_mesh(original.name+' deck replacement',vertices,faces,original,collection)
        old=original.data;original.data=replacement.data;replacement.data=old
        bpy.data.objects.remove(replacement,do_unlink=True)
    def add_beam(label,a,b,width=2.5):
        obj=beam(original.get('asset_name',config['asset_id'])+' / '+label,a,b,original,collection,width)
        obj['bridge_added_component']=TAG; additions.append(obj)
    rails=[]
    if index==386:
        rails=[(2,3,[.20,.46,.73,1.0],True),(1,0,[.20,.46,.73,1.0],True)]
    elif index==385:
        rails=[(2,3,[0,.19,.38,.59,.79,1],False),(1,0,[0,.18,.40,.61,.80],False)]
    else:
        # Only the unobscured tower landing balusters have reliable counts.
        rails=[(6,7,[0,.20,.40,.60,.80,1],False),(3,2,[0,.33,.66,1],False)]
    for side,(first,last,times,taper) in enumerate(rails):
        a,b=world(points[first]),world(points[last]); offset=Vector((0,0,27/COSINE))
        for i,t in enumerate(times):
            base=a.lerp(b,t);add_beam(f'rail {side+1} post {i+1}',base,base+offset)
        add_beam(f'rail {side+1} cap',a.lerp(b,times[0])+offset,a.lerp(b,times[-1])+offset,3)
        if taper:add_beam(f'rail {side+1} ground return',a,a.lerp(b,times[0])+offset,3)
    if index==385:
        # Two legs and paired braces below the near trestle are visible in the source.
        a,b=world(points[1]),world(points[0]); other_a,other_b=world(points[2]),world(points[3])
        for side,(start,end) in enumerate([(a,b),(other_a,other_b)]):
            top=start.lerp(end,.36)-Vector((0,0,7/COSINE));foot=top.copy();foot.z=-5/COSINE
            add_beam(f'trestle leg {side+1}',foot,top,4)
            for number,t in enumerate([0,.72]):add_beam(f'trestle {side+1} brace {number+1}',foot,start.lerp(end,t)-Vector((0,0,7/COSINE)),3)
    masks_path=Path(config['source_mask_manifest'])
    masks=json.loads(masks_path.read_text())
    entries=masks['projections']['exterior']['assignments']
    entries[:]=[entry for entry in entries if entry.get('source_node')!=f'building-{index:03}']
    if index==386:
        entries.append({'source_node':f'building-{index:03}', 'mask_indices':[195], 'reviewed':True,
                        'review_reason':'Native mask195 visually matches the complete south bridge silhouette.'})
    else:
        for obj in additions:
            component=obj['projection_component']
            if not component.startswith('rail '):continue
            mask=333 if index==226 else (177 if component.startswith('rail 1 ') else 176)
            entries.append({'source_node':f'building-{index:03}', 'projection_component':component,
                            'mask_indices':[mask], 'reviewed':True,
                            'review_reason':'Native railing silhouette is restricted to its explicit timber component; it must never project onto deck or trestle receivers.'})
    masks_path.write_text(json.dumps(masks,indent=2)+'\n')
    original['bridge_recipe']=TAG
    bpy.context.view_layer.update()
    counts={'visible_rail_posts':sum(len(r[2]) for r in rails),'rail_caps':len(rails),'ground_returns':sum(r[3] for r in rails)}
    report={'recipe':TAG,'asset_id':config['asset_id'],'source_node':f'building-{index:03}',
            'native_level_sha256':hashlib.sha256(native_path.read_bytes()).hexdigest(),
            'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'native_obstacle':level['sight_obstacles'][index], 'repeated_elements':counts,
            'added_components':[o.name for o in additions], 'projection_status':'STALE',
            'source_supported':'Native deck upper corners retained. Rail post counts inspected on source crop; ramp ground returns and open space below deck are visible.',
            'inference':'Timber sections 2.5-4 scene units, deck thickness 7 game-height units, rail height 27 game pixels; depth and hidden reverse faces inferred.',
            'limitations':(['The winding west bridge middle handrail and deep tower supports remain incomplete; only two unobscured landing rails modeled.'] if index==226 else [])+['Post spacing approximates measured source spacing; fixed-camera projection requires visual approval.','Underwater support footings are inferred and remain unknown gray.'],
            'status':'refinement in progress'}
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection/bridge-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace',type=Path)
    parser.add_argument('--native-level',type=Path,default=Path('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json'))
    parser.add_argument('--render',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    workspace=args.workspace.resolve()
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise RuntimeError('Open the worker model.blend')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate,modified
    validate(workspace);report=refine(workspace,args.native_level);validate(workspace)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    if args.render:modified(workspace)
    print(json.dumps(report))

if __name__=='__main__':main()
