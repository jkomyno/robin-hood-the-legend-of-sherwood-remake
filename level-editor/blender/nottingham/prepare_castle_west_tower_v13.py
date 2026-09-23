"""Preserve refined west tower geometry while transferring gate piers out of its group."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from prepare_gate_v11 import capture,geometry,key,sha

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Vector
 from refinement_workspace import prepare,modified
 asset='nottingham-castle-gate-west-tower';old=WORK/'round-23/assets'/asset;out=WORK/'round-24/assets'/asset;captured=capture(old/'model.blend',asset);imports={k:v for k,v in captured.items()if k[0]in ['building-329','building-330','building-331','building-332']};assert len(imports)==4
 grouped=WORK/'grouped/nottingham-grouped-v13.blend';bpy.ops.wm.open_mainfile(filepath=str(grouped));bpy.context.view_layer.update();collection=bpy.data.collections['nottingham Working'];targets={key(o):o for o in collection.all_objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==asset};assert set(targets)==set(imports)
 outside={o.name:geometry(o) for o in collection.all_objects if o.type=='MESH'and o not in targets.values()};neutral=bpy.data.materials.new('West tower V13 unknown neutral');neutral.diffuse_color=(.45,.45,.45,1);rows=[]
 for obj in collection.all_objects:
  if obj.type=='MESH'and not obj.data.materials:obj.data.materials.append(neutral)
 for identity,obj in targets.items():
  record=imports[identity];matrix=obj.matrix_world.copy();inverse=matrix.inverted();mesh=bpy.data.meshes.new(obj.name+' preserved refined mesh');mesh.from_pydata([inverse@Vector(v)for v in record['world_vertices']],[],record['faces']);mesh.update();mesh.materials.append(neutral)
  for name,values in record['uv_layers'].items():
   layer=mesh.uv_layers.new(name=name)
   for v,uv in zip(layer.data,values):v.uv=uv
  obj.data=mesh
  for k,v in record['projection_properties'].items():obj[k]=v
  drift=max((matrix@v.co-Vector(p)).length for v,p in zip(mesh.vertices,record['world_vertices']));assert drift<.001
  rows.append(dict(source_node=identity[0],maximum_world_vertex_drift=drift,vertices=len(mesh.vertices),faces=len(mesh.polygons)))
 assert outside=={o.name:geometry(o)for o in collection.all_objects if o.type=='MESH'and o not in targets.values()}
 evidence=grouped.with_suffix('.evidence');prepare(out,asset_id=asset,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=WORK/'grouping/catalog-v13.json',inventory_path=evidence/'inventory.json',review_path=WORK/'grouping/grouping-review-v13.json',source_mask_manifest=old/'source-masks.json',width=256,height=320,context_padding=35,framing_padding=1.1)
 modified(out);report=dict(version=1,status='awaiting-independent-visual-review',previous_workspace=str(old),previous_model_sha256=sha(old/'model.blend'),model_sha256=sha(out/'model.blend'),geometry_unchanged=True,grouping_revision=13,source_imports=rows,foreign_geometry_preserved=len(outside),changes='Moved gate piers349/350 out of west tower into arch in V13 catalog; retained exact4 refined tower parts and corrected native284/285/286 minus cottage65/chimney67.')
 (out/'texture-feedback-correction.json').write_text(json.dumps(report,indent=2)+'\n');(out/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=asset,status='refinement-in-progress',geometry_reviewed=False,geometry_refined=False,inspected_views=[]),indent=2)+'\n')
if __name__=='__main__':main()
