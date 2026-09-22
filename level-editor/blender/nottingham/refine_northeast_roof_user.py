"""Source-fitted rounded roof and measured metal finial for the northeast tower."""
import copy,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from refine_round_house_curvature import samples
from refine_town_shells import replace
WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-northeast-round-tower';SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35));CX=2147.;CY=510.82


def write_mesh(obj,verts,faces):
    matrix=obj.matrix_world.copy();mesh=bpy.data.meshes.new(obj.name+' / source-fitted roof');inverse=matrix.inverted();mesh.from_pydata([inverse@Vector((x,-y/SIN,z/COS))for x,y,z in verts],[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-7 for f in bm.faces)
    if bad or deg:raise ValueError((obj.name,bad,deg))
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
    for m in obj.data.materials:mesh.materials.append(m)
    obj.data=mesh;assert obj.matrix_world==matrix
    return {'source_node':obj['source_node'],'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':bad,'degenerate_faces':deg,'transform_drift':0}


def append(target,vertices,faces):
    v,f=target;offset=len(v);v.extend(vertices);f.extend(tuple(offset+i for i in face)for face in faces)


def lathe(profile,count=40):
    vertices=[(CX+r*math.cos(2*math.pi*i/count),CY+r*SIN*math.sin(2*math.pi*i/count),z)for r,z in profile for i in range(count)]
    faces=[tuple(reversed(range(count))),tuple(range((len(profile)-1)*count,len(profile)*count))]
    for j in range(len(profile)-1):
        for i in range(count):k=(i+1)%count;faces.append((j*count+i,j*count+k,(j+1)*count+k,(j+1)*count+i))
    return vertices,faces


def roof_sector(a,b,params):
    rx,ry,top,power=[params[k]for k in ['radius_x','radius_native_y','top_height','power']];radii=[.18+.82*i/16 for i in range(17)];vertices=[]
    for dz in [0,-2.2]:
        for r in radii:
            z=195.358+(top-195.358)*((1-r)/.82)**power+dz
            vertices.extend((CX+rx*r*math.cos(t),CY+ry*r*math.sin(t),z)for t in [a,b])
    n=len(radii)*2;faces=[]
    for j in range(len(radii)-1):
        x=j*2;faces.extend([(x,x+1,x+3,x+2),(n+x+2,n+x+3,n+x+1,n+x),(x+2,x,n+x,n+x+2),(x+1,x+3,n+x+3,n+x+1)])
    faces.extend([(0,1,n+1,n),(n-2,n*2-2,n*2-1,n-1)])
    return vertices,faces


def refine():
    fit_path=WORK/'fortifications-audit/north-user-revision/tower-roof-fit.json';fit=json.loads(fit_path.read_text());params=fit['parameters'];native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'];body=copy.deepcopy(native[172]['points'])
    objects={int(o['source_node'][-3:]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET}
    angles=[math.atan2((p['y']-CY)/params['radius_native_y'],(p['x']-CX)/params['radius_x'])%(2*math.pi)for p in body]
    radii=[math.hypot((p['x']-CX)/params['radius_x'],(p['y']-CY)/params['radius_native_y'])for p in body]
    shaft=[]
    for i,a in enumerate(angles):
        b=angles[(i+1)%6]
        while b<a:b+=2*math.pi
        for j in range(12):
            t=j/12;angle=a+(b-a)*t;radius=radii[i]*(1-t)+radii[(i+1)%6]*t;q=copy.deepcopy(body[i]);q.update(x=CX+params['radius_x']*radius*math.cos(angle),y=CY+params['radius_native_y']*radius*math.sin(angle));shaft.append(q)
    reports=[replace(objects[172],[shaft])]
    parts={n:([],[])for n in [173,174,175,176]};owners={0:175,1:175,2:175,3:176,4:173,5:174}
    for i,a in enumerate(angles):
        b=angles[(i+1)%6]
        while b<a:b+=2*math.pi
        count=max(1,math.ceil((b-a)/(2*math.pi/80)))
        for j in range(count):append(parts[owners[i]],*roof_sector(a+(b-a)*j/count,a+(b-a)*(j+1)/count,params))
    # Separate cap, balls and pole follow measured source landmarks. All stay
    # inside canonical roof173 so source-node ownership is unchanged.
    append(parts[173],*lathe([(13.5,254.5),(13.5,258.5),(4,267.5),(2,269)]))
    for radius,zcenter in [(7,271.82),(4.5,286.82)]:
        profile=[(max(.25,radius*math.cos(t)),zcenter+radius*COS*math.sin(t))for t in [-math.pi/2+i*math.pi/16 for i in range(17)]]
        append(parts[173],*lathe(profile))
    append(parts[173],*lathe([(.8,264),(.8,317)]))
    flag=[(2147,CY-.4,308),(2158,CY-.4,307),(2163,CY-.4,297),(2147,CY-.4,298)];flag+= [(x,CY+.4,z)for x,y,z in flag]
    append(parts[173],flag,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    reports.extend(write_mesh(objects[n],*parts[n])for n in parts)
    return {'asset_id':ASSET,'status':'refined','objects':reports,'changes':['Rounded the shaft between its six measured anchors using72 perimeter samples and polar arcs, so the long concealed rear chord also becomes curved.','Replaced the tall faceted cone with a source-fitted curved tile roof, sampled with80 angular intervals and17 radial levels.','Separated the measured metal cap, two finial balls, pole and small vane from the tiled roof profile; all remain within canonical roof ownership.'],'inference':['Roof radial symmetry and unseen rear continuation are inferred from the isolated native roof outline; fit mean boundary error0.658 source pixels.','Concealed finial depth uses circular metal sections and a thin vane; no generated texture is used.'],'fit_evidence':str(fit_path),'fit_sha256':hashlib.sha256(fit_path.read_bytes()).hexdigest(),'finial_landmarks_source':{'pole_tip':[2147,194],'small_ball_center':[2147,224],'large_ball_center':[2147,239],'cap_base':[2147,259]},'world_transform_drift':0}


def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling();acquire()
    import refinement_review
    from refinement_workspace import prepare,modified
    old=WORK/'round-1/assets'/ASSET;out=WORK/'round-10/assets'/ASSET
    if not out.exists():
        bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
        oldfit=refinement_review.fit_camera
        def expected(*args,**kwargs):
            kwargs['points']=list(kwargs['points'])+[Vector((CX,-CY/SIN,317/COS))];kwargs['padding']=1.08
            return oldfit(*args,**kwargs)
        refinement_review.fit_camera=expected
        prepare(out,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=WORK/'grouped/nottingham-grouped-v5.evidence/catalog.json',inventory_path=WORK/'grouped/nottingham-grouped-v5.evidence/inventory.json',review_path=WORK/'grouped/nottingham-grouped-v5.evidence/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=256,height=320,context_padding=48)
        refinement_review.fit_camera=oldfit
    else:bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
    report=refine()
    def sig():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}
    first=sig();refine();assert sig()==first;report['idempotence']='PASS';(out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'recipe.py');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));print(modified(out),flush=True)
if __name__=='__main__':main()
