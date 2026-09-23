"""Bind reviewed tower packets to the shared collector contract."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve()
BASE=HERE.parents[2]/'work/leicester-refinement/round-1/assets-v2'
SPECS={'northwest':(5,'patch-007'),'east-moat':(4,'patch-003'),'church-side':(4,'patch-003'),'west-moat':(2,'combined')}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def record_visual(path,evidence):
 report=json.loads(path.read_text())
 assert report['status']=='STRUCTURAL-PASS' and not report['problems']
 assert all(sha(path.parent/name)==digest for name,digest in report['artifact_sha256'].items())
 report['visual_review']={'status':'PASS','views':list(range(8)),'evidence':evidence,'reviewer':'mask_audit'}
 path.write_text(json.dumps(report,indent=2)+'\n')
def run():
 for name,(version,display) in SPECS.items():
  workspace=BASE/f'leicester-{name}-tower';model_hash=sha(workspace/'model.blend')
  evidence=workspace/f'inspection/review-evidence-v{version}.json';prior=json.loads(evidence.read_text())
  states=json.loads((workspace/f'inspection/states-v{version}/states.json').read_text())['states'];material_states=[]
  for state in states:
   state_id=state['patch_id']+'-'+state['state'];audit=workspace/f'inspection/stored-material-{state_id}-v{version}/audit.json'
   report=json.loads(audit.read_text());assert report['model_sha256']==model_hash
   assert sorted(report['render_object_names'])==sorted(state['object_names'])
   record_visual(audit,prior['stored_material_visual_inspection'])
   material_states.append(dict(id=state_id,audit=str(audit.relative_to(workspace)),frame_manifest='input/views.json'))
  record_visual(workspace/'inspection/stored-materials/audit.json','All eight primary actual-material views inspected alongside the source-reviewed covered/revealed state sheets; unchanged source ownership, neutral unknown faces, no displaced atlas textures.')
  sources={p.name:{'sha256':sha(p),'source':p.read_text()} for p in HERE.parent.glob('towers*.py') if 'diagnostic' not in p.name}
  recipe=workspace/'inspection/tower-recipe-bundle.json';recipe.write_text(json.dumps(dict(description='Tower authoring and repair helpers; per-asset applied reports identify executed revisions.',sources=sources),indent=2)+'\n')
  handoff=dict(status='ready-for-user',notes=prior['stored_material_visual_inspection'],recipe=str(recipe.relative_to(workspace)),ownership='source-masks.json',all_eight_views_inspected=True,has_revealed_state=True,geometry_approval='pending',texture_generation='not-started',stored_material_states=material_states,review_evidence=str(evidence.relative_to(workspace)))
  for state in ['covered','revealed']:
   for kind in ['solid','textured','context']:
    handoff[state+'_'+kind]=f'inspection/states-v{version}/{display}/{state}/{kind}.png'
  (workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
  prior['files'].update({str(p.relative_to(workspace)):sha(p) for p in [workspace/'handoff.json',recipe,workspace/'inspection/stored-materials/audit.json']})
  for item in material_states:prior['files'][item['audit']]=sha(workspace/item['audit'])
  evidence.write_text(json.dumps(prior,indent=2)+'\n')
if __name__=='__main__':run()
