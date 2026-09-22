from PIL import Image,ImageDraw
from pathlib import Path
import json
W=Path(__file__).parent;D=W/'next-zigzag-v3'
source=Image.open(W/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
for name,crop,nodes in [('stair-turret',(1220,725,1340,835),[198]),('rear',(1350,750,1580,940),[185]),('front-west',(1180,875,1345,1015),[184,191,192,194]),('front-south',(1320,955,1430,1065),[194,183]),('front-east',(1400,955,1570,1065),[183,189])]:
    for state,file in [('before','top-edges.json'),('after','candidate-edges.json')]:
        im=source.crop(crop).resize(((crop[2]-crop[0])*5,(crop[3]-crop[1])*5),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im)
        for row in json.loads((D/file).read_text()):
            if row['node'] not in [f'building-{i}' for i in nodes]:continue
            for edge in row['edges']:
                draw.line([((x-crop[0])*5,(y-crop[1])*5) for x,y in edge['source']],fill='#00ffff',width=1)
        im.save(D/(name+'-'+state+'-actual-edges.png'))
