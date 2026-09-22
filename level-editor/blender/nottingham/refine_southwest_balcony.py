"""Restore the source-visible timber boundary around the southwest house balcony."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
ASSET='nottingham-southwest-wall-house'
TAG='nottingham_southwest_balcony_boundary_v1'
SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))


def mesh_hash(obj):
    return hashlib.sha256(json.dumps({'vertices':[list(v.co) for v in obj.data.vertices],
        'faces':[list(p.vertices) for p in obj.data.polygons]},sort_keys=True).encode()).hexdigest()


def refine():
    import bpy,bmesh
    from mathutils import Vector
    targets=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==ASSET and o.get('source_node')=='building-108' and not o.hide_render]
    if len(targets)!=1:raise ValueError('Expected exactly one canonical balcony receiver')
    obj=targets[0]
    if obj.get(TAG):return json.loads(obj[TAG])
    raw=json.loads((ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles'][108]['points']
    floor=[Vector((p['x'],-p['y']/SIN,p['z_top']/COS)) for p in raw]
    # Source camera annotations locate the front cap near (1086,2015) and
    # (1126,2001), 27 native vertical pixels above the existing balcony deck.
    height=27/COS;lower=4.0/COS;upper=23.5/COS;thickness=2.0
    vertices=[];faces=[]
    def solid_box(a,b,width,depth):
        axis=(b-a).normalized();u=axis.cross(Vector((0,0,1)))
        if u.length<.001:u=Vector((1,0,0))
        u.normalize();v=axis.cross(u).normalized();start=len(vertices)
        offsets=[u*x*width/2+v*y*depth/2 for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        vertices.extend(p+o for p in (a,b) for o in offsets)
        faces.extend(tuple(start+i for i in f) for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)))
    def panel(a,b,bays):
        axis=b-a;axis.z=0;length=axis.length;axis.normalize();inward=Vector((-axis.y,axis.x,0))
        # Grid-cell boundary extraction builds a watertight perforated panel;
        # internal coplanar faces are omitted instead of piling boxes together.
        gap=1.0;cuts=[0.0]
        for j in range(1,bays):cuts.extend([length*j/bays-gap/2,length*j/bays+gap/2])
        cuts.append(length);levels=[0,lower,upper,height];occupied={(i,j) for i in range(len(cuts)-1) for j in range(3) if not(i%2 and j==1)}
        lookup={}
        def vertex(i,j,k):
            key=(i,j,k)
            if key not in lookup:
                lookup[key]=len(vertices);vertices.append(a+axis*cuts[i]+Vector((0,0,levels[j]))+inward*(k-.5)*thickness)
            return lookup[key]
        for i,j in occupied:
            faces.extend([(vertex(i,j,0),vertex(i,j+1,0),vertex(i+1,j+1,0),vertex(i+1,j,0)),
                          (vertex(i,j,1),vertex(i+1,j,1),vertex(i+1,j+1,1),vertex(i,j+1,1))])
            for neighbour,quad in [((i-1,j),((i,j,0),(i,j,1),(i,j+1,1),(i,j+1,0))),
                                   ((i+1,j),((i+1,j,0),(i+1,j+1,0),(i+1,j+1,1),(i+1,j,1))),
                                   ((i,j-1),((i,j,0),(i+1,j,0),(i+1,j,1),(i,j,1))),
                                   ((i,j+1),((i,j+1,0),(i,j+1,1),(i+1,j+1,1),(i+1,j+1,0)))]:
                if neighbour not in occupied:faces.append(tuple(vertex(*x) for x in quad))
    # Front five broad timber bays are separated by four narrow source gaps.
    panel(floor[2],floor[1],5)
    # The visible left return has framing and an oblique timber brace. The
    # concealed right return repeats its enclosing frame without invented gaps.
    for back,front in ((floor[3],floor[2]),(floor[0],floor[1])):
        for p in (back,front):solid_box(p,p+Vector((0,0,height)),2.4,2.4)
        solid_box(back+Vector((0,0,lower/2)),front+Vector((0,0,lower/2)),2,lower)
        solid_box(back+Vector((0,0,(upper+height)/2)),front+Vector((0,0,(upper+height)/2)),2,height-upper)
    solid_box(floor[3]+Vector((0,0,lower)),floor[2]+Vector((0,0,upper)),2.4,2.2)
    mesh=bpy.data.meshes.new('Southwest balcony timber boundary');mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
    defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free()
    # Append to the existing canonical receiver: source ownership remains unique.
    inverse=obj.matrix_world.inverted();base=len(obj.data.vertices)
    combined=[v.co.copy() for v in obj.data.vertices]+[inverse@v.co for v in mesh.vertices]
    combined_faces=[list(f.vertices) for f in obj.data.polygons]+[[base+i for i in f.vertices] for f in mesh.polygons]
    out=bpy.data.meshes.new('Balcony deck and measured timber boundary');out.from_pydata(combined,[],combined_faces);out.update()
    for material in obj.data.materials:out.materials.append(material)
    out.uv_layers.new(name='Source projection')
    for loop in out.loops:
        p=obj.matrix_world@out.vertices[loop.vertex_index].co
        out.uv_layers.active.data[loop.index].uv=(p.x/2304,1-(-p.y*SIN-p.z*COS)/3520)
    before=mesh_hash(obj);obj.data=out
    report={'version':1,'asset_id':ASSET,'source_node':'building-108','status':'refined',
        'front_board_bays':5,'front_narrow_gaps':4,'return_frames':2,'visible_return_braces':1,
        'boundary_height_world':height,'boundary_thickness_world':thickness,'new_boundary_validation':defects,
        'preserved_deck_vertices':base,'new_vertices':len(mesh.vertices),'transform_drift':0,
        'before_geometry_sha256':before,'after_geometry_sha256':mesh_hash(obj),
        'source_cap_endpoints':[[1085.664,2014.86279],[1126.261,2000.63299]],
        'source_cap_world_endpoints':[list(floor[2]+Vector((0,0,height))),list(floor[1]+Vector((0,0,height)))],
        'changes':['Added U-shaped timber balcony boundary to canonical108: five broad front bays, four narrow vertical gaps, continuous cap/base framing, two return frames and one visible left diagonal brace.'],
        'inference':['Boundary thickness and concealed right return frame are structural inference.','Source endpoint interpretation is accurate to roughly 2–3 native pixels; the small source does not establish joinery or an interior beyond the doorway.','New timber pieces are individually closed solids with intentional contact at their joints; the pre-existing balcony deck mesh is retained.']}
    obj[TAG]=json.dumps(report);return report


def main():
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    select_tooling(ROOT/'level-editor/work/nottingham-refinement/tooling/315d227e98d52a78')
    import bpy
    from refinement_workspace import modified,initialize_working_masks
    workspace=ROOT/'level-editor/work/nottingham-refinement/round-1/assets'/ASSET
    archive=workspace/'inspection/before-balcony-boundary'
    if not archive.exists():
        archive.mkdir(parents=True)
        for name in ('model.blend','candidate.json','review.md'):shutil.copy2(workspace/name,archive/name)
        shutil.copytree(workspace/'modified',archive/'modified')
    initialize_working_masks(workspace)
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    def snapshot(exclude_balcony=False):return {o.name:(mesh_hash(o),[list(row) for row in o.matrix_world]) for o in bpy.context.scene.objects if o.type=='MESH' and not(exclude_balcony and o.get('asset_group')==ASSET and o.get('source_node')=='building-108')}
    outside=snapshot(True);report=refine()
    if outside!=snapshot(True):raise ValueError('Changed a non-balcony mesh')
    first=snapshot();refine()
    if first!=snapshot():raise ValueError('Balcony recipe is not idempotent')
    report['idempotence']='PASS';report['other_meshes_preserved']=len(outside)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    (workspace/'inspection/balcony-boundary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(modified(workspace),flush=True)


if __name__=='__main__':main()
