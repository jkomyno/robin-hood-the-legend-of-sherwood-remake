"""Retain every rejected native-domain sample for spatial source review."""
import sys
from pathlib import Path
script=Path(__file__).parent/'audit_castle_final_source_coverage.py'
code=script.read_text().replace('recovered=[]','recovered=[];domain_rows=[]')
code=code.replace('counts[key]+=1',"counts[key]+=1;domain_rows.append(dict(pixel=[x,y],classification=key,**details))")
code += '''
colors={'no_receiver':(0,100,255),'hit_outside_receiver_assignment':(255,140,0)}
overlay=source.crop(crop)
for row in domain_rows:
 color=colors.get(row['classification'])
 if color:
  x,y=row['pixel'];overlay.putpixel((x-box[0],y-box[1]),color)
overlay.resize((overlay.width*2,overlay.height*2),Image.Resampling.NEAREST).save(w/'inspection/native-domain-rejections.png')
(w/'inspection/native-domain-rejections.json').write_text(json.dumps(dict(model_sha256=report['model_sha256'],source_sha256=hashlib.sha256((w/'reference/source.png').read_bytes()).hexdigest(),legend=colors,rows=domain_rows),indent=2)+'\\n')
'''
exec(compile(code,str(script),'exec'))
if (w/'crown-correction.json').exists():
 trace=json.loads(Path(json.loads((w/'crown-correction.json').read_text())['trace']).read_text())
 caps=collections.defaultdict(list)
 for corner in trace['corners']:caps[corner['cap']].append(corner['source_pixel'])
 def inside(x,y,polygon):
  result=False
  for a,b in zip(polygon,polygon[1:]+polygon[:1]):
   if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
  return result
 cap_report={}
 for name,polygon in caps.items():
  rows=[r for r in domain_rows if inside(r['pixel'][0]+.5,r['pixel'][1]+.5,polygon)]
  cap_report[name]=dict(counts=dict(collections.Counter(r['classification']for r in rows)),no_receiver=[r['pixel']for r in rows if r['classification']=='no_receiver'])
 (w/'inspection/crown-native-polygon-coverage.json').write_text(json.dumps(dict(model_sha256=report['model_sha256'],caps=cap_report),indent=2)+'\n')
