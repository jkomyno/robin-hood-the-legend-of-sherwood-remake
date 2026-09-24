"""Group approved facade attachments without changing their saved mesh appearance."""
import argparse, copy, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(d,indent=2)+'\n')
def signature(obj):
 from workspace_components import appearance_state
 appearance=appearance_state(obj)
 for mat in appearance['materials']:
  if mat:
   mat.pop('name',None)
   for node in mat.get('nodes',[]):
    if 'image' in node:
     node['image'].pop('name',None);node['image'].pop('filepath',None)
 return dict(vertices=[list(v.co)for v in obj.data.vertices],faces=[list(p.vertices)for p in obj.data.polygons],world=[list(obj.matrix_world@v.co)for v in obj.data.vertices],matrix=[list(row)for row in obj.matrix_world],appearance=appearance,hidden=obj.hide_render)
def main():
 p=argparse.ArgumentParser();p.add_argument('asset',choices=['northwest-timber-house','north-dormer-house']);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);asset='nottingham-'+a.asset
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Matrix
 import refinement_workspace as rw
 from refinement_review import render_review
 plan=json.loads((WORK/'coordinator-audit/batch6-grouping/donor-workspaces.json').read_text());out=WORK/'round-38/assets'/asset
 if out.exists():raise FileExistsError(out)
 donors=[Path(plan['donor_workspaces'][asset]),Path(plan['donor_workspaces']['nottingham-church-road-mission-props'])]
 propnodes={f'building-{n}'for n in ([551,552]if a.asset.startswith('northwest')else[553,554])};imports={};protected={}
 for i,donor in enumerate(donors):
  model=donor/'model.blend';protected[str(model)]=sha(model);bpy.ops.wm.open_mainfile(filepath=str(model));bpy.context.view_layer.update()
  for obj in bpy.data.collections['nottingham Working'].all_objects:
   if obj.type!='MESH' or (obj.get('asset_group')!=asset if i==0 else obj.get('source_node')not in propnodes):continue
   if obj.modifiers:raise ValueError(('Unexpected modifiers',obj.name))
   imports[obj['source_node']]=dict(name=obj.name,donor=str(model),signature=signature(obj),properties={k:obj[k]for k in obj.keys()if k not in ('asset_group','asset_name','asset_part_name')})
 grouped=Path(plan['grouped_scene']);bpy.ops.wm.open_mainfile(filepath=str(grouped));bpy.context.view_layer.update();targets={o['source_node']:o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==asset};assert set(targets)==set(imports)
 for node,record in imports.items():
  target=targets[node]
  with bpy.data.libraries.load(record['donor'],link=False)as(src,dst):dst.objects=[record['name']]
  loaded=dst.objects[0];target.data=loaded.data.copy();target.matrix_world=Matrix(record['signature']['matrix']);target.hide_render=record['signature']['hidden']
  for k,v in record['properties'].items():target[k]=v
  if node in propnodes:target['simulation_patch_id']='patch-010';target['simulation_patch_applied_active']=False;target['patch_render_visibility_unchanged']=True
  bpy.data.objects.remove(loaded,do_unlink=True)
 bpy.context.view_layer.update()
 def verify():
  rows=[]
  for node,obj in targets.items():
   before=imports[node]['signature'];after=signature(obj)
   for field in ['vertices','faces','appearance','hidden']:
    if before[field]!=after[field]:raise ValueError(('Approved donor changed',node,field))
   drift=max(abs(x-y)for v,w in zip(before['world'],after['world'])for x,y in zip(v,w))
   if drift>1e-5:raise ValueError(('World transform drift',node,drift))
   rows.append(dict(source_node=node,world_drift=drift,mesh_appearance_sha256=hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest()))
  return rows
 verify()
 housem=json.loads((donors[0]/'source-masks.json').read_text());propm=json.loads((donors[1]/'source-masks.json').read_text());m=copy.deepcopy(housem)
 # Retain independent source states, while checking shared native-mask bytes.
 oldinv=Path(housem['mask_inventory']);newinv=Path(propm['mask_inventory']);oldrows={r['index']:r for r in json.loads(oldinv.read_text())['masks']};newrows={r['index']:r for r in json.loads(newinv.read_text())['masks']}
 for row in housem['projections']['exterior']['assignments']:
  if row['source_node']not in targets or row['source_node']in propnodes:continue
  for n in row['mask_indices']+row.get('exclude_mask_indices',[]):
   if sha(oldinv.parent/oldrows[n]['png'])!=sha(newinv.parent/newrows[n]['png']):raise ValueError(('Native mask changed',n))
 m['mask_inventory']=str(newinv);m['projections']['mission-custom1']=copy.deepcopy(propm['projections']['exterior'])
 evidence=WORK/'coordinator-audit/batch6-grouping'/f'{asset}-masks.json';write(evidence,m)
 active=sorted({o.get('source_node')for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render})
 layers=[dict(source_path=str(donors[0]/'reference/source.png'),receiver_nodes=sorted(set(targets)-propnodes),occluder_nodes=active,projection_label='exterior'),dict(source_path=str(donors[1]/'reference/source.png'),receiver_nodes=sorted(propnodes),occluder_nodes=active,projection_label='mission-custom1')]
 # This is an ownership-only preparation. Approved mesh/material datablocks are
 # preserved; the shared renderer still evaluates each source layer independently.
 def preserved_projection(config,report_dir):
  report=dict(status='PRESERVED-APPROVED-PROJECTION',method='Exact approved mesh/UV/material import; no geometry edits or projection bake',parts=verify(),donor_sha256=protected)
  write(Path(report_dir)/'preserved.json',report);return report
 def layered_render(config,output,baseline=None):
  result=render_review(output,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=asset,source_path=config['source_path'],frame_manifest=baseline,width=256,height=320,context_padding=35,framing_padding=1.1,projection_layers=layers,source_mask_manifest=config['source_mask_manifest'],allow_projection_revision=bool(baseline),allow_mask_revision=bool(baseline))
  result['component_ownership']=config['component_ownership'];write(Path(output)/'views.json',result);return result
 rw._reproject=preserved_projection;rw._render=layered_render
 rw.prepare(out,asset_id=asset,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=donors[1]/'reference/source.png',grouping_manifest=WORK/'grouping/catalog-v15.json',inventory_path=grouped.with_suffix('.evidence')/'inventory.json',review_path=WORK/'grouping/grouping-review-v15.json',source_mask_manifest=evidence,width=256,height=320,context_padding=35,framing_padding=1.1)
 rw.modified(out);rows=verify()
 write(out/'preserved-projection-layers.json',dict(layers=layers,donor_sha256=protected,regeneration_recipe=str(Path(__file__).resolve()),geometry_unchanged=True))
 (out/'INSTRUCTIONS.md').write_text('''# V15 preserved house group

This is a grouping-only packet with two independent source layers. The approved donor geometry, UVs and materials are preserved byte-for-byte at the datablock content level. Regenerate only using v15_houses_prepare.py into a fresh workspace; the generic single-source modified command must not replace these materials.

Covered house source and custom1 attachment source are separately assigned in preserved-projection-layers.json. Patch010 deactivates simulation masks/obstacles only; it does not hide the house or attachments in this packet. All eight source diagnostic views and actual saved-material views require review.
''')
 state=dict(version=1,patch_id='patch-010',source_nodes=sorted(propnodes),behavior='Applied state disables simulation obstacles and masks only; all render meshes and materials remain visible.',parent_visibility_unchanged=True,initial_render=str(out/'modified'),applied_render=str(out/'modified'),source_layers=layers)
 write(out/'state-review.json',state)
 write(out/'grouping-preservation.json',dict(status='PASS',asset_id=asset,grouping_revision=15,model_sha256=sha(out/'model.blend'),modified_views_sha256=sha(out/'modified/views.json'),donor_sha256=protected,parts=rows,material_uv_preserved=True,world_geometry_preserved=True,source_layers=layers,patch_010=state))
 write(out/'candidate.json',dict(version=1,asset_id=asset,status='refinement-in-progress',geometry_refined=False,geometry_reviewed=False,inspected_views=[],source_comparison='inspection/v15-saved-materials/materials.png',source_comparison_caption='Actual saved approved materials at the same eight cameras.',recipe=str(Path(__file__).resolve()),state_note='Patch010 changes attachment simulation membership only; no render mesh is hidden.',limitations=['Ownership-only merge preserves approved donor geometry and materials. Patch010 changes simulation membership, not mesh visibility.','Source diagnostic sheets and saved-material renders require separate visual review.']))
 for path,digest in protected.items():assert sha(path)==digest
 print('V15_HOUSE_PRESERVED',asset,flush=True)
if __name__=='__main__':main()
