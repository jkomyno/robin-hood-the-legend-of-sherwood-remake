"""Restore the church annex mask and source-backed front-room reveal opening."""
import json,sys,hashlib
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-church'
OLD=WORK/'round-3/assets'/ASSET
NEW=WORK/'round-23/assets'/ASSET
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from refine_church import fingerprint,prism,copy_component,label,replace_native,split_plane,SIN,COS

def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def owned():return [o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
def component(n,c=None):
 matches=[o for o in owned() if o.get('source_node')==f'building-{n:03}' and (c is None or o.get('projection_component')==c)]
 assert len(matches)==1,[(o.name,o.get('projection_component')) for o in matches]
 return matches[0]

def revise():
 obj=component(414,'church-retained')
 if obj.get('church_review4'):return json.loads(obj['church_review4'])
 others={o.name:fingerprint(o) for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')!=ASSET}
 native=json.loads((WORK/'source-states/level.json').read_text())['sight_obstacles'];pts=native[414]['points'];xy=[(p['x'],p['y']) for p in pts]
 # The reveal removes the near leg of the elbow wall; the return behind the
 # bed stays tall. Its footprint, corner and concealed thickness stay native.
 near=[xy[i] for i in [0,1,2,5]]
 cover=copy_component(obj,'church-removable-cover');prism(cover,near,28,123.5);label(cover,'church-removable-cover')['reveal_state']='covered'
 vertices=[(x,y,0) for x,y in xy]+[(x,y,28 if i<2 else 123.5) for i,(x,y) in enumerate(xy)]+[(xy[i][0],xy[i][1],28) for i in [2,5]]
 faces=[(5,4,3,2,1,0),(0,1,7,6),(1,2,12,7),(2,3,9,8,12),(3,4,10,9),(4,5,13,11,10),(5,0,6,13),(6,7,12,13),(8,9,10,11),(12,8,11,13)]
 replace_native(obj,vertices,faces)
 bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
 defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
 assert not any(defects.values()),defects
 bm.to_mesh(obj.data);bm.free()
 obj['reveal_state']='both'
 bm=bmesh.new();bm.from_mesh(cover.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(cover.data);bm.free()
 lintel=component(391);label(lintel,'church-removable-cover')['reveal_state']='covered'
 for n in [393,394,395,396]:
  target=component(n,'church-retained')
  covers=[o for o in owned() if o.get('source_node')==f'building-{n}' and o.get('projection_component')=='church-removable-cover']
  for obsolete in covers:bpy.data.objects.remove(obsolete,do_unlink=True)
  points=native[n]['points'];prism(target,[(p['x'],p['y']) for p in points],[p['z_bottom'] for p in points],[p['z_top'] for p in points]);split_plane(target,(0,0,1),28/COS)
 label(component(415),'church-retained')

 for o in owned():o['projection_min_cosine']=.05
 drift=[n for n,h in others.items() if fingerprint(bpy.data.objects[n])!=h];assert not drift,drift
 report={'status':'refined','asset_id':ASSET,'changes':['Restore omitted native roof mask323 on annex403/404/405.','Lower only the near leg of wall414 to the painted28-unit cut rim; retain its full-height rear return.','Remove source391 door lintel together with the vanished front wall in revealed state.','Lower apse front walls393–396 from the incorrect100-unit band to the source28-unit rim; retain the full-height rear wall400.','Restore native331 interior partition and327 front-rim ownership on reviewed retained receivers.'], 'outside_object_changes':drift,'outside_objects_preserved':len(others),'source_mask':323,'retained_front_rim_native_height':28,'limitations':['Native footprints and concealed depths preserved; low rim and tall return form one closed stepped wall mesh.','Rear-facing source-unseen roof and wall surfaces remain neutral.'], 'geometry_approval':'pending','texture_generation':'not-started'}
 obj['church_review4']=json.dumps(report);return report

def configure():
 from refinement_workspace import _absolute_manifest_images
 cfg=json.loads((NEW/'workspace.json').read_text());p=Path(cfg['projection_manifest'])
 a=_absolute_manifest_images(json.loads((NEW/'reference/layers.json').read_text()),NEW/'reference');r=a['projection_reviews']['patch-000']
 for n in [391,393,394,395,396,414]:
  node=f'building-{n:03}';s={'source_node':node,'projection_component':'church-removable-cover','patch_id':'patch-000'}
  if node not in r['partial_cover_nodes']:r['partial_cover_nodes'].append(node)
  for key in ['exclude_occluder_components']:
   if s not in r[key]:r[key].append(s)
  if s not in r['render_visibility']['revealed']['hidden_components']:r['render_visibility']['revealed']['hidden_components'].append(s)
 for n in [393,414]:
  selector={'source_node':f'building-{n}','projection_components':['church-removable-cover'],'patch_id':'patch-000'}
  if selector not in r['receiver_components']['exterior']:r['receiver_components']['exterior'].append(selector)
 if 'building-415' not in r['receiver_nodes']:r['receiver_nodes'].append('building-415')
 selector={'source_node':'building-415','projection_components':['church-retained'],'patch_id':'patch-000'}
 if selector not in r['receiver_components']['interior-patch-000']:r['receiver_components']['interior-patch-000'].append(selector)
 r['evidence']+=' Review4: native rear-annex mask323 restored. Near414 wall leg and391 lintel disappear above the source-painted low front rim, while the rear bed-wall return stays full-height.'
 write(p,a)
 p=Path(cfg['source_mask_manifest']);a=json.loads((NEW/'mask-reference/assignments.json').read_text())
 for e in a['projections']['exterior']['assignments']:
  if e['source_node'] in [f'building-{n}' for n in [403,404,405]]:
   e['mask_indices']=sorted(set(e['mask_indices']+[323]));e['review_note']+=' Native mask323 explicitly associates roofs404/405 and restores source-visible annex pixels, with scene-depth gating unchanged.'
 entries=a['projections']['interior-patch-000']['assignments']
 entries[:]=[e for e in entries if not(e.get('source_node')=='building-414' and e.get('projection_component')=='church-retained')]
 entries.append({'reviewed':True,'source_node':'building-414','projection_component':'church-retained','mask_indices':[327,328,329,330,331], 'constraint_kind':'reviewed-state-receiver','review_evidence':'church-audit/review4-cut-rims.png','review_note':'Retained low front rim and tall bed-wall return; source geometry partitions the shared state masks.'})
 for n,indices in [(386,[331]),(393,[327]),(400,[326,327]),(415,[331])]:
  entries[:]=[e for e in entries if not(e.get('source_node')==f'building-{n}' and e.get('projection_component')=='church-retained')]
  entries.append({'reviewed':True,'source_node':f'building-{n}','projection_component':'church-retained','mask_indices':indices,'constraint_kind':'reviewed-state-receiver','review_evidence':'church-audit/review4-interior-masks.png','review_note':'Native revealed wall silhouette, constrained to the named receiver and first scene-depth hit.'})
 write(p,a)

def main():
 acquire();tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from refinement_workspace import prepare,modified
 operation=sys.argv[sys.argv.index('--')+1]
 if operation=='prepare':
  bpy.ops.wm.open_mainfile(filepath=str(OLD/'model.blend'))
  prepare(NEW,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=OLD/'reference/source.png',grouping_manifest=OLD/'reference/grouping.json',inventory_path=OLD/'reference/inventory.json',review_path=OLD/'reference/grouping-review.json',projection_manifest=OLD/'projection-layers.json',source_mask_manifest=OLD/'source-masks.json',width=384,height=448,context_padding=28,framing_padding=1.15)
  write(NEW/'tooling.json',tooling)
 else:
  bpy.ops.wm.open_mainfile(filepath=str(NEW/('baseline.blend' if operation=='modify' else 'model.blend')));bpy.context.view_layer.update()
  if operation=='modify':
   report=revise();revise();configure();write(NEW/'geometry-report.json',report);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(NEW/'model.blend'));modified(NEW)
  from asset_reference_views import render_states
  target=NEW/'inspection/final-states'
  if target.exists():
   import time
   target.rename(target.with_name('states-history-'+str(time.time_ns())))
  render_states(NEW,target)
if __name__=='__main__':main()
