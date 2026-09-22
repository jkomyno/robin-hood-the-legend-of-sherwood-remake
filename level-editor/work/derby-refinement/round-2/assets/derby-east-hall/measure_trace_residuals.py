import json,math
from pathlib import Path
from PIL import Image,ImageDraw
W=Path(__file__).parent;D=W/'next-zigzag-v3'
source=Image.open(W/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
mask=Image.open(D/'candidate-source-silhouette.png').getchannel('A')
pix=mask.load();observations=json.loads((D/'source-corners.json').read_text())
edges=json.loads((D/'candidate-edges.json').read_text())
def segment(p,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];n=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/n)) if n else 0
    q=[a[0]+t*dx,a[1]+t*dy]
    return math.dist(p,q),q
results=[]
for run in observations['runs']:
    points=run['points'];is_silhouette=run['id'].startswith('rear-') or run['id']=='stair-turret-silhouette'
    all_edges=[e['source'] for row in edges if row['node'] in [f'building-{i}' for i in run['nodes']] for e in row['edges']]
    crop=(min(p[0] for p in points)-20,min(p[1] for p in points)-20,max(p[0] for p in points)+20,max(p[1] for p in points)+25)
    im=source.crop(crop).resize(((crop[2]-crop[0])*6,(crop[3]-crop[1])*6),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im)
    measured=[]
    for i,p in enumerate(points):
        if is_silhouette:
            candidates=[]
            for x in range(max(0,p[0]-20),min(mask.width,p[0]+21)):
                y=next((y for y in range(700,1100) if pix[x,y]>127),None)
                if y is not None:candidates.append((math.dist(p,[x,y]),[x,y]))
            distance,q=min(candidates)
        else:distance,q=min(segment(p,*edge) for edge in all_edges)
        mapped=lambda xy:((xy[0]-crop[0])*6+3,(xy[1]-crop[1])*6+3)
        a,b=mapped(p),mapped(q);draw.line([a,b],fill='#ffcc00',width=2)
        draw.ellipse((a[0]-2,a[1]-2,a[0]+2,a[1]+2),outline='#00ffff')
        draw.rectangle((b[0]-2,b[1]-2,b[0]+2,b[1]+2),outline='#ff375f')
        draw.text((a[0]+4,a[1]+3),str(i),fill='#00ffff',stroke_width=1,stroke_fill='black')
        measured.append(dict(index=i,source=p,model=q,distance_px=distance))
    im.save(D/(run['id']+'-residuals.png'))
    results.append(dict(id=run['id'],metric='rendered upper silhouette' if is_silhouette else 'nearest projected upper mesh edge; not visibility filtered',
                        mean_px=sum(p['distance_px'] for p in measured)/len(measured),max_px=max(p['distance_px'] for p in measured),points=measured))
(D/'candidate-residuals.json').write_text(json.dumps(results,indent=2))
print([(r['id'],round(r['mean_px'],2),round(r['max_px'],2)) for r in results])
