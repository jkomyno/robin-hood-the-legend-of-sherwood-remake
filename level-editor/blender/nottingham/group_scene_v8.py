"""Integrate immutable baseline partitions into the complete V7 scene and group V8."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
from render_slots import acquire

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def coordinates(obj):return {'matrix':[list(row)for row in obj.matrix_world],'vertices':[list(v.co)for v in obj.data.vertices],'faces':[list(p.vertices)for p in obj.data.polygons]}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--tooling-dir',type=Path,required=True);args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);tooling=select_tooling(args.tooling_dir);acquire()
 import bpy
 from catalog_schema import parse_catalog
 from group_assets import reconcile_asset_groups
 from refinement_inventory import validate_catalog
 source=WORK/'grouped/nottingham-grouped-v7.blend';parts=WORK/'wall-partitions-v8/baseline-components.blend';catalog_path=WORK/'grouping/catalog-v8.json';review_path=WORK/'grouping/grouping-review-v8.json';inventory=WORK/'inventory/inventory-v2.json';output=WORK/'grouped/nottingham-grouped-v8.blend'
 if output.exists():raise FileExistsError(output)
 catalog=json.loads(catalog_path.read_text());review=json.loads(review_path.read_text());index=parse_catalog(catalog)
 if review['catalog_sha256']!=sha(catalog_path)or review['inventory_sha256']!=sha(inventory):raise ValueError('V8 review binding changed')
 for evidence in review['evidence']:
  if sha(WORK/evidence['path'])!=evidence['sha256']:raise ValueError('Reviewed partition evidence changed: '+evidence['path'])
 partition_proof=json.loads((WORK/'wall-partitions-v8/baseline-partition-proof.json').read_text())
 for proof_source in partition_proof['sources']:
  if sha(ROOT/proof_source['path'])!=proof_source['sha256']:raise ValueError('Partition baseline source changed: '+proof_source['path'])
 source_sha=sha(source);bpy.ops.wm.open_mainfile(filepath=str(source));working=bpy.data.collections['nottingham Working'];existing=[o for o in working.all_objects if o.type=='MESH'];before={o.get('source_node'):coordinates(o)for o in existing}
 for obj in existing:
  if obj.get('source_node')in index.split_sources:
   if obj.get('projection_component'):raise ValueError('V7 source unexpectedly already split')
   obj.hide_render=True;obj.hide_viewport=True;obj['canonical_partition_original']=True
 names={component for source,component in index.component_owners}
 with bpy.data.libraries.load(str(parts),link=False)as(available,loaded):
  if names-set(available.objects):raise ValueError('Missing partition object names')
  loaded.objects=sorted(names)
 for obj in loaded.objects:
  working.objects.link(obj);selector=(obj.get('source_node'),obj.get('projection_component'))
  if selector not in index.component_owners:raise ValueError('Unexpected baseline partition selector')
  obj['source_obstacle']=obj['source_node']
 bpy.context.view_layer.update()
 component_coordinates={(obj['source_node'],obj['projection_component']):coordinates(obj)for obj in loaded.objects}
 result=reconcile_asset_groups(catalog_path);bpy.context.view_layer.update()
 for obj in existing:
  current=coordinates(obj);previous=before[obj['source_node']]
  if current['vertices']!=previous['vertices']or current['faces']!=previous['faces']:raise ValueError('Grouping changed canonical mesh')
  if max(abs(a-b)for ra,rb in zip(current['matrix'],previous['matrix'])for a,b in zip(ra,rb))>1e-5:raise ValueError('Grouping changed canonical transform')
 for obj in loaded.objects:
  previous=component_coordinates[obj['source_node'],obj['projection_component']];current=coordinates(obj)
  if current['vertices']!=previous['vertices']or current['faces']!=previous['faces']:raise ValueError('Grouping changed partition geometry')
  if max(abs(a-b)for ra,rb in zip(current['matrix'],previous['matrix'])for a,b in zip(ra,rb))>1e-5:raise ValueError('Grouping changed partition transform')
 bpy.ops.wm.save_as_mainfile(filepath=str(output));evidence=output.with_suffix('.evidence');evidence.mkdir()
 for name,path in [('catalog.json',catalog_path),('inventory.json',inventory),('grouping-review.json',review_path)]:shutil.copy2(path,evidence/name)
 if sha(source)!=source_sha:raise ValueError('V7 immutable baseline changed')
 report={'status':'PASS','version':1,'tooling':tooling,'catalog_validation':validate_catalog(inventory,catalog_path),'grouping':result,'source_sha256':source_sha,'partition_blend_sha256':sha(parts),'catalog_sha256':sha(catalog_path),'inventory_sha256':sha(inventory),'grouped_sha256':sha(output),'geometry_mutations':0,'canonical_originals_hidden':sorted(index.split_sources),'explicit_components':len(component_coordinates),'recipe_sha256':sha(__file__),'argv':sys.argv};output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='tooling'}),flush=True)
if __name__=='__main__':main()
