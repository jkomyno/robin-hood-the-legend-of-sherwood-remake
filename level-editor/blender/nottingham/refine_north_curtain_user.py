"""Build source-pixel-fitted northern battlements with unchanged canonical ownership."""
import copy,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/blender/nottingham/freeze_tooling.py').is_file())
sys.path.insert(0,str(ROOT/'level-editor/blender/nottingham'))
from refine_fortifications import north_wall_geometry
WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-north-curtain-wall';SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))

def projected(objects):
    data={}
    for obj in objects:
        obj.data.calc_loop_triangles();v=[obj.matrix_world@p.co for p in obj.data.vertices]
        data[obj['source_node']]={'vertices':[[p.x,-p.y*SIN-p.z*COS]for p in v],'faces':[list(f.vertices)for f in obj.data.loop_triangles]}
    return data

def refine():
    fit_path=WORK/'fortifications-audit/north-user-revision/final-fit.json';fit=json.loads(fit_path.read_text());native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    objs={int(o['source_node'][-3:]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET};generated={};reports=[]
    runs={r['name']:r for r in fit['runs']};notches=[]
    for name,lo,hi in [('west',1530,1806),('central-projecting-turret',1806,1904),('east',1904,2110)]:
        notches.extend([max(lo,a),min(hi,b)]for a,b in runs[name]['notches']if lo<a<hi)
    for n,pairs,gaps in [(178,[(7,6),(8,5),(9,4),(10,3),(11,2),(12,1),(13,0)],notches),(177,[(2,3),(1,0)],runs['east-continuation']['notches'])]:
        points=[{**q,'z_top':fit['height']}for q in native[n]['points']]
        if n==178:
            # The source shows a rounded projecting-turret return, not the
            # abrupt two-edge bend of its coarse obstacle footprint.
            sections=[(copy.deepcopy(points[a]),copy.deepcopy(points[b]))for a,b in pairs[:4]]
            for x,source_y in [(1885,244),(1890,246),(1895,250),(1899,254),(1903,260),(1904,269)]:
                seg=(10,3,11,2)if x<=points[11]['x']else(11,2,12,1)
                a,b,c,d=[points[i]for i in seg];t=max(0,min(1,(x-a['x'])/(c['x']-a['x'])));dx=(b['x']-a['x'])*(1-t)+(d['x']-c['x'])*t;dy=(b['y']-a['y'])*(1-t)+(d['y']-c['y'])*t
                back=copy.deepcopy(a);back.update(x=x,y=source_y+fit['height']+.5);front=copy.deepcopy(back);front.update(x=x+dx,y=back['y']+dy);sections.append((back,front))
            sections.append((copy.deepcopy(points[13]),copy.deepcopy(points[0])))
            points=[q for section in sections for q in section];pairs=[(i*2,i*2+1)for i in range(len(sections))]
        verts,faces=north_wall_geometry(points,pairs,gaps,notch_depth=fit['notch_depth']);obj=objs[n];matrix=obj.matrix_world.copy();mesh=bpy.data.meshes.new(obj.name+' / pixel-fitted battlements');inverse=matrix.inverted();mesh.from_pydata([inverse@Vector((x,-y/SIN,z/COS))for x,y,z in verts],[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);assert bad==0;bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
        for material in obj.data.materials:mesh.materials.append(material)
        obj.data=mesh;assert obj.matrix_world==matrix;reports.append({'source_node':obj['source_node'],'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'nonmanifold_edges':bad,'transform_drift':0})
    return {'asset_id':ASSET,'status':'refined','objects':reports,'changes':['Corrected battlement phase by measuring notch positions on the source-visible back edge, rather than the displaced front edge.','Fitted individual gap corners, shared parapet height and10.6-source-unit notch depth to native mask115; west, central turret, east and continuation runs retain independent measured phases.','Aligned the rounded central return with six measured source silhouette anchors, removing the previous abrupt corner mismatch.'],'inference':['Six source-pixel anchors round the projecting-turret return; concealed thickness interpolates the adjacent native cross-sections.','End continuation outside the2304-pixel source width remains inferred.'],'fit_sha256':hashlib.sha256(fit_path.read_bytes()).hexdigest(),'fit_evidence':str(fit_path),'world_transform_drift':0,'actual_mesh_projection':projected([objs[177],objs[178]])}

def main():
    from freeze_tooling import select_tooling
    from render_slots import acquire
    select_tooling();acquire()
    from refinement_workspace import modified
    out=WORK/'round-1/assets'/ASSET;archive=out/'inspection/pre-user-battlements'
    if not archive.exists():
        archive.mkdir()
        for name in ['model.blend','candidate.json','review.md']:
            if(out/name).exists():shutil.copy2(out/name,archive/name)
        shutil.copytree(out/'modified',archive/'modified')
    bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'));objs=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET and o.get('source_node')in['building-177','building-178']]
    if not(archive/'actual-mesh-projection.json').exists():(archive/'actual-mesh-projection.json').write_text(json.dumps(projected(objs))+'\n')
    report=refine()
    def sig():return {o.name:([tuple(v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'}
    first=sig();refine();assert sig()==first;report['idempotence']='PASS';(out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'recipe.py');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));print(modified(out),flush=True)
if __name__=='__main__':main()
