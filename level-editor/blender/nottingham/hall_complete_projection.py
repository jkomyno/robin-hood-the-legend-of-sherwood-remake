"""Restore reviewed hall source domains omitted by conservative placeholder masks."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
ASSET='nottingham-castle-main-hall';OLD=WORK/'round-38/assets'/ASSET;OUT=WORK/'round-39/assets'/ASSET
from correct_source_projection import geometry,geometry_sha
from render_slots import acquire
from freeze_tooling import select_tooling

def write(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import prepare,modified
 from asset_reference_views import render_states
 bpy.ops.wm.open_mainfile(filepath=str(OLD/'model.blend'));before=geometry();cfg=json.loads((OLD/'workspace.json').read_text());m=json.loads((OLD/'source-masks.json').read_text());rows=[]
 for a in m['projections']['exterior']['assignments']:
  if a['source_node']not in cfg['part_ids'] or a['source_node']=='building-497':continue
  node=a['source_node'];component=a.get('projection_component');prior=dict(a)
  # Furniture and ceiling are retained in their reviewed separate room layers.
  if node in ['building-533','building-534','building-535','building-530']:continue
  a.clear();a.update(source_node=node,reviewed=True,mask_indices=[453]if component in ['castle-hall-retained-roof','castle-hall-removable-cover']and node in ['building-505','building-506','building-507','building-527','building-528']else[449],exclude_mask_indices=[442,444,445,451],exclusions_reviewed=True,exclusion_reason='Separate corner spires only. Western terrace440/441 and chimney443 belong to the hall.',constraint_kind='reviewed-native-silhouette',native_ownership_reviewed=True,review_evidence=str(WORK/'hall-completeness/exterior-native-domains.png'),review_note='Complete hall native449 (roof453 for named roof components); original placeholder527 omitted supported facade, terrace and roof receivers. Full-scene first-hit and separate room ownership remain mandatory.')
  if component:a['projection_component']=component
  rows.append({'source_node':node,'component':component,'before':prior,'after':dict(a)})
 mask=WORK/'hall-completeness/complete-exterior-masks.json';write(mask,m)
 prepare(OUT,asset_id=ASSET,scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=OLD/'reference/source.png',grouping_manifest=OLD/'reference/grouping.json',inventory_path=OLD/'reference/inventory.json',review_path=OLD/'reference/grouping-review.json',projection_manifest=OLD/'projection-layers.json',source_mask_manifest=mask,width=cfg['width'],height=cfg['height'],context_padding=cfg['context_padding'],framing_padding=cfg.get('framing_padding',1.04))
 modified(OUT);assert geometry()==before
 render_states(OUT,OUT/'states');write(OUT/'state-packet.json',{'version':1,'directory':str(OUT/'states'),'revealed_input':'input'})
 write(OUT/'mask-correction.json',{'status':'awaiting-completeness-review','geometry_before_sha256':geometry_sha(before),'geometry_after_sha256':geometry_sha(geometry()),'changes':rows})
 write(OUT/'candidate.json',{'version':1,'asset_id':ASSET,'status':'refinement-in-progress','geometry_reviewed':False,'geometry_refined':True,'inspected_views':[],'recipe':str(Path(__file__).resolve()),'texture_generation':'not-started'})
if __name__=='__main__':main()
