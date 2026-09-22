"""Source-measured timber enclosure and visible stone infill for receiver073."""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from props import signature
VERSION='leicester-east-gate-v2'
SINE,COSINE=math.sin(math.radians(35)),math.cos(math.radians(35))


def refine(obj):
    matrix=obj.matrix_world.copy();before=signature(obj);vertices=[];faces=[]
    def world(x,y,z):return Vector((x,-y/SINE,z/COSINE))
    def beam(a,b,width,depth):
        axis=(b-a).normalized();reference=Vector((0,0,1)) if abs(axis.z)<.9 else Vector((1,0,0))
        side=axis.cross(reference).normalized()*width/2;up=axis.cross(side).normalized()*depth/2
        start=len(vertices);vertices.extend(p+s*side+t*up for p in (a,b) for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)])
        faces.extend(tuple(start+i for i in f) for f in [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    # Independent image measurements: crop origin3089,1032 at10x.
    # Ground depths are inferred; projected rail/post endpoints are measured.
    left=world(3093.3,1087,0);right=world(3119.7,1099,0)
    beam(left,left+Vector((0,0,30.2/COSINE)),3,3)
    beam(right,world(3122.3,1099,26.6),3,3)
    rails=[((3093.6,1066.3),(3122.3,1076.4)),
           ((3093.9,1072.5),(3121.2,1080.9)),
           ((3094.0,1078.7),(3119.7,1086.6))]
    for (lx,ly),(rx,ry) in rails:
        beam(world(lx,1087,1087-ly),world(rx,1099,1099-ry),2.2,2.8)
    beam(left+Vector((0,0,1.2/COSINE)),right+Vector((0,0,2.4/COSINE)),5,3)
    rear=world(3124.5,1062.7,0)
    for i in range(12):
        t=(i+.5)/12;point=left.lerp(rear,t)
        top=30.2*(1-t)+28.5*t;bottom=21.1*(1-t)+10.5*t
        beam(point+Vector((0,0,bottom/COSINE)),point+Vector((0,0,top/COSINE)),3.0,2.3)
    for a,b in [(30.2,28.5),(21.1,10.5)]:beam(left+Vector((0,0,a/COSINE)),rear+Vector((0,0,b/COSINE)),3,3)
    beam(rear+Vector((0,0,10.5/COSINE)),rear+Vector((0,0,28.5/COSINE)),3,3)
    # Six pale source clusters are represented by low closed polyhedra. The
    # camera-ray depth is a hypothesis, not six proven disconnected stones.
    stones=[(3107,1064,5,4),(3117,1058,5,4),(3125,1052,5,4),(3122,1068,5,5),(3113,1075,5,5),(3102,1075,4,4)]
    for x,source_y,rx,rz in stones:
        center=world(x,source_y+rz*COSINE,rz*COSINE);start=len(vertices);n=8
        for z,scale in [(-rz,.58),(0,1),(rz,.52)]:
            for i in range(n):
                a=math.tau*i/n;vertices.append(center+Vector((rx*scale*math.cos(a),rx*scale*math.sin(a),z)))
        faces.append(tuple(start+i for i in reversed(range(n))))
        for layer in range(2):
            for i in range(n):j=(i+1)%n;faces.append((start+layer*n+i,start+layer*n+j,start+(layer+1)*n+j,start+(layer+1)*n+i))
        faces.append(tuple(start+2*n+i for i in range(n)))
    mesh=bpy.data.meshes.new(obj.name+' open timber enclosure');inverse=matrix.inverted()
    mesh.from_pydata([inverse@v for v in vertices],[],faces);mesh.uv_layers.new(name='UVMap')
    for material in obj.data.materials:mesh.materials.append(material)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology={'vertices':len(bm.verts),'faces':len(bm.faces),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if topology['nonmanifold_edges'] or topology['degenerate_faces']:raise ValueError(topology)
    bm.to_mesh(mesh);bm.free();mesh.update();old=obj.data;obj.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    obj['leicester_geometry_recipe']=VERSION
    if obj.matrix_world!=matrix:raise ValueError('Transform drift')
    return {'source_node':obj['source_node'],'before_geometry_sha256':before,'after_geometry_sha256':signature(obj),'topology':topology,'world_transform_drift':0}


def run(workspace):
    workspace=Path(workspace).resolve();config=json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve()!=workspace/'model.blend':raise ValueError('Open isolated model')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from refinement_workspace import validate
    validate(workspace)
    targets=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
    if len(targets)!=1 or targets[0].get('source_node')!='building-073':raise ValueError('Only gate073 is supported')
    obj=targets[0];record=refine(obj);first=signature(obj);refine(obj)
    if signature(obj)!=first:raise ValueError('Non-idempotent gate')
    report={'recipe':VERSION,'asset_id':config['asset_id'],'objects':[record],'idempotence':'PASS','limitations':[
        'Three front rails and lower sill follow the visible timber enclosure; receiver073 also includes the rising side panel and pale stone clusters.',
        'Twelve side boards and six stone clusters approximate soft artwork; exact counts, concealed depths and rear faces are not source-confirmed.',
        'The enclosure is clipped at the map edge. Right post and off-map closure remain inferred; no rear closure is invented.',
        'Native mask118 owns this composite enclosure; foreground hay belongs separately to070/071. Timber and stones require visual alignment review.'],
        'approval_status':'refinement-in-progress','texture_generation':'not-started'}
    validate(workspace);(workspace/'inspection').mkdir(exist_ok=True);(workspace/'inspection/gate-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspace');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(run(args.workspace)))
