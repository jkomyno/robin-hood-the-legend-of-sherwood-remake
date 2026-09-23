"""Reopen before/after curved walls and compare actual crown edges and source columns."""
import json,math,sys,hashlib
from pathlib import Path
import bpy
import numpy as np
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement';P=W/'round-13/assets/nottingham-south-curtain-wall-1';sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
acquire();r=json.loads((P/'inspection/curved-crown-correction.json').read_text());box=(1373,2047,1529,2117);source=Image.open(W/'source-states/covered.png').convert('RGB').crop(box);scale=6;rows=[];records=[];S=math.sin(math.radians(35));C=math.cos(math.radians(35))
trace=source.resize((936,420),Image.Resampling.NEAREST);d=ImageDraw.Draw(trace)
for c in r['source_fit']['measured_corners']:
 x,y=c['source_xy'];x=(x-box[0])*scale;y=(y-box[1])*scale;d.ellipse((x-2,y-2,x+2,y+2),fill='yellow');d.text((x+3,y-10),str(c['number']),fill='yellow',stroke_width=1,stroke_fill='black')
rows.append(('Numbered observed cap/notch corners; near and far edge roles are in JSON',trace))
for label,path in [('Before',P/'crown-before'/r['previous_model_sha256'][:12]/'model.blend'),('After',P/'model.blend')]:
 bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('projection_component')=='wall-200-1');world=[obj.matrix_world@v.co for v in obj.data.vertices];points=[[p.x,-p.y*S-p.z*C]for p in world];overlay=source.copy();d=ImageDraw.Draw(overlay);raster=Image.new('1',(156,85));rd=ImageDraw.Draw(raster)
 for f in obj.data.polygons:rd.polygon([(points[i][0]-1373,points[i][1]-2040)for i in f.vertices],fill=1)
 for e in obj.data.edges:
  a,b=e.vertices
  if min(world[a].z,world[b].z)>180:d.line([(points[a][0]-box[0],points[a][1]-box[1]),(points[b][0]-box[0],points[b][1]-box[1])],fill=(255,0,255)if label=='Before'else(0,255,255))
 xs=np.array(r['source_fit']['source_x']);top=np.asarray(raster)[:,xs-1373].argmax(axis=0)+2040;target=np.array(r['source_fit']['source_skyline']);records.append({'revision':label,'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'actual_source_vertices':points,'actual_skyline':top.tolist(),'source_x':xs.tolist(),'mean_absolute_silhouette_error_pixels':float(np.mean(abs(top-target))),'maximum_silhouette_error_pixels':int(max(abs(top-target)))})
 rows.append((label+' actual saved mesh edges',overlay.resize((936,420),Image.Resampling.NEAREST)))
rows.append(('Untouched source',source.resize((936,420),Image.Resampling.NEAREST)))
canvas=Image.new('RGB',(936,445*len(rows)),'#222222');d=ImageDraw.Draw(canvas)
for i,(label,im)in enumerate(rows):d.text((5,i*445+5),label,fill='white');canvas.paste(im,(0,i*445+25))
canvas.save(P/'inspection/curved-crown-source-comparison.png');(P/'inspection/actual-curved-crown-audit.json').write_text(json.dumps({'method':'Reopened saved before/after meshes; source-column skyline raster compared with native126. This is a construction diagnostic, not independent confirmation of landmark choice. Full near/far corner roles and uncertainty in correction report.','source_sha256':r['source_fit']['source_sha256'],'records':records},indent=2)+'\n');print([(q['revision'],q['mean_absolute_silhouette_error_pixels'],q['maximum_silhouette_error_pixels'])for q in records])
