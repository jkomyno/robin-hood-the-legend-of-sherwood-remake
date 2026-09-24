"""Freeze a cached-generation background-support trial without changing source art."""
import hashlib,json,os,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from generated_surface_support import support
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for asset in sys.argv[1:]:
 p=ROOT/'level-editor/work/nottingham-refinement/texture-generation/experiments'/asset;o=p/'repair-background-support';o.mkdir(exist_ok=False)
 for name in ['input.png','mask.png','solid.png','approved-model.blend','approval.json','preparation.json']:
  os.symlink(p/name,o/name)
 m=json.loads((p/'views.json').read_text());m['texture_generated_background_max_rgb']=.015;(o/'views.json').write_text(json.dumps(m,indent=2)+'\n')
 g=p/'generation-short-no-mask-with-lighting-openrouter';a=np.asarray(Image.open(g/'generated-preserved.png').convert('RGBA'));solid=np.asarray(Image.open(p/'solid.png').convert('RGBA'));mask=np.asarray(Image.open(p/'mask.png').convert('RGBA'));reject=np.zeros(a.shape[:2],bool);records=[]
 for v in m['views']:
  c=v['crop'];ys=slice(c['top'],c['top']+c['height']);xs=slice(c['left'],c['left']+c['width']);inside=solid[ys,xs,3]>0;bad=~support(a[ys,xs]/255,inside,.015)&inside&(mask[ys,xs,3]==0);reject[ys,xs]=bad;records.append(dict(view=v['index'],unknown_background_pixels=int(bad.sum())))
 overlay=a.copy();overlay[reject,:3]=[255,0,255];Image.fromarray(overlay).save(o/'rejected-generated-background.png')
 (o/'diagnosis.json').write_text(json.dumps(dict(asset_id=asset,threshold=.015,views=records,total_rejected_unknown_pixels=int(reject.sum()),input_sha256=sha(p/'input.png'),mask_sha256=sha(p/'mask.png'),solid_sha256=sha(p/'solid.png'),generated_sha256=sha(g/'generated-preserved.png'),notes=['Reject exterior-connected near-black pixels only in source-unknown approved geometry.','Enclosed dark timber and windows remain eligible; all protected source texels remain exact.']),indent=2)+'\n');print(asset,records)
