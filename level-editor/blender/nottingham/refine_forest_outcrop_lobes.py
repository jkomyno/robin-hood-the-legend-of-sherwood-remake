"""Fit closed rock lobes to the isolated forest outcrop source silhouette."""
import json,math,sys,shutil
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-forest-rock-outcrop';SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))
sys.path.insert(0,str(Path(__file__).resolve().parent))

def simplify(points,tolerance=1.8):
    if len(points)<3:return points
    a,b=Vector(points[0]),Vector(points[-1]);delta=b-a
    distances=[((Vector(p)-a)-delta*max(0,min(1,(Vector(p)-a).dot(delta)/max(delta.length_squared,1e-10)))).length for p in points]
    i=max(range(len(points)),key=lambda i:distances[i])
    if distances[i]<=tolerance:return [points[0],points[-1]]
    return simplify(points[:i+1],tolerance)[:-1]+simplify(points[i:],tolerance)

def clipped_outline(region):
    from PIL import Image,ImageDraw
    im=Image.open(WORK/'mask-review/inventory-v6/000501.png').convert('L');clip=Image.new('1',im.size);ImageDraw.Draw(clip).polygon([(x-1007,y-85)for x,y in region],fill=1)
    pixels={(x,y)for y in range(im.height)for x in range(im.width)if im.getpixel((x,y))>127 and clip.getpixel((x,y))};edges={}
    for x,y in pixels:
        for neighbor,a,b in [((x,y-1),(x,y),(x+1,y)),((x+1,y),(x+1,y),(x+1,y+1)),((x,y+1),(x+1,y+1),(x,y+1)),((x-1,y),(x,y+1),(x,y))]:
            if neighbor not in pixels:edges.setdefault(a,[]).append(b)
    loops=[]
    while edges:
        start=next(iter(edges));p=start;loop=[]
        while True:
            loop.append(p);q=edges[p].pop()
            if not edges[p]:del edges[p]
            p=q
            if p==start:break
        loops.append(loop)
    outline=max(loops,key=len);middle=len(outline)//2;outline=simplify(outline[:middle+1])[:-1]+simplify(outline[middle:]+[outline[0]])[:-1]
    return [(x+1007,y+85)for x,y in outline]

def outlines():
    # Native boundaries constrain outer edges; measured stone seams constrain
    # overlap between the cap, supporting mass, upright and foreground lobes.
    sections=[
      ('upper cap',40,[(1000,80),(1110,80),(1107,124),(1083,134),(1045,142),(1010,139)]),
      ('middle supporting rock',18,[(1015,126),(1045,139),(1087,128),(1118,129),(1118,161),(1100,174),(1060,181),(1010,169)]),
      ('lower left support',0,[(1014,163),(1075,165),(1095,176),(1080,196),(1065,209),(1030,207),(1000,200),(1000,179)]),
      ('right upright rock',17,[(1104,116),(1155,116),(1155,176),(1134,179),(1107,168),(1096,145)]),
      ('front right rock',0,[(1080,162),(1110,154),(1155,154),(1155,222),(1120,230),(1087,235),(1060,216),(1060,195),(1068,180)]),
      ('lower toe rock',0,[(1050,216),(1082,208),(1115,220),(1115,250),(1050,250)])]
    return [(name,elevation,clipped_outline(region))for name,elevation,region in sections]

def lobe(outline,elevation):
    n=len(outline);cx=sum(x for x,y in outline)/n;cy=sum(y for x,y in outline)/n;bottom=max(y for x,y in outline);width=max(x for x,y in outline)-min(x for x,y in outline);height=bottom-min(y for x,y in outline);depth=.45*min(width,height);d0=-bottom*COS/SIN-elevation/(COS*SIN)
    def point(u,v,d):return Vector((u,-v*SIN+d*COS,-v*COS-d*SIN))
    vertices=[point(u,v,d0)for u,v in outline];faces=[]
    for side in [-1,1]:
        start=len(vertices)
        for scale,bulge in [(.68,.72),(.32,.97)]:
            for u,v in outline:
                x=cx+(u-cx)*scale;y=cy+(v-cy)*scale;d=d0+side*depth*bulge
                # Concealed lower shoulders stop at the ground plane without
                # changing the measured source projection.
                d=min(d,-y*COS/SIN)
                vertices.append(point(x,y,d))
        center=len(vertices);d=min(d0+side*depth,-cy*COS/SIN);vertices.append(point(cx,cy,d))
        for j in range(n):
            k=(j+1)%n;faces.extend([(j,k,start+k,start+j),(start+j,start+k,start+n+k,start+n+j),(start+n+j,start+n+k,center)])
    return vertices,faces

