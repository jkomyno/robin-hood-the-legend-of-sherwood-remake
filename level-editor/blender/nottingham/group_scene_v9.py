"""Integrate approved market partitions into V8 while preserving all outside meshes."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from freeze_tooling import select_tooling
from render_slots import acquire

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geometry(o):return {'vertices':[list(v.co)for v in o.data.vertices],'faces':[list(p.vertices)for p in o.data.polygons],'matrix':[list(row)for row in o.matrix_world],'uv':{u.name:[list(v.uv)for v in u.data]for u in o.data.uv_layers}}
def main():
 tooling=select_tooling(WORK/'tooling/94116d984f92dbae');acquire()
 import bpy
 from catalog_schema import parse_catalog
 from group_assets import reconcile_asset_groups
 source=WORK/'grouped/nottingham-grouped-v8.blend';parts=WORK/'market-partitions-v9/components.blend';output=WORK/'grouped/nottingham-grouped-v9.blend';catalog_path=WORK/'grouping/catalog-v9.json';review_path=WORK/'grouping/grouping-review-v9.json';inventory=WORK/'inventory/inventory-v2.json'
 if output.exists():raise FileExistsError(output)
 review=json.loads(review_path.read_text());proof=json.loads((WORK/'market-partitions-v9/partition-proof.json').read_text())
 if sha(catalog_path)!=review['catalog_sha256'] or sha(inventory)!=review['inventory_sha256']:raise ValueError('Review binding changed')
 for item in review['evidence']:
  if sha(WORK/item['path'])!=item['sha256']:raise ValueError('Partition evidence changed')
 if sha(proof['approved_parent'])!=proof['approved_parent_sha256']:raise ValueError('Approved parent changed')
 bpy.ops.wm.open_mainfile(filepath=str(source));working=bpy.data.collections['nottingham Working'];existing=[o for o in working.all_objects if o.type=='MESH']; market=[o for o in existing if o.get('asset_group')=='nottingham-market-terrace'];outside=[o for o in existing if o not in market];before={o.as_pointer():geometry(o) for o in outside}
 if len(market)!=23:raise ValueError('Expected exactly 23 canonical market meshes')
 names=[p['object']for p in proof['unchanged_meshes']]+[p['object']for p in proof['components']]+[proof['canonical_object']]
 for o in market:bpy.data.objects.remove(o,do_unlink=True)
 with bpy.data.libraries.load(str(parts),link=False)as(available,loaded):
  if set(names)-set(available.objects):raise ValueError('Missing market partitions')
  loaded.objects=names
 imported=list(loaded.objects)
 for o in imported:
  matrix=o.matrix_world.copy();o.parent=None;o.matrix_world=matrix;working.objects.link(o)
 bpy.context.view_layer.update();import_before={o.as_pointer():geometry(o)for o in imported}
 result=reconcile_asset_groups(catalog_path);bpy.context.view_layer.update()
 for o in outside+imported:
  prev=(before if o in outside else import_before)[o.as_pointer()];now=geometry(o)
  if any(prev[k]!=now[k]for k in ('vertices','faces','uv')):raise ValueError('Grouping changed mesh or UV')
  if max(abs(a-b)for ra,rb in zip(prev['matrix'],now['matrix'])for a,b in zip(ra,rb))>1e-5:raise ValueError('Grouping changed transform')
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(output));evidence=output.with_suffix('.evidence');evidence.mkdir()
 for name,path in [('catalog.json',catalog_path),('inventory.json',inventory),('grouping-review.json',review_path)]:shutil.copy2(path,evidence/name)
 report={'status':'PASS','version':1,'tooling':tooling,'source_sha256':sha(source),'partition_blend_sha256':sha(parts),'grouped_sha256':sha(output),'catalog_sha256':sha(catalog_path),'grouping':result,'outside_meshes_preserved':len(outside),'market_meshes_imported':len(imported),'approved_parent_sha256':proof['approved_parent_sha256'],'geometry_mutations_during_grouping':0,'recipe_sha256':sha(__file__)}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n');print('V9_GROUPING_PASS',len(outside),len(imported),flush=True)
if __name__=='__main__':main()
