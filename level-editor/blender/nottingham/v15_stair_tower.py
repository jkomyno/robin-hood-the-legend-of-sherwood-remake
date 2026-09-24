"""Transfer an upper-terrace parapet out while preserving the approved stair assembly."""
import hashlib,json,sys
from array import array
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from freeze_tooling import select_tooling
from render_slots import acquire
ASSET='nottingham-castle-west-stair-tower';NODES={f'building-{n}'for n in [485,486,487,496,498]}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def material(mat):
 if mat is None:return None
 result={'use_nodes':mat.use_nodes,'diffuse':list(mat.diffuse_color),'nodes':[],'links':[]}
 if mat.use_nodes:
  for n in mat.node_tree.nodes:
   d={'name':n.name,'type':n.bl_idname,'inputs':[]}
   for socket in n.inputs:
    if hasattr(socket,'default_value'):
     v=socket.default_value
     if isinstance(v,(int,float,str,bool)):d['inputs'].append([socket.name,v])
     elif hasattr(v,'__iter__'):d['inputs'].append([socket.name,list(v)])
   for k in ['uv_map','interpolation','extension','projection','operation','blend_type']:
    if hasattr(n,k):d[k]=getattr(n,k)
   if n.type=='TEX_IMAGE' and n.image:
    im=n.image;pixels=array('f',[0])*len(im.pixels);im.pixels.foreach_get(pixels);d['image']={'size':list(im.size),'pixels':hashlib.sha256(pixels.tobytes()).hexdigest(),'colorspace':im.colorspace_settings.name,'alpha_mode':im.alpha_mode}
   result['nodes'].append(d)
  result['links']=[[l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name]for l in mat.node_tree.links]
 return result
def signature(o):
 return {'vertices':[list(v.co)for v in o.data.vertices],'polygons':[[list(p.vertices),p.material_index,p.use_smooth]for p in o.data.polygons],'uv':{l.name:[list(v.uv)for v in l.data]for l in o.data.uv_layers},'matrix':[list(r)for r in o.matrix_world],'materials':[material(m)for m in o.data.materials],'hidden':o.hide_render}
def append_donor(path):
 with bpy.data.libraries.load(str(path),link=False) as (a,b):b.objects=[n for n in a.objects if n.startswith('Castle western stair tower /')]
 objs=[o for o in b.objects if o and o.type=='MESH'and o.get('source_node')in NODES and not o.hide_render]
 result={o['source_node']:o for o in objs};assert set(result)==NODES;return result

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from refinement_workspace import prepare,modified,validate
 from mathutils import Matrix
 donor=WORK/'round-26/assets'/ASSET;w=WORK/'round-41/assets'/ASSET;grouped=WORK/'grouped/nottingham-grouped-v15.blend';catalog=WORK/'grouping/catalog-v15.json';protected_hash=sha(donor/'model.blend');bpy.ops.wm.open_mainfile(filepath=str(donor/'model.blend'));bpy.context.view_layer.update();golden={o['source_node']:o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render and o.get('asset_group')==ASSET and o.get('source_node')in NODES};snapshots={n:signature(o)for n,o in golden.items()};parenting={n:{'inverse':[list(r)for r in o.matrix_parent_inverse],'basis':[list(r)for r in o.matrix_basis],'parent_world':[list(r)for r in o.parent.matrix_world]}for n,o in golden.items()};bpy.ops.wm.open_mainfile(filepath=str(grouped));bpy.context.view_layer.update();collection=bpy.data.collections['nottingham Working'];targets={o.get('source_node'):o for o in collection.all_objects if o.type=='MESH'and o.get('asset_group')==ASSET and not o.hide_render};assert set(targets)==NODES
 imports=append_donor(donor/'model.blend')
 def assign(records):
  for node,obj in targets.items():
   source=records[node];obj.data=source.data.copy();assert [list(r)for r in obj.parent.matrix_world]==parenting[node]['parent_world'];obj.matrix_parent_inverse=Matrix(parenting[node]['inverse']);obj.matrix_basis=Matrix(parenting[node]['basis'])
   for key in list(obj.keys()):
    if key.startswith(('projection_','reprojection_')) and key!='projection_component':del obj[key]
   for key in source.keys():
    if key.startswith(('projection_','reprojection_')) and key!='projection_component':obj[key]=source[key]
   obj.hide_render=source.hide_render
  bpy.context.view_layer.update()
  for node,obj in targets.items():
   actual=signature(obj);diff=[k for k in actual if actual[k]!=snapshots[node][k]]
   if diff:print('DIFFERENCE',node,diff,[(k,actual[k],snapshots[node][k])for k in diff if k in ['matrix','hidden']],flush=True)
   assert not diff,node
 assign(imports)
 # Unlinked donor objects are solely import carriers and cannot affect scene rays.
 for obj in imports.values():bpy.data.objects.remove(obj,do_unlink=True)
 cfg=json.loads((donor/'workspace.json').read_text());evidence=grouped.with_suffix('.evidence')
 prepare(w,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=donor/'reference/source.png',grouping_manifest=catalog,inventory_path=evidence/'inventory.json',review_path=WORK/'grouping/grouping-review-v15.json',source_mask_manifest=donor/'source-masks.json',width=cfg['width'],height=cfg['height'],context_padding=cfg['context_padding'],framing_padding=cfg.get('framing_padding',1.04))
 modified(w)
 restored=append_donor(donor/'model.blend');assign(restored)
 for obj in restored.values():bpy.data.objects.remove(obj,do_unlink=True)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));validation=validate(w);assert protected_hash==sha(donor/'model.blend')
 report={'status':'PASS','asset_id':ASSET,'catalog_sha256':sha(catalog),'donor_model_sha256':protected_hash,'model_sha256':sha(w/'model.blend'),'modified_views_sha256':sha(w/'modified/views.json'),'retained_source_nodes':sorted(NODES),'transferred_source_node':'building-497','new_parent_asset':'nottingham-castle-main-hall','approved_geometry_uv_materials_transforms_preserved':True,'signature_authority':'Approved donor opened as the main scene with evaluated parent transforms, not unlinked imported objects','signatures':{n:digest(v)for n,v in snapshots.items()},'source_packet_method':'Shared native source projection, then exact approved mesh/UV/material restoration. Actual saved material renders are required separately.','validation':validation}
 (w/'regrouping-preservation.json').write_text(json.dumps(report,indent=2)+'\n');(w/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');c=json.loads((donor/'candidate.json').read_text());c.pop('source_comparison',None);c.pop('source_trace',None);c['limitations']=['Rear faces and lower support volumes concealed by neighboring castle structures remain neutral because they have no original visible artwork.'];c.update(status='refinement-in-progress',geometry_reviewed=False,geometry_refined=False,no_change_reason='Exact approved five-part geometry, UVs, materials and world transforms retained. Detached terrace parapet497 moved to the main hall group.',inspected_views=[],model_sha256=report['model_sha256'],modified_views_sha256=report['modified_views_sha256'],changes=['Moved upper-terrace parapet497 into the main hall group.','Retained the approved stair, turret, landing, side coping and small doorway roof unchanged.'],recipe=str(Path(__file__).resolve()),user_approval='pending',stored_material_evidence='inspection/v15-stored-materials/audit.json');(w/'candidate.json').write_text(json.dumps(c,indent=2)+'\n');print('V15_STAIR_PRESERVED',report['model_sha256'],flush=True)
if __name__=='__main__':main()
