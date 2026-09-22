"""Original-pixel grids and explicitly labelled near/far/floor observations."""
from pathlib import Path
import json
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
out=root/'inspection/south-cap-fit-v9';out.mkdir(parents=True,exist_ok=True)
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
for name,box in [('042-first',(390,2118,441,2179)),('042-middle',(430,2148,481,2210)),('042-last',(470,2180,530,2244)),
                 ('023-first',(321,1814,351,1904)),('023-bend',(339,1874,378,1972)),('023-far',(360,1934,393,2065))]:
    scale=12;pad=40
    raw=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
    raw.save(out/f'{name}-raw.png')
    grid=Image.new('RGB',(raw.width+pad,raw.height+pad),'black');grid.paste(raw,(pad,pad));d=ImageDraw.Draw(grid)
    for x in range(box[0],box[2]):
        if x%5:continue
        px=pad+(x-box[0]+.5)*scale
        d.line((px,pad,px,grid.height),fill=(80,80,120),width=1);d.text((px-9,10),str(x),fill='white')
    for y in range(box[1],box[3]):
        if y%5:continue
        py=pad+(y-box[1]+.5)*scale
        d.line((pad,py,grid.width,py),fill=(80,80,120),width=1);d.text((0,py-4),str(y),fill='white')
    grid.save(out/f'{name}-grid.png')

# Each row is near crown, far crown, near notch floor. The source-facing
# corner and thickness edge are recorded separately; no model pixels are used.
observations={
 'building-023':[
  [[328,1828],[334,1826],[328,1848]], [[331,1838],[337,1836],[331,1858]],
  [[334,1848],[340,1846],[334,1868]], [[337,1858],[343,1856],[337,1878]],
  [[340,1868],[346,1866],[340,1888]], [[342,1877],[348,1875],[342,1897]],
  [[345,1886],[351,1884],[345,1906]], [[347,1895],[353,1893],[347,1915]],
  [[351,1904],[357,1902],[351,1924]], [[354,1914],[360,1912],[354,1934]],
  [[358,1922],[364,1920],[358,1942]], [[360,1932],[366,1930],[360,1952]],
  [[364,1941],[370,1939],[364,1961]], [[366,1950],[372,1948],[366,1970]]],
 'building-042':[
  [[400,2129],[409,2125],[400,2149]], [[411,2138],[420,2134],[411,2157]],
  [[420,2146],[429,2142],[420,2165]], [[431,2154],[440,2150],[431,2173]],
  [[440,2162],[449,2158],[440,2181]], [[451,2170],[460,2166],[451,2189]],
  [[460,2178],[469,2174],[460,2198]], [[471,2186],[480,2182],[471,2205]],
  [[480,2194],[489,2190],[480,2213]], [[491,2202],[500,2198],[491,2222]],
  [[500,2210],[509,2206],[500,2230]], [[511,2218],[520,2214],[511,2237]]]
}
(out/'source-correspondences.json').write_text(json.dumps({'uncertainty_pixels':2,
 'floor_caveat':'Right-side notch floor corners are occluded and constrained by the visible left-side floor; twenty-pixel depth on023 is a regularized estimate.',
 'corners':observations},indent=2)+'\n')
for node,rows in observations.items():
    box=(320,1812,388,1978) if node.endswith('023') else (390,2118,531,2246)
    im=source.crop(box).resize(((box[2]-box[0])*6,(box[3]-box[1])*6),Image.Resampling.NEAREST);d=ImageDraw.Draw(im)
    def xy(p):return ((p[0]-box[0]+.5)*6,(p[1]-box[1]+.5)*6)
    for i,(near,far,floor) in enumerate(rows):
        d.line((xy(near),xy(far)),fill='cyan',width=1)
        d.line((xy(near),xy(floor)),fill='yellow',width=1)
        for p,color in [(near,'yellow'),(far,'cyan'),(floor,'red')]:
            x,y=xy(p);d.ellipse((x-2,y-2,x+2,y+2),fill=color)
        x,y=xy(near);d.text((x-12,y-10),str(i+1),fill='white')
    im.save(out/f'{node}-observations.png')
