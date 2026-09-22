"""Restore source-measured terrace footline without filling its upper overhangs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor').is_dir())
WORK=ROOT/'level-editor/work/nottingham-refinement'
SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))
TAG='nottingham_market_source_footline_v1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def geometry(obj):
    return {'vertices':[list(v.co) for v in obj.data.vertices],
            'faces':[list(f.vertices) for f in obj.data.polygons],
            'matrix':[list(r) for r in obj.matrix_world]}

def snapshot(objects):return {o.name:geometry(o) for o in objects}


def depth_samples():
    vertices=[];faces=[];owners=[]
    for obj in bpy.data.collections['nottingham Working'].all_objects:
        if obj.type!='MESH' or obj.hide_render:continue
        offset=len(vertices);vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            faces.append(tuple(offset+i for i in tri.vertices));owners.append(obj.get('source_node',obj.name))
    tree=BVHTree.FromPolygons(vertices,faces,all_triangles=True)
    toward=Vector((0,-COS,SIN));depth=max(p.dot(toward) for p in vertices)+10
    samples=[]
    for y in range(1450,1671,2):
        for x in range(1490,2041,2):
            point=Vector((x,-y/SIN,0));hit,normal,index,d=tree.ray_cast(point+toward*(depth-point.dot(toward)),-toward)
            owner=owners[index] if index is not None else None
            if owner in {f'building-{i:03}' for i in range(23)}:
                samples.append({'xy':[x,y],'first_hit':owner,'world':list(hit),'height_native':hit.z*COS})
    return samples


def refine():
    objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH']
    target=next(o for o in objects if o.get('source_node')=='building-012')
    if TAG in target:return json.loads(target[TAG])
    before=snapshot([o for o in objects if o!=target])
    old=geometry(target)
    source=WORK/'baseline/nottingham.rhp.json';native=json.loads(source.read_text())['sight_obstacles'][12]['points'];count=len(native)
    points=[Vector((p['x'],-p['y']/SIN,p[key]/COS)) for key in ['z_bottom','z_top'] for p in native]
    faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    inverse=target.matrix_world.inverted();mesh=bpy.data.meshes.new('Market terrace / measured continuous masonry')
    mesh.from_pydata([inverse@p for p in points],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
    defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free();uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p=target.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(p.x/2304,1-(-p.y*SIN-p.z*COS)/3520)
    for material in target.data.materials:mesh.materials.append(material)
    target.data=mesh
    if before!=snapshot([o for o in objects if o!=target]):raise ValueError('Outside base012 geometry changed')
    report={'status':'refined-source-footline','source_node':'building-012','source_native_sha256':sha(source),
            'source_footprint':[[p['x'],p['y']] for p in native],
            'changes':['Removed the four added ground-to-roof-footprint prisms that covered courtyard dirt and hid barrel005.','Rebuilt the continuous stepped masonry base on the fourteen original source-supported footprint anchors.','Preserved every other terrace part, roof contact repair, the red/right green supporting facade and the open left portico.'],
            'inference':['Concealed rear and underside remain closed structural continuations.','Upper-story overhangs are retained instead of extending their entire roof footprint to ground.'],
            'before_vertices':len(old['vertices']),'after_vertices':len(mesh.vertices),'after_faces':len(mesh.polygons),
            'topology':defects,'outside_objects_preserved':len(before),'transforms_preserved':True,'approval':'pending'}
    target[TAG]=json.dumps(report,sort_keys=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--tooling-dir',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    from render_slots import acquire
    acquire();tooling=select_tooling(args.tooling_dir)
    from refinement_workspace import modified
    w=args.workspace.resolve();archive=w/'front-geometry-reference'/sha(w/'model.blend')[:12];archive.mkdir(parents=True,exist_ok=False)
    for name in ['model.blend','candidate.json','review.md','source-masks.json','projection-correction.json','recipe.py']:
        if (w/name).is_file():shutil.copy2(w/name,archive/name)
    shutil.copytree(w/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes['nottingham Refinement']
    first=depth_samples();report=refine();once=snapshot([o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH']);refine()
    if once!=snapshot([o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH']):raise ValueError('Non-idempotent footline recipe')
    bpy.context.view_layer.update();second=depth_samples()
    before_barrel=sum(s['first_hit']=='building-005' for s in first);after_barrel=sum(s['first_hit']=='building-005' for s in second)
    if not after_barrel>before_barrel:raise ValueError('Barrel remains hidden after footline repair')
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
    validation=modified(w)
    report.update(idempotence='PASS',validation=validation,tooling=tooling,before_model_sha256=sha(archive/'model.blend'),model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),
                  barrel_grid_samples_before=before_barrel,barrel_grid_samples_after=after_barrel,archive=str(archive),recipe_sha256=sha(__file__))
    (w/'front-geometry-correction.json').write_text(json.dumps(report,indent=2)+'\n')
    (w/'market-front-depth-corrected.json').write_text(json.dumps({'model_sha256':sha(w/'model.blend'),'samples':second},indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','before_vertices','after_vertices','barrel_grid_samples_before','barrel_grid_samples_after','idempotence','model_sha256']}))


if __name__=='__main__':main()
