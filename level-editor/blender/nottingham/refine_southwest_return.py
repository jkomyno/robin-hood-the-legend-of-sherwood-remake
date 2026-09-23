"""Fit the short southern curtain return to numbered source-cap corners."""
import json,hashlib,math,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-13/assets/nottingham-southwest-curtain-wall-south'
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
# Ordered near/front cap edge. Far edges are hidden or ambiguous and retain
# native wall thickness. Native pixel uncertainty is approximately two pixels.
CORNERS=[(1020,2061,'cap-start'),(1046,2062,'cap-end'),(1046,2075,'notch-floor-start'),(1064,2075,'notch-floor-end'),(1064,2063,'cap-start'),(1091,2063,'cap-end'),(1091,2077,'notch-floor-start'),(1110,2077,'notch-floor-end'),(1110,2064,'cap-start'),(1125,2064,'cap-end')]
NOTCHES=[(1046,1064,193.2),(1091,1110,191.55)]
def evidence():
 from PIL import Image,ImageDraw
 src=R/'source-states/covered.png';box=(1000,2035,1140,2120);plain=Image.open(src).convert('RGB').crop(box).resize((1120,680),Image.Resampling.NEAREST);mark=plain.copy();d=ImageDraw.Draw(mark)
 pts=[((x-box[0])*8,(y-box[1])*8)for x,y,_ in CORNERS];d.line(pts,fill='red',width=2)
 for i,(p,corner) in enumerate(zip(pts,CORNERS)):
  x,y=p;d.ellipse((x-4,y-4,x+4,y+4),fill='red');d.text((x+5,y+(-20 if i%2==0 else 6)),str(i),fill='yellow')
 sheet=Image.new('RGB',(2240,680));sheet.paste(plain,(0,0));sheet.paste(mark,(1120,0));sheet.save(W/'return-numbered-source.png')
 write(W/'return-source-corners.json',dict(source_sha256=sha(src),crop=list(box),source_node='building-219',component='wall-219-south',run='east-facing short return',cap_edge='near/front',uncertainty_native_pixels=2,corners=[dict(index=i,x=x,y=y,role=role,visibility='measured')for i,(x,y,role)in enumerate(CORNERS)],merlons=3,notches=2,hidden_inference='Far cap and concealed wall depth retain native footprint.'))
def geometry(o):return {'vertices':[list(v.co)for v in o.data.vertices],'faces':[list(f.vertices)for f in o.data.polygons],'matrix':[list(row)for row in o.matrix_world]}
def main():
 import bpy,bmesh
 from mathutils import Vector
 sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
 acquire();from freeze_tooling import select_tooling
 select_tooling(R/'tooling/58744eeaf71a21e9');from refinement_workspace import modified
 bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));config=json.loads((W/'workspace.json').read_text());objects=list(bpy.data.collections[config['collection_name']].all_objects);obj=next(o for o in objects if o.type=='MESH' and o.get('projection_component')=='wall-219-south' and not o.hide_render);outside={o.name:geometry(o)for o in objects if o.type=='MESH' and o!=obj}
 reference=W/'return-reference';reference.mkdir(exist_ok=True)
 if not (reference/'model.blend').exists():
  for name in ['model.blend','candidate.json','partition-application.json']:shutil.copy2(W/name,reference/name)
  shutil.copytree(W/'modified',reference/'modified')
 else:
  with bpy.data.libraries.load(str(reference/'model.blend'),link=False)as(src,dst):dst.objects=[obj.name]
  prior=dst.objects[0];obj.data=prior.data.copy();bpy.data.objects.remove(prior,do_unlink=True)
 bpy.context.view_layer.objects.active=obj;obj.hide_set(False)
 for lo,hi,z in NOTCHES:
  verts=[(x,-y/S,h/C)for h in [z,240]for y in [2248,2280]for x in [lo,hi]];faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
  mesh=bpy.data.meshes.new('Temporary notch cutter');mesh.from_pydata(verts,[],faces);mesh.update();cb=bmesh.new();cb.from_mesh(mesh);bmesh.ops.recalc_face_normals(cb,faces=list(cb.faces));cb.to_mesh(mesh);cb.free();cut=bpy.data.objects.new('Temporary notch cutter',mesh);bpy.context.scene.collection.objects.link(cut)
  mod=obj.modifiers.new('Measured return gap','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
 bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)};bm.to_mesh(obj.data);bm.free();assert not any(bad.values()),bad
 assert outside=={o.name:geometry(o)for o in objects if o.type=='MESH' and o!=obj}
 evidence();native=[(float(p.x),float(-p.y*S),float(p.z*C))for p in [obj.matrix_world@v.co for v in obj.data.vertices]];matches=[]
 for i,(x,y,role)in enumerate(CORNERS):
  # Restrict correspondence to near-face vertices; nearest screen vertex alone
  # could incorrectly match a rear edge behind the cap.
  near=[p for p in native if 2267.8<=p[1]<=2269 and abs(p[0]-x)<2]
  best=min(near,key=lambda p:(p[0]-x)**2+(p[1]-p[2]-y)**2);matches.append(dict(index=i,target=[x,y],actual=[best[0],best[1]-best[2]],error_pixels=math.hypot(best[0]-x,best[1]-best[2]-y)))
 assert max(m['error_pixels']for m in matches)<2.1,matches
 from mathutils.bvhtree import BVHTree
 tree=BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],[list(p.vertices)for p in obj.data.polygons]);heights=[]
 for x,expected in [(1035,205.501),(1055,193.2),(1080,205.501),(1100,191.55),(1118,205.501)]:
  hit=tree.ray_cast(Vector((x,-2263/S,300/C)),Vector((0,0,-1)))[0];actual=hit.z*C if hit is not None else None;assert actual is not None and abs(actual-expected)<.01,(x,expected,actual);heights.append(dict(x=x,expected=expected,actual=actual))
 from PIL import Image,ImageDraw
 box=(1000,2035,1140,2120);im=Image.open(R/'source-states/covered.png').convert('RGB').crop(box).resize((1120,680),Image.Resampling.NEAREST);d=ImageDraw.Draw(im)
 def screen(p):return ((p[0]-box[0])*8,(p[1]-box[1])*8)
 actual_points=[screen(m['actual'])for m in matches];d.line(actual_points,fill='cyan',width=3)
 d.line([screen(matches[0]['actual']),screen(matches[-1]['actual'])],fill='orange',width=2)
 for m in matches:
  a=screen(m['actual']);t=screen(m['target']);d.line([a,t],fill='red',width=2);d.ellipse((t[0]-3,t[1]-3,t[0]+3,t[1]+3),fill='yellow')
 d.text((12,12),'Cyan: actual corrected mesh edge; orange: former continuous cap; yellow: measured source targets',fill='cyan');im.save(W/'return-actual-edge-overlay.png')
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(W/'model.blend'));before=geometry(obj);modified(W);assert geometry(obj)==before
 write(W/'return-corner-fit.json',dict(status='PASS',model_sha256=sha(W/'model.blend'),modified_views_sha256=sha(W/'modified/views.json'),recipe_sha256=sha(__file__),component='wall-219-south',topology=bad,outside_meshes_preserved=len(outside),source_corner_correspondence=matches,construction_check_only=True,notch_height_rays=heights,geometry_sha256=hashlib.sha256(json.dumps(geometry(obj),sort_keys=True).encode()).hexdigest(),limitations=['Near cap corner observations have approximately two-pixel uncertainty; residuals check construction against those observations, not independent tracing accuracy.','Far notch walls inherit native thickness.']))
if __name__=='__main__':main()
