"""Bind the corrected gateway context and preserved tower meshes to saved files."""
import sys,json,hashlib,collections,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 import bpy,bmesh
 gate=WORK/'round-39/assets/nottingham-castle-gate-arch'
 tower=WORK/'round-43/assets/nottingham-castle-gate-east-tower'
 def read(path):
  bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();out={}
  for o in bpy.data.collections['nottingham Working'].all_objects:
   if o.type!='MESH':continue
   vertices=[list(o.matrix_world@v.co)for v in o.data.vertices]
   value=dict(vertices=vertices,faces=[list(f.vertices)for f in o.data.polygons])
   bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world)
   topology=dict(nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces),volume=abs(bm.calc_volume()));bm.free()
   out[o.name]=dict(asset=o.get('asset_group'),node=o.get('source_node'),component=o.get('projection_component'),state=o.get('animation_state'),geometry_sha256=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest(),topology=topology)
  return out
 old=read(WORK/'round-23/assets'/tower.name/'model.blend')
 arch=read(gate/'model.blend');final=read(tower/'model.blend');base=read(tower/'baseline.blend')
 owned={n:r for n,r in old.items()if r['asset']==tower.name}
 crown_changes={n for n,r in owned.items()if r['component']=='mechanism-upper' or r['node']=='building-338'}
 assert all(final[n]['geometry_sha256']==r['geometry_sha256']for n,r in owned.items()if n not in crown_changes)
 context={n:r for n,r in arch.items()if r['asset']==gate.name}
 assert all(final[n]['geometry_sha256']==r['geometry_sha256']for n,r in context.items())
 nodes={r['node']for r in context.values()}
 assert {n for n,r in final.items()if r['node']in nodes}==set(context)
 assert all(final[n]['geometry_sha256']==r['geometry_sha256']for n,r in base.items()if n not in crown_changes)
 assert set(final)==set(base);name=next(n for n,r in final.items()if r['component']=='gate-jamb-exterior')
 assert final[name]['topology']['nonmanifold_edges']==0 and final[name]['topology']['degenerate_faces']==0
 priorarch=read(WORK/'round-30/assets'/gate.name/'model.blend')
 preserved={n:r for n,r in priorarch.items()if r['asset']==gate.name and(r['state']or r['node']in ['building-335','building-336'])}
 assert all(arch[n]['geometry_sha256']==r['geometry_sha256']for n,r in preserved.items())
 offset=11/(31.6296/35.94214+.348)
 report=dict(status='PASS',gate_model_sha256=sha(gate/'model.blend'),tower_model_sha256=sha(tower/'model.blend'),tower_baseline_sha256=sha(tower/'baseline.blend'),original_tower_meshes_preserved_except_measured_crown=[n for n in owned if n not in crown_changes],measured_crown_changes=sorted(crown_changes),all_frozen_context_meshes_preserved=len(base)-len(crown_changes),paired_arch_context_exact=list(context),stale_canonical_context_duplicates=0,arch_preserved_crown_and_endpoint_meshes=list(preserved),added_exterior=final[name],physical_aperture_at_gate_plane=[910-offset,984-offset],physical_aperture_center=947-offset,original_lowered_sprite_bounds=[910,966],sprite_center_error=abs(938-(947-offset)),inferred_metal_geometry_added=False,floor_changed=False)
 def exterior_signature(path):
  bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update()
  o=next(o for o in bpy.data.objects if o.get('projection_component')=='gate-jamb-exterior')
  import array
  materials=[]
  for m in o.data.materials:
   images=[]
   for n in m.node_tree.nodes if m and m.use_nodes else []:
    if n.type=='TEX_IMAGE' and n.image:
     images.append(dict(size=list(n.image.size),pixels_sha256=hashlib.sha256(array.array('f',n.image.pixels).tobytes()).hexdigest()))
   materials.append(images)
  value=dict(visible=not o.hide_render,vertices=[list(o.matrix_world@v.co)for v in o.data.vertices],faces=[list(f.vertices)for f in o.data.polygons],material_indices=[f.material_index for f in o.data.polygons],uvs={u.name:[list(p.uv)for p in u.data]for u in o.data.uv_layers},materials=materials)
  return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
 signature=exterior_signature(tower/'model.blend');state_records=[]
 for state in ['initial','applied']:
  path=tower/'inspection/endpoints-v6'/('mechanism-'+state)/'model.blend'
  assert exterior_signature(path)==signature, 'Endpoint changed the static exterior jamb material or mesh'
  state_records.append(dict(state=state,model=str(path),model_sha256=sha(path),static_exterior_mesh_uv_packed_rgb_sha256=signature))
 report['tower_endpoint_exterior_preservation']=state_records
 for w in [gate,tower]:(w/'inspection/final-pair-structure.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items()if k not in ['original_tower_meshes_preserved_except_measured_crown','paired_arch_context_exact']}),flush=True)
if __name__=='__main__':main()
