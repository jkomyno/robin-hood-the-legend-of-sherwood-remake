"""Source-aligned entry footprint and reviewed walkable-floor projection."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).resolve().parent))

def apply(workspace):
 import bpy
 from refine_castle_secondary import native_prism,entry_treads,sha,write
 from refinement_workspace import _geometry,modified
 config=json.loads((workspace/'workspace.json').read_text());objects=list(bpy.data.collections[config['collection_name']].all_objects);targets={int(o['source_node'][9:]):o for o in objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']};before={o.name:_geometry(o) for o in objects}
 def point(x,source_y,z):return {'x':x,'y':source_y+z,'z_top':z}
 landing=[point(641,1147,115),point(660,1184,115),point(554,1214,115),point(533,1185,115)]
 outer=[point(670,1176,100),point(665,1206,100),point(553,1234,100),point(524,1203,100)]
 rows=[{'source_node':'building-373',**native_prism(targets[373],landing,bottom=100)}]
 for n,indices in [(374,(1,2)),(375,(2,3)),(376,(0,1))]:
  a,b=indices;rows.append({'source_node':f'building-{n}',**entry_treads(targets[n],[outer[a],outer[b],landing[b],landing[a]])})
 assert all(before[o.name]==_geometry(o) for o in objects if o not in targets.values())
 write(workspace/'entry-floor-report.json',{'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'changes':rows,'source_outline':{'upper':[(p['x'],p['y']-p['z_top']) for p in landing],'lower':[(p['x'],p['y']-p['z_top']) for p in outer]},'source_evidence':['castle-audit/entry-source-measure.png','castle-audit/entry-derived-mask-review.png'],'inference':'Courtyard100 and landing115 retain native datums; hidden corners behind doorway columns and equal intermediate tread depths are inferred.'})
 bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)

if __name__=='__main__':
 from freeze_tooling import select_tooling
 select_tooling()
 from render_slots import acquire
 acquire()
 w=WORK/'round-6/assets/nottingham-castle-entry-steps'
 if not (w/'model.blend').exists():
  import refinement_review
  original=refinement_review.fit_camera
  def fit(*a,**kw):kw['padding']=1.3;return original(*a,**kw)
  refinement_review.fit_camera=fit
  from prepare_assets import main
  main(['--source-blend',str(WORK/'grouped/nottingham-grouped-v5.blend'),'--output',str(WORK/'round-6/assets'),'--source-path',str(WORK/'source-states/covered.png'),'--grouping-manifest',str(WORK/'grouping/catalog-v5.json'),'--inventory-path',str(WORK/'inventory/inventory-v2.json'),'--review-path',str(WORK/'grouping/grouping-review-v5.json'),'--projection-manifest',str(WORK/'state-review/baseline-final-layers.json'),'--source-mask-manifest',str(WORK/'mask-review/source-masks-entry-v1.json'),'--width','256','--height','320','--prepare-only','nottingham-castle-entry-steps'])
 else:
  import bpy
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
 apply(w)
