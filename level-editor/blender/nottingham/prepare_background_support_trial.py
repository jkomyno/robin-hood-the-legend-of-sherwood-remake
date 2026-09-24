"""Freeze a cached-generation background-support trial without changing source art."""
import hashlib,json,os,shutil,sys,argparse
from pathlib import Path
from texture_experiment_paths import selected_experiment
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from generated_surface_support import support
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--scope',default='repair-background-support');parser.add_argument('--use-generation-review',action='store_true');parser.add_argument('assets',nargs='+');args=parser.parse_args()
if Path(args.scope).name!=args.scope:raise ValueError('Scope must be a directory name')
for asset in args.assets:
 p=selected_experiment(asset);o=p/args.scope;o.mkdir(exist_ok=False)
 active=json.loads((p/'texture-review.json').read_text()) if (p/'texture-review.json').exists() else {}
 manifest=p/'views.json'
 raw_review=json.loads((p/'generation-review.json').read_text())
 g=p/active['generation'] if active.get('generation') and not args.use_generation_review else Path(raw_review['generated_preserved_path']).parent
 validation=p/active.get('bake','bake-batch-001')/'validation.json'
 if validation.exists():
  evidence=json.loads(validation.read_text()).get('evidence_sha256',{})
  candidates=[Path(k) for k in evidence if Path(k).name=='views.json']
  if len(candidates)!=1:raise ValueError('Ambiguous active correction manifest')
  manifest=candidates[0]
  if sha(manifest)!=evidence[str(manifest)]:raise ValueError('Active correction manifest changed')
 base=manifest.parent
 for name in ['input.png','mask.png','solid.png','approved-model.blend','approval.json','preparation.json']:
  os.symlink(base/name,o/name)
 m=json.loads(manifest.read_text());m['texture_generated_background_max_rgb']=.015;(o/'views.json').write_text(json.dumps(m,indent=2)+'\n')
 a=np.asarray(Image.open(g/'generated-preserved.png').convert('RGBA'));solid=np.asarray(Image.open(p/'solid.png').convert('RGBA'));mask=np.asarray(Image.open(p/'mask.png').convert('RGBA'));reject=np.zeros(a.shape[:2],bool);records=[]
 for v in m['views']:
  c=v['crop'];ys=slice(c['top'],c['top']+c['height']);xs=slice(c['left'],c['left']+c['width']);inside=solid[ys,xs,3]>0;bad=~support(a[ys,xs]/255,inside,.015)&inside&(mask[ys,xs,3]==0);reject[ys,xs]=bad;records.append(dict(view=v['index'],unknown_background_pixels=int(bad.sum())))
 overlay=a.copy();overlay[reject,:3]=[255,0,255];Image.fromarray(overlay).save(o/'rejected-generated-background.png')
 (o/'diagnosis.json').write_text(json.dumps(dict(asset_id=asset,generation_directory=str(g),parent_manifest=str(manifest),parent_manifest_sha256=sha(manifest),threshold=.015,views=records,total_rejected_unknown_pixels=int(reject.sum()),input_sha256=sha(p/'input.png'),mask_sha256=sha(p/'mask.png'),solid_sha256=sha(p/'solid.png'),generated_sha256=sha(g/'generated-preserved.png'),notes=['Reject exterior-connected near-black pixels only in source-unknown approved geometry.','Enclosed dark timber and windows remain eligible; all protected source texels remain exact.']),indent=2)+'\n');print(asset,records)
