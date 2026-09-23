"""Fit gateway parapets to ordered source cap and notch corners."""
import json,sys,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-castle-gate-arch'
# Far cap edges, in original artwork pixels, left to right. Rear left cap is
# concealed by the tower and its continuation is inferred from the visible run.
TRACES={335:[(876,1340),(882,1338),(882,1316),(908,1307),(908,1325),(919,1321),(919,1303),(944,1294),(944,1313),(955,1309),(955,1289),(982,1280),(982,1299),(992,1295),(992,1277),(1018,1268),(1018,1286),(1019.2907,1285.6)],336:[(863.7979,1290),(874,1286),(874,1265),(899,1256),(899,1274),(912,1269),(912,1253),(937,1244),(937,1262),(949,1258),(949,1237),(971.0065,1229)]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
 acquire();from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from refinement_workspace import prepare,modified
 from refine_church import fingerprint,SIN,COS
 from refine_gate_states import cross_section
 from PIL import Image,ImageDraw
 old=WORK/'round-24/assets'/ASSET;out=WORK/'round-30/assets'/ASSET;c=json.loads((old/'workspace.json').read_text())
 m=json.loads((old/'source-masks.json').read_text());inventory_path=Path(m['mask_inventory']);inventory=json.loads(inventory_path.read_text());from PIL import ImageChops
 scope=WORK/'castle-audit/batch5-arch-occluder';scope.mkdir(exist_ok=True);combined=Image.new('L',(2304,3520))
 for row in inventory['masks']:
  if row['index'] in [289,375]:
   layer=Image.new('L',combined.size);layer.paste(Image.open(inventory_path.parent/row['png']).convert('L'),row['box_top_left']);combined=ImageChops.lighter(combined,layer)
  row['png']=str((inventory_path.parent/row['png']).resolve())
 excluded=Image.new('L',combined.size);ImageDraw.Draw(excluded).polygon([(992,1277),(1018,1268),(1025,1274),(1025,1284),(999,1293),(992,1286)],fill=255);combined=ImageChops.subtract(combined,excluded);combined.save(scope/'tower-owned-domain.png');index=max(r['index']for r in inventory['masks'])+1;inventory['masks'].append(dict(index=index,layer=-1,layer_index=-1,png='tower-owned-domain.png',box_top_left=[0,0],box_size=[2304,3520],mask_type='reviewed-foreign-occluder',source_sha256=sha(old/'reference/source.png'),description='Native289/375 minus visibly foreground right gate merlon cap polygon; only foreign334/337 blocking gate335 are scoped.'))
 (scope/'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n');m['mask_inventory']=str(scope/'manifest.json');[m['projections']['exterior'].setdefault('occluder_constraints',[]).append(dict(reviewed=True,source_node=f'building-{blocker}',receiver_nodes=['building-335'],mask_indices=[index],reason='Native289/375 overlap the visible foreground gate cap; source witnesses1000,1277 and1006,1275 belong gate287/288. Subtract only the directly traced right cap polygon from foreign334/337 occlusion of335; all own and other scene occlusion remains.',review_evidence=str(WORK/'round-28/assets'/ASSET/'inspection/source-coverage-witnesses.json')))for blocker in [334,337]];mask=scope/'source-masks.json';mask.write_text(json.dumps(m,indent=2)+'\n')
 bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update()
 if not out.exists():prepare(out,asset_id=ASSET,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',projection_manifest=old/'projection-layers.json',source_mask_manifest=mask,width=320,height=400,context_padding=35,framing_padding=1.18)
 coll=bpy.data.collections[c['collection_name']];objects={int(o['source_node'].split('-')[1]):o for o in coll.all_objects if o.type=='MESH' and o.get('asset_group')==ASSET and not o.get('animation_state')}
 before={o.name:fingerprint(o) for o in coll.all_objects if o.type=='MESH'};native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'];rows=[];topology={}
 for node,trace in TRACES.items():
  points=native[node]['points'];a,b=points[3],points[0];dx,dy=points[1]['x']-b['x'],points[1]['y']-b['y'];profile=[]
  for index,(x,y) in enumerate(trace):
   t=(x-a['x'])/(b['x']-a['x']);height=a['y']+t*(b['y']-a['y'])-y;profile.append((t,height));rows.append(dict(node=node,index=index+1,source_pixel=[x,y],native_xyz=[x,y+height,height],role='far cap/notch shoulder',visibility='inferred' if (node==336 and x<911) or index in [0,len(trace)-1] else 'observed',uncertainty_pixels=2))
  cross_section(objects[node],[(0,points[0]['z_bottom']),(1,points[0]['z_bottom'])]+list(reversed(profile)),(a['x'],a['y']),(b['x'],b['y']),(dx,dy))
  bm=bmesh.new();bm.from_mesh(objects[node].data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));topology[str(node)]={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)};bm.to_mesh(objects[node].data);bm.free();assert not any(topology[str(node)].values())
  objects[node]['measured_merlon_count']=4 if node==335 else 3
 # Fill the source-visible floor strip between the retained vault roof and
 # the rear parapet. The vault opening and all original333 vertices remain exact.
 from mathutils import Vector
 body=objects[333];verts=[list(v.co) for v in body.data.vertices];faces=[list(f.vertices) for f in body.data.polygons];offset=len(verts);inv=body.matrix_world.inverted()
 rear=lambda x:1589.9856+(x-868.6859)*(1552.4119-1589.9856)/(975.8945-868.6859)
 front=lambda x:1617-(x-910)*.348-30
 right_end=975.8945 # Exact near endpoint of rear parapet336; no invented tower extension.
 footprint=[(882,rear(882)),(right_end,rear(right_end)),(right_end,front(right_end)),(882,front(882))]
 verts += [list(inv@Vector((x,-y/SIN,z/COS))) for z in [271,275] for x,y in footprint]
 faces += [tuple(offset+j for j in f) for f in [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]]
 from refine_church import neutral
 mesh=bpy.data.meshes.new('Gateway original shell plus rear walkway slab');mesh.from_pydata(verts,[],faces);mesh.materials.append(neutral());mesh.uv_layers.new(name='UnprojectedSurfaceUV');mesh.update();body.data=mesh
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));topology['333']={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)};bm.to_mesh(mesh);bm.free();assert not any(topology['333'].values())
 changed={objects[n].name for n in [333,335,336]};assert all(fingerprint(bpy.data.objects[name])==v for name,v in before.items()if name not in changed)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));modified(out)
 crop=(850,1210,1040,1380);scale=5;source=Image.open(old/'reference/source.png');im=source.crop(crop).resize(((crop[2]-crop[0])*scale,(crop[3]-crop[1])*scale),Image.Resampling.NEAREST);(out/'inspection').mkdir(exist_ok=True);im.save(out/'inspection/battlement-source.png');draw=ImageDraw.Draw(im)
 for row in rows:
  x,y=row['source_pixel'];x=(x-crop[0])*scale;y=(y-crop[1])*scale;draw.ellipse((x-3,y-3,x+3,y+3),fill='cyan' if row['visibility']=='observed' else 'orange');draw.text((x+4,y),f"{row['node']%10}.{row['index']}",fill='red')
 im.save(out/'inspection/battlement-numbered.png')
 overlay=source.crop(crop).resize(im.size,Image.Resampling.NEAREST);draw=ImageDraw.Draw(overlay)
 for node in TRACES:
  obj=objects[node]
  for e in obj.data.edges:
   ps=[obj.matrix_world@obj.data.vertices[i].co for i in e.vertices];draw.line([((p.x-crop[0])*scale,(-p.y*SIN-p.z*COS-crop[1])*scale)for p in ps],fill='red',width=1)
 overlay.save(out/'inspection/battlement-actual-mesh.png')
 report=dict(status='awaiting-independent-review',source_sha256=sha(old/'reference/source.png'),model_sha256=sha(out/'model.blend'),corners=rows,topology=topology,outside_preserved=len(before)-3,changed_nodes=[333,335,336],merlon_counts={'front':4,'rear':3},walkway=dict(native_footprint=footprint,native_heights=[271,275],right_end_matches_rear_parapet=right_end,connection='Full front edge equals retained333 back wall plane at nativez271..275; rear edge equals near336 wall plane; both exact shared contacts.'),limitations=['Rear left cap is partly hidden by the west tower; its continuation follows the neighboring repeated profile.','Concealed parapet thickness and lower wall footprint are retained from the previous reviewed model.','Four-unit walkway slab underside is inferred; all original vault and moulding vertices are retained.'])
 (out/'battlement-report.json').write_text(json.dumps(report,indent=2)+'\n');(out/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=ASSET,status='refinement-in-progress',geometry_refined=True,geometry_reviewed=False,recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
