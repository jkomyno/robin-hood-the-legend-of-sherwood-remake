"""Inventory selected held support bakes and bind depth-corrected diagnostics."""
import json,hashlib,sys
from pathlib import Path
from texture_experiment_paths import selected_experiment
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'level-editor/work/nottingham-refinement/coordinator-audit/support-backlog'
NAMES=['market-front-red','market-front-west-green','south-curtain-wall-3','south-curtain-wall-4','castle-southwest-spire','southwest-curtain-wall-south','church-west-house','upper-west-house','village-west-cottage','forest-east-stump','village-small-hut-prop','upper-street-turret','castle-upper-wall','southeast-shutter-house','village-stream-wall','castle-west-stair','castle-west-courtyard-wall','south-gate-arch','south-stair-house']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory():
 rows=[]
 for name in NAMES:
  asset='nottingham-'+name;exp=selected_experiment(asset);bake=exp/('bake-background-support-002'if name in ['castle-west-stair','castle-west-courtyard-wall']else'bake-background-support-001');v=json.loads((bake/'validation.json').read_text());manifests=[Path(p)for p in v['evidence_sha256']if Path(p).name=='views.json'];assert len(manifests)==1;manifest=manifests[0];assert sha(manifest)==v['evidence_sha256'][str(manifest)]
  current=json.loads((exp/'texture-review.json').read_text());coverage=next((bake/p/'coverage.json'for p in ['coverage-depth','coverage']if(bake/p/'coverage.json').exists()),None);actual=next((bake/p/'textured.png'for p in ['actual-depth','actual']if(bake/p/'textured.png').exists()),None)
  row=dict(asset_id=asset,experiment=str(exp),bake=str(bake),model_sha256=sha(bake/'worker.blend'),manifest=str(manifest),manifest_sha256=sha(manifest),validation_sha256=sha(bake/'validation.json'),current_review_status=current['status'],current_review_sha256=sha(exp/'texture-review.json'),status='awaiting-exact-rays')
  if coverage:
   c=json.loads(coverage.read_text());assert c['model_sha256']==row['model_sha256']and c['manifest_sha256']==row['manifest_sha256'];row.update(coverage=str(coverage),coverage_sha256=sha(coverage),red_pixels=sum(v['unfilled_visible_pixels']for v in c['views']),depth_corrected=coverage.parent.name=='coverage-depth')
  else:row['status']='coverage-render-needed'
  if actual:row.update(actual=str(actual),actual_sha256=sha(actual))
  rows.append(row)
 OUT.mkdir(exist_ok=True);(OUT/'inventory.json').write_text(json.dumps(rows,indent=2)+'\n');print([(r['asset_id'],r['status'],r.get('red_pixels'),r.get('depth_corrected'))for r in rows])
if __name__=='__main__':inventory()
