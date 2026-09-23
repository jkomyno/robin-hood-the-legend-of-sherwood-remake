"""Rebuild closed irregular castle rock masses from source crest and foot anchors."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
S=math.sin(math.radians(35));C=math.cos(math.radians(35));ASSET='nottingham-castle-west-rocks'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def snapshot(objs):return {o.name:([list(v.co)for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons],[list(r)for r in o.matrix_world])for o in objs if o.type=='MESH'}
def refine(obj):
    n=int(obj['source_node'][-3:]);vs=[];fs=[];profiles=[]
    def mass(rows):
        profiles.append(rows);start=len(vs);count=12;radial=[1,.94,1.025,.97,1.02,.95,1,.96,1.01,.97,1.025,.94]
        for row,(cx,gy,h,rx,ry) in enumerate(rows):
            for i in range(count):
                a=i*math.tau/count;factor=radial[i];x=cx+rx*factor*math.cos(a);y=gy+ry*factor*math.sin(a);vs.append(Vector((x,-y/S,h/C)))
        fs.append(tuple(start+i for i in reversed(range(count))))
        for j in range(len(rows)-1):
            for i in range(count):a=start+j*count+i;b=start+j*count+(i+1)%count;fs.append((a,b,b+count,a+count))
        fs.append(tuple(start+(len(rows)-1)*count+i for i in range(count)))
    def boulder(cx,gy,rx,ry,h):
        mass([(cx,gy,0,rx*.79,ry*.77),(cx,gy,h*.25,rx,ry),(cx-rx*.05,gy-ry*.1,h*.75,rx*.86,ry*.78),(cx-rx*.07,gy-ry*.15,h,rx*.42,ry*.4)])
    if n==478:
        boulder(126,2278,70,28,53);boulder(246,2300,103,28,43)
    elif n==479:
        boulder(34,2130,55,42,62);boulder(55,2200,61,40,61);boulder(101,2263,64,32,65)
    elif n==480:
        mass([(137,2120,0,75,33),(144,2111,37,76,30),(159,2095,65,48,24),(175,2085,77,20,5)])
    elif n==481:
        mass([(236,2090,0,60,24),(236,2080,40,64,23),(214,2080,63,34,9),(207,2077,68,16,5)])
    elif n==484:
        boulder(687,2132,88,33,57);boulder(801,2140,60,25,50)
    else:raise ValueError(n)
    inverse=obj.matrix_world.inverted();mesh=bpy.data.meshes.new(obj.name+' / closed source rock masses');mesh.from_pydata([inverse@v for v in vs],[],fs);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bad={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(bad.values()):raise ValueError(bad)
    bm.to_mesh(mesh);bm.free();uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        q=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(q.x/2304,1-(-q.y*S-q.z*C)/3520)
    for m in obj.data.materials:mesh.materials.append(m)
    obj.data=mesh
    return {'node':obj['source_node'],'profiles_x_groundY_height_radiusX_radiusY':profiles,'closed_volumes':len(profiles),'topology':bad}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['old-workspace','output','masks','tooling-dir']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);from render_slots import acquire
    acquire();tooling=select_tooling(a.tooling_dir);from refinement_workspace import prepare,modified
    old=a.old_workspace.resolve();oldsha=sha(old/'model.blend');config=json.loads((old/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));collection=bpy.data.collections[config['collection_name']];outside=[o for o in collection.all_objects if o.type=='MESH'and o.get('asset_group')!=ASSET];protected=snapshot(outside);targets=[o for o in collection.all_objects if o.type=='MESH'and o.get('asset_group')==ASSET];reports=[refine(o)for o in targets]
    if snapshot(outside)!=protected:raise ValueError('Foreign geometry changed')
    prepared=prepare(a.output,asset_id=ASSET,scene_name=config['scene_name'],collection_name=config['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=a.masks,width=config['width'],height=config['height'],context_padding=config['context_padding']);validation=modified(a.output)
    if sha(old/'model.blend')!=oldsha:raise ValueError('Previous worker changed')
    report={'status':'PASS','model_sha256':sha(a.output/'model.blend'),'modified_views_sha256':sha(a.output/'modified/views.json'),'previous_model_sha256':oldsha,'objects':reports,'tooling':tooling,'recipe_sha256':sha(__file__),'validation':validation,'inference':['Exposed crest and foot regions anchor closed irregular lobes.','Concealed rear radius and foliage-covered shoulders are compact volume continuations.','No separate upper brown cliff or neighboring masonry is invented;484 follows only the lower rockfoot.'],'prepared':prepared};(a.output/'rock-volume-correction.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',report['model_sha256'])
if __name__=='__main__':main()
