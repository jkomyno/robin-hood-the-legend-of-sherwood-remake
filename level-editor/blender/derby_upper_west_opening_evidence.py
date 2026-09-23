"""Make individual original/target/actual-mesh opening comparisons."""
import json,sys,math
from pathlib import Path
from PIL import Image,ImageDraw

# Source-pixel near-face corner targets reviewed on enlarged original artwork.
# Rows are left-top, left-floor, right-floor, right-top. Raster ambiguity is
# about two pixels; these targets are not a claim of exact recovered dimensions.
LOWER_CORNERS=[
 [(177,1105),(177,1113),(184,1121),(184,1113)],
 [(197,1128),(197,1136),(204,1144),(204,1136)],
 [(217,1151),(217,1159),(224,1167),(224,1159)],
 [(237,1174),(237,1182),(244,1190),(244,1182)],
 [(257,1197),(257,1205),(264,1213),(264,1205)],
 [(277,1221),(277,1229),(283,1236),(283,1228)],
 [(297,1244),(297,1252),(304,1260),(304,1252)],
 [(317,1267),(317,1275),(323,1282),(323,1274)],
 [(337,1290),(337,1298),(344,1306),(344,1298)],
 [(357,1313),(357,1321),(364,1329),(364,1321)],
 [(377,1336),(377,1344),(384,1352),(384,1344)],
 [(397,1359),(397,1367),(404,1375),(404,1367)],
 [(416,1382),(416,1390),(422,1397),(422,1389)],
]


def main():
    packet=Path(sys.argv[1]);frame=json.loads((packet/'modified/views.json').read_text())
    art=Image.open(frame['source_image']).convert('RGB')
    overlay=Image.open(packet/'modified/mesh-on-artwork.png').convert('RGB')
    root=packet/'opening-evidence';root.mkdir(exist_ok=True)
    crop=frame['context_crop'];records=[];panels=[]
    def card(label,box,points):
        source=art.crop(box).resize((240,300),Image.Resampling.NEAREST)
        target=source.copy();draw=ImageDraw.Draw(target)
        def xy(p):return((p[0]-box[0])*240/(box[2]-box[0]),(p[1]-box[1])*300/(box[3]-box[1]))
        if points:
            draw.line([xy(p) for p in points],fill=(50,255,80),width=1)
            for i,p in enumerate(points):
                x,y=xy(p);draw.ellipse((x-2,y-2,x+2,y+2),fill=(50,255,80))
                draw.text((x+3,y),str(i+1),fill=(255,255,0))
        obox=((box[0]-crop['left'])*3,(box[1]-crop['top'])*3,
              (box[2]-crop['left'])*3,(box[3]-crop['top'])*3)
        actual=overlay.crop(obox).resize((240,300),Image.Resampling.NEAREST)
        panel=Image.new('RGB',(720,328),'#202020');d=ImageDraw.Draw(panel)
        for x,im,title in [(0,source,'Raw source'),(240,target,'Source corner targets'),(480,actual,'Saved mesh edges')]:
            panel.paste(im,(x,28));d.text((x+5,8),f'{label}: {title}',fill='white')
        panel.save(root/f'{label}.png');panels.append(panel)
        records.append(dict(id=label,source_crop=box,source_corners=points,source_uncertainty_pixels=2))
    for i,points in enumerate(LOWER_CORNERS):
        x,y=points[0];card(f'lower-{i+1:02}',(x-6,y-13,x+20,y+22),points)
    # The native silhouette supplies independent rear-edge pixels, rather than
    # manufacturing a projected model contour and calling it source evidence.
    native_root=Path('datadirs/fullgame_gog_hackable/Data/Levels/Derby.rhp.d/masks')
    inv=json.loads((native_root/'manifest.json').read_text())
    record=next(r for r in inv['masks'] if r['index']==108)
    native=Image.open(native_root/record['png']).convert('L');ox,oy=record['box_top_left']
    for i,(left,right) in enumerate([(181,191),(192,202),(204,214),(216,226),(228,238)]):
        points=[]
        for x in range(left,right+1):
            ys=[y for y in range(native.height) if native.getpixel((x-ox,y))]
            if ys:points.append((x,min(ys)+oy))
        y=min(p[1] for p in points)
        card(f'upper-{i+1:02}',(left-3,y-5,right+15,y+36),points)
    (packet/'source-opening-targets.json').write_text(json.dumps(records,indent=2))
    for name,start,end in [('lower-openings',0,13),('upper-openings',13,18)]:
        selected=panels[start:end];sheet=Image.new('RGB',(720,len(selected)*328),'#202020')
        for i,panel in enumerate(selected):sheet.paste(panel,(0,i*328))
        sheet.save(root/f'{name}.png')


if __name__=='__main__':main()
