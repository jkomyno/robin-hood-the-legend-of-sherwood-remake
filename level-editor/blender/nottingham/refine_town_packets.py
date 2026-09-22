"""Apply and verify town contact recipes using the frozen packet helpers.

Usage: blender --background --threads 2 --python refine_town_packets.py -- ASSET...
Pass --restore to replay base seam/architecture and contact recipes from baseline.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
select_tooling()
from render_slots import acquire
from refine_town import refine as base_refine
from refine_town_contacts import refine
from refinement_workspace import modified

def mesh_hash(asset):
 rows=[]
 for o in sorted(bpy.data.collections['nottingham Working'].all_objects,key=lambda o:o.name):
  if o.type=='MESH'and o.get('asset_group')==asset:
   rows.append([o['source_node'],[list(v.co)for v in o.data.vertices],[list(p.vertices)for p in o.data.polygons],[list(row)for row in o.matrix_world]])
 return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('assets',nargs='+');parser.add_argument('--restore',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);acquire()
 for asset in args.assets:
  p=WORK/'round-1/assets'/asset;bpy.ops.wm.open_mainfile(filepath=str(p/('baseline.blend'if args.restore else'model.blend')))
  if args.restore:base_refine(asset)
  report=refine(asset);before=mesh_hash(asset);refine(asset);after=mesh_hash(asset)
  if before!=after:raise ValueError('Recipe is not idempotent')
  report['idempotence']={'status':'PASS','geometry_sha256':after};(p/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');print(asset,modified(p),flush=True)
if __name__=='__main__':main()
