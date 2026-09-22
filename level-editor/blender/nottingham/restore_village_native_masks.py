"""Restore reviewed native source ownership for rural props and the eastern cliff."""
from pathlib import Path
import hashlib,json
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];RUN=ROOT/'level-editor/work/nottingham-refinement'
# Native masks were inspected against the covered source; no bitmap is authored
# or changed. Separate foliage/fence masks exclude those foreground pixels.
ASSETS={
 'small-hut-prop':('round-1',{314:([217],[])}),
 'west-boundary-supplies':('round-1',{315:([228],[233]),316:([228],[233]),317:([229],[233]),318:([230],[])}),
 'south-road-prop':('round-1',{320:([249],[])}),
 'southeast-yard-supplies':('round-1',{321:([264],[]),322:([264],[])}),
 'dovecote-yard-supplies':('round-1',{323:([266],[]),324:([266],[])}),
 'east-boulders':('round-1',{310:([271],[273]),311:([271],[273])}),
 'east-boundary':('round-1',{308:([265],[251,252,253,256]),309:([265],[251,252,253,256])}),
}

def main():
 reports=[]
 for short,(round_name,nodes) in ASSETS.items():
  workspace=RUN/round_name/'assets'/('nottingham-village-'+short);path=workspace/'source-masks.json';manifest=json.loads(path.read_text());inventory_path=Path(manifest['mask_inventory']);inventory=json.loads(inventory_path.read_text());rows={r['index']:r for r in inventory['masks']};changes=[]
  archive=workspace/'inspection/before-native-source-restoration';archive.mkdir(parents=True,exist_ok=True)
  if not(archive/'source-masks.json').exists():(archive/'source-masks.json').write_bytes(path.read_bytes())
  for node,(indices,excluded) in nodes.items():
   entries=[a for a in manifest['projections']['exterior']['assignments']if a.get('source_node')==f'building-{node}' and not a.get('projection_component')]
   if len(entries)!=1:raise ValueError((short,node,len(entries)))
   entry=entries[0];entry.update(mask_indices=indices,exclude_mask_indices=excluded,reviewed=True,native_ownership_reviewed=True,exclusions_reviewed=True,constraint_kind='reviewed-native-visible-object',review_evidence=str(RUN/'village-positive-mask-audit'/f'native-{indices[0]}.png'),review_note='Native positive silhouette reviewed against covered artwork. Distinct foreground foliage and fence masks are excluded where present. Off-image and hidden surfaces remain unknown.')
   entry.pop('accepted_source_pixels',None)
   entry['exclusion_reason']='Separately identified foreground vegetation and fence.' if excluded else 'No separate foreground exclusion is needed inside this native silhouette.'
   changes.append({'source_node':entry['source_node'],'mask_indices':indices,'exclude_mask_indices':excluded,'native_hashes':{str(i):hashlib.sha256((inventory_path.parent/rows[i]['png']).read_bytes()).hexdigest()for i in indices+excluded}})
  path.write_text(json.dumps(manifest,indent=2)+'\n');report={'status':'native-authority-restored-render-pending','asset_id':'nottingham-village-'+short,'mask_inventory_unchanged_sha256':hashlib.sha256(inventory_path.read_bytes()).hexdigest(),'changes':changes};(workspace/'inspection/native-source-restoration.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
 (RUN/'village-positive-mask-audit/ownership-restoration.json').write_text(json.dumps(reports,indent=2)+'\n')
 print('\n'.join(str(RUN/round_name/'assets'/('nottingham-village-'+name))for name,(round_name,_)in ASSETS.items()))

if __name__=='__main__':main()