def refine():
    obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET and o.get('source_node')=='building-546');matrix=obj.matrix_world.copy();vertices=[];faces=[];sections=outlines()
    for name,elevation,outline in sections:
        v,f=lobe(outline,elevation);offset=len(vertices);vertices.extend(v);faces.extend(tuple(offset+i for i in face)for face in f)
    mesh=bpy.data.meshes.new('Forest outcrop / six source-fitted rock lobes');inverse=matrix.inverted();mesh.from_pydata([inverse@p for p in vertices],[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-7 for f in bm.faces);assert bad==0 and deg==0;bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
    for m in obj.data.materials:mesh.materials.append(m)
    obj.data=mesh;assert obj.matrix_world==matrix
    mesh.calc_loop_triangles();v=[matrix@p.co for p in mesh.vertices]
    return {'asset_id':ASSET,'status':'refined','source_node':'building-546','vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':bad,'degenerate_faces':deg,'world_transform_drift':0,'source_mask':501,'source_sections':[{'name':n,'base_elevation_native':e,'outline':p}for n,e,p in sections],'changes':['Replaced the continuous shelf proxy with six closed lobes: upper cap, middle and lower left supports, right upright, front rock and lower toe.','Measured each lobe silhouette from native501 pixels and visible source seams; canonical546 owns every part.','Rounded front and concealed rear shoulders into compact rock volumes, removing rectangular sides and flat shelves.'],'inference':['Source seams divide overlapping rock lobes; source-hidden rear curvature and thickness are inferred.','Base elevations of the cap and upright rock infer their support by neighboring lobes; all meshes remain above ground.','Native501 includes integrated vegetation; no separately owned tree or ground texture is added.'],'actual_mesh_projection':{'vertices':[[p.x,-p.y*SIN-p.z*COS]for p in v],'faces':[list(f.vertices)for f in mesh.loop_triangles]}}

def signature():
    return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}

def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    tooling=select_tooling(WORK/'tooling/94116d984f92dbae');acquire()
    import refinement_review
    from refinement_workspace import prepare,modified
    old=WORK/'round-12/assets'/ASSET;out=WORK/'round-13/assets'/ASSET
    if not out.exists():
        bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));planned=[p for _,e,outline in outlines()for p in lobe(outline,e)[0]];fit=refinement_review.fit_camera
        def fitted(*args,**kwargs):kwargs['points']=list(kwargs['points'])+planned;kwargs['padding']=1.12;return fit(*args,**kwargs)
        refinement_review.fit_camera=fitted
        prepare(out,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=WORK/'grouped/nottingham-grouped-v7.evidence/catalog.json',inventory_path=WORK/'grouped/nottingham-grouped-v7.evidence/inventory.json',review_path=WORK/'grouped/nottingham-grouped-v7.evidence/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=320,height=320,context_padding=30)
        refinement_review.fit_camera=fit
    else:bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
    outside={k:v for k,v in signature().items()if bpy.data.objects[k].get('asset_group')!=ASSET};report=refine();assert outside=={k:v for k,v in signature().items()if bpy.data.objects[k].get('asset_group')!=ASSET};first=signature();refine();assert first==signature();report.update(idempotence='PASS',protected_geometry='PASS',tooling=tooling['snapshot_id']);(out/'inspection').mkdir(exist_ok=True);(out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'recipe.py');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));print(modified(out),flush=True)
if __name__=='__main__':main()
