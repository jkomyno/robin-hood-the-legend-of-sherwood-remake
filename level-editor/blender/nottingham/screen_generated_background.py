"""Rank exterior-connected black intrusions before baking; never auto-approve or reject."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import binary_erosion,label,find_objects
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement/texture-generation'
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from generated_surface_support import support
out=WORK/'generation-background-screening';out.mkdir(exist_ok=True);records=[];skipped=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p in sorted((WORK/'experiments').iterdir()):
 if not p.is_dir() or not (p/'views.json').exists():continue
 m=json.loads((p/'views.json').read_text());g=p/'generation-short-no-mask-with-lighting-openrouter/generated-preserved.png'
 if not g.exists() or len(m.get('views',[]))!=8:skipped.append(p.name);continue
 paths=[p/'input.png',p/'solid.png',p/'mask.png',g];images=[np.asarray(Image.open(f).convert('RGBA')) for f in paths];input_,solid,mask,generated=images
 if len({a.shape for a in images})!=1:raise ValueError('Dimension mismatch '+p.name)
 views=[];worst=None
 for v in m['views']:
  c=v['crop'];ys=slice(c['top'],c['top']+c['height']);xs=slice(c['left'],c['left']+c['width']);inside=solid[ys,xs,3]>0;unknown=mask[ys,xs,3]==0
  bad=(~support(generated[ys,xs]/255,inside,.015))&unknown&binary_erosion(inside,iterations=2);count=int(bad.sum());components=[];labels,n=label(bad)
  for i,box in enumerate(find_objects(labels),1):
   if box is None:continue
   y,x=box;components.append(dict(pixels=int((labels[box]==i).sum()),box=[x.start,y.start,x.stop,y.stop]))
  components.sort(key=lambda r:r['pixels'],reverse=True);views.append(dict(view=v['index'],pixels=count,components=components[:5]))
  if count and (worst is None or count>worst[0]):worst=(count,v,bad,components[0])
 record=dict(asset_id=m['asset_id'],experiment=str(p),total=sum(v['pixels'] for v in views),views=views,evidence={f.name:sha(f) for f in paths})
 if worst:
  _,v,bad,component=worst;c=v['crop'];box=component['box'];x0=max(0,box[0]-20);y0=max(0,box[1]-20);x1=min(c['width'],box[2]+20);y1=min(c['height'],box[3]+20);ys=slice(c['top']+y0,c['top']+y1);xs=slice(c['left']+x0,c['left']+x1)
  a=Image.fromarray(input_[ys,xs]);b=Image.fromarray(generated[ys,xs]);overlay=generated[ys,xs].copy();overlay[bad[y0:y1,x0:x1],:3]=[255,0,255];d=Image.fromarray(overlay);canvas=Image.new('RGBA',(a.width*3,a.height+20),(20,20,20,255));draw=ImageDraw.Draw(canvas);draw.text((3,3),f'{p.name} view {v["index"]}: input | generated | suspect',fill='white')
  for i,img in enumerate([a,b,d]):canvas.paste(img,(i*a.width,20))
  path=out/(p.name+'.png');canvas.convert('RGB').save(path);record['illustration']=str(path);record['illustrated_view']=v['index']
 records.append(record)
records.sort(key=lambda r:r['total'],reverse=True);report=dict(status='diagnostic-only',criteria='Source-unknown, approved silhouette eroded 2px, RGB<=.015 connected to exterior. Legitimate dark material must be visually classified; no automatic holds.',assets_scanned=len(records),skipped=skipped,records=records)
(WORK/'generation-background-screening.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(assets_scanned=len(records),top=[dict(asset_id=r['asset_id'],pixels=r['total']) for r in records[:25]]),indent=2))
