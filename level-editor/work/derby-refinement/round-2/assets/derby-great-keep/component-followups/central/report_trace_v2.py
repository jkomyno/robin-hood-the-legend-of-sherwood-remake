"""Build source-sized diagnostics from measured Blender vertices."""
from pathlib import Path
import json,math,ast,shutil
import numpy as np
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parent;O=W/'trace-v2';ROOT=W.parents[7]
module=ast.parse((ROOT/'level-editor/blender/derby_round4_keep_central_trace.py').read_text())
traces=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TRACES' for t in n.targets))
old=json.loads((W/'mesh-inspection-v2.json').read_text());new=json.loads((O/'mesh-inspection-v2.json').read_text())
source=Image.open(W.parents[1]/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
revealed=Image.open(W.parents[1]/'reference/revealed.png').convert('RGB')
def segments(rows,node,top=True):
 out=[]
 for ob in rows:
  if ob['hidden'] or ob['node']!=node:continue
  edges={tuple(sorted((a,b))) for f in ob['faces'] for a,b in zip(f,f[1:]+f[:1])}
  for a,b in edges:
   if top and min(ob['vertices'][a][2],ob['vertices'][b][2])<655:continue
   out.append((np.array(ob['projected'][a]),np.array(ob['projected'][b])))
 return out
def distance(p,edges):
 p=np.array(p)
 def d(a,b):
  v=b-a;t=np.clip(np.dot(p-a,v)/max(np.dot(v,v),1e-12),0,1);return float(np.linalg.norm(p-a-t*v))
 return min(d(a,b) for a,b in edges)
box=(748,287,883,466);scale=6
def transform(p):return ((p[0]-box[0])*scale,(p[1]-box[1])*scale)
metrics=[]
for state,img in [('covered',source),('revealed',revealed)]:
 base=img.crop(box).resize((135*scale,179*scale),Image.Resampling.NEAREST)
 for version,rows in [('before',old),('after',new)]:
  panel=base.copy();d=ImageDraw.Draw(panel)
  for node in ['building-153','building-158']:
   for a,b in segments(rows,node):d.line([transform(a),transform(b)],fill=(0,230,255),width=1)
  for name,points in traces.items():
   for i,p in enumerate(points):
    x,y=transform(p);d.ellipse((x-2,y-2,x+2,y+2),fill='yellow');d.text((x+3,y-10),f'{name[0]}{i}',fill='yellow',stroke_width=1,stroke_fill='black')
  panel.save(O/f'{state}-{version}-contour.png')
 base.save(O/f'{state}-source-detail.png')
for name,points in traces.items():
 node='building-153' if name=='front' else 'building-158'
 before=[distance(p,segments(old,node)) for p in points];after=[distance(p,segments(new,node)) for p in points]
 metrics.append({'run':name,'ordered_source_pixels':points,'before_nearest_edge_pixels':before,'after_nearest_edge_pixels':after,'before_mean':sum(before)/len(before),'after_mean':sum(after)/len(after),'uncertainty':'manual pixel trace, about 2-3 pixels; rear-right termination occluded; nearest projected edge is diagnostic and not full silhouette IoU'})
deck=next(o for o in old if o['node']=='building-160' and not o['hidden'])
v=np.array(deck['vertices']);ids=sorted({i for f,n in zip(deck['faces'],deck['normals']) if n[2]>.9 for i in f});top=v[ids];coeff=np.linalg.lstsq(np.column_stack([top[:,:2],np.ones(len(top))]),top[:,2],rcond=None)[0];res=top[:,2]-np.column_stack([top[:,:2],np.ones(len(top))])@coeff
bridge={'top_vertices':top.tolist(),'plane_z_ax_by_c':coeff.tolist(),'plane_rms_world':float(np.sqrt(np.mean(res**2))),'elevation_degrees':math.degrees(math.atan(float(np.linalg.norm(coeff[:2])))),'height_range': [float(top[:,2].min()),float(top[:,2].max())],'changed':False,'reason':'Deck mostly hidden behind parapets in source. Physical slope is real in inherited model, not merely camera perspective; no independent endpoint heights establish a flat replacement.'}
for state,img in [('covered',source),('revealed',revealed)]:
 crop=(510,500,700,660);im=img.crop(crop).resize((760,640),Image.Resampling.NEAREST);d=ImageDraw.Draw(im)
 for i in ids:
  x,y=deck['projected'][i];x=(x-crop[0])*4;y=(y-crop[1])*4;d.ellipse((x-3,y-3,x+3,y+3),fill='cyan');d.text((x+4,y),str(i),fill='yellow',stroke_width=1,stroke_fill='black')
 for a,b in [(6,7),(7,8),(9,10),(10,11)]:d.line([((deck['projected'][i][0]-crop[0])*4,(deck['projected'][i][1]-crop[1])*4) for i in (a,b)],fill='cyan',width=2)
 im.save(O/f'{state}-bridge-projection.png')
(O/'trace-and-slope.json').write_text(json.dumps({'traces':metrics,'bridge':bridge,'sun_elevation_degrees':48},indent=2))
for name in ['solid.png','textured.png']:shutil.copy2(W/'modified'/name,O/('before-'+name))
(O/'review.md').write_text('''# Central Turret/Gallery correction — source trace and 48° lighting

Corrected the three front gaps and three rear gap boundaries by individually measured source positions. Visible merlon count was already correct; phase, width and front notch depth were corrected. The hidden final rear-right termination is retained. All thirteen active meshes are closed with positive volume; all 817 outside objects are unchanged. Original projection was reapplied with native-source constraints.

Yellow numbered points are manual source observations; cyan lines are projected model edges. These include interior/thickness edges, so the numerical nearest-edge distance is a diagnostic, not a semantic silhouette score. Manual uncertainty is about 2–3 source pixels.

![Covered original](covered-source-detail.png)
![Covered before](covered-before-contour.png)
![Covered corrected](covered-after-contour.png)
![Revealed original](revealed-source-detail.png)
![Revealed corrected](revealed-after-contour.png)

## Bridge

The inherited deck really has a world-space slope; it is not only a diagonal from the camera. Its deck endpoints and segments are shown below in cyan. Most of the deck lies behind the front parapet. The adjacent Hall floor and West Tower interior belong to other component workers. They are preserved. These pictures do not establish reliable independent deck endpoint heights, so this revision does not flatten it or claim its slope is proved correct.

![Covered bridge projection](covered-bridge-projection.png)
![Revealed bridge projection](revealed-bridge-projection.png)

## Eight views

Before uses the archived lighting; after explicitly uses the user-selected 48° world sun. Geometry comparison is clearest in the source-space contour overlays above.

![Before solid](before-solid.png)
![After solid](modified/solid.png)
![Before source textures](before-textured.png)
![After source textures](modified/textured.png)

Exact ordered corners, residuals and measured deck plane are in [trace-and-slope.json](trace-and-slope.json). No AI fill or editor publication was performed. Revealed context is shown for alignment inspection; no central component is registered as an interior-patch receiver and no adjacent interior mesh was modified.
''')
print(json.dumps({'traces':[(r['run'],r['before_mean'],r['after_mean']) for r in metrics],'bridge':bridge},indent=2))
