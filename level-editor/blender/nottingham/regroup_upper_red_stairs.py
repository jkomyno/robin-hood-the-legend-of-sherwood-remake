"""Preserve approved red-house geometry and add its source-measured side steps."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
from prepare_assets import preflight_source
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor').is_dir())
WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-upper-red-house'
SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def geom(obj):return {'vertices':[list(v.co) for v in obj.data.vertices],'faces':[list(p.vertices) for p in obj.data.polygons],'matrix':[list(r) for r in obj.matrix_world]}

def stairs(obj):
    p=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][167]['points']
    def point(p,z):return Vector((p['x'],-p['y']/SIN,z/COS))
    low=[point(p[i],0) for i in [3,2]];high=[point(p[i],20.401001) for i in [0,1]]
    count=5;profile=[(0,0)]
    for i in range(count):profile.extend([(i/count,(i+1)/count),((i+1)/count,(i+1)/count)])
    profile.append((1,0));vertices=[]
    for side in [0,1]:
        for t,h in profile:
            v=low[side].lerp(high[side],t);v.z=high[side].z*h;vertices.append(v)
    n=len(profile);faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    inverse=obj.matrix_world.inverted();mesh=bpy.data.meshes.new('Upper red house / five stone side steps');mesh.from_pydata([inverse@v for v in vertices],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free();uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        v=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x/2304,1-(-v.y*SIN-v.z*COS)/3520)
    for mat in obj.data.materials:mesh.materials.append(mat)
    obj.data=mesh
    return {'source_node':'building-167','treads':5,'topology':defects,'upper_native_corners':[[v['x'],v['y'],v['z_top']]for v in p[:2]],'changes':['Grouped stair167 with the red house side entrance it reaches.','Replaced the solid ramp with five closed masonry steps, preserving native footprint and upper/lower endpoints.'],'inference':['Five broad tread bands follow the source stair; hidden side and underside are closed masonry continuations.']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['tooling-dir','source-blend','catalog','review','output','approved-house']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);from render_slots import acquire
    acquire();tooling=select_tooling(a.tooling_dir);from refinement_workspace import prepare,modified
    if a.output.exists():raise FileExistsError(a.output)
    approved_sha=sha(a.approved_house);bpy.ops.wm.open_mainfile(filepath=str(a.approved_house.resolve()))
    approved={o['source_node']:geom(o) for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET}
    if set(approved)!={f'building-{i:03}' for i in range(144,150)}:raise ValueError('Approved house canonical parts differ')
    bpy.ops.wm.open_mainfile(filepath=str(a.source_blend.resolve()));preflight_source('nottingham Refinement','nottingham Working',json.loads(a.catalog.read_text()))
    prepared=prepare(a.output,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=a.catalog,inventory_path=WORK/'inventory/inventory-v2.json',review_path=a.review,source_mask_manifest=WORK/'mask-review/source-masks-v11-baseline.json',width=256,height=320,context_padding=36)
    objects={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET}
    if set(objects)!=set(approved)|{'building-167'}:raise ValueError('Merged house membership differs')
    for node,data in approved.items():
        obj=objects[node]
        if max(abs(obj.matrix_world[i][j]-data['matrix'][i][j])for i in range(4)for j in range(4))>1e-5:raise ValueError('Approved house transform differs')
        mesh=bpy.data.meshes.new(obj.name+' / preserved approved geometry');mesh.from_pydata(data['vertices'],[],data['faces']);mesh.update();uv=mesh.uv_layers.new(name='Source projection')
        for loop in mesh.loops:
            v=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x/2304,1-(-v.y*SIN-v.z*COS)/3520)
        for material in obj.data.materials:mesh.materials.append(material)
        obj.data=mesh
        if geom(obj)['vertices']!=data['vertices'] or geom(obj)['faces']!=data['faces']:raise ValueError('Approved mesh geometry changed')
    report=stairs(objects['building-167']);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()/'model.blend'))
    validation=modified(a.output)
    for node,data in approved.items():
        actual=geom(objects[node])
        if actual['vertices']!=data['vertices'] or actual['faces']!=data['faces']:raise ValueError('Projection changed approved geometry')
    if sha(a.approved_house)!=approved_sha:raise ValueError('Approved house worker changed')
    report.update(status='PASS',validation=validation,approved_house=str(a.approved_house.resolve()),approved_house_sha256=approved_sha,approved_house_geometry_preserved=list(approved),tooling=tooling,prepared=prepared,model_sha256=sha(a.output/'model.blend'),modified_views_sha256=sha(a.output/'modified/views.json'),recipe_sha256=sha(__file__))
    (a.output/'stair-grouping-correction.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS merged house and side stairs')
if __name__=='__main__':main()
