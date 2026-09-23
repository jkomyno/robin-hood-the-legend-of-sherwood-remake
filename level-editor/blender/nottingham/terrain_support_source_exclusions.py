"""Independent observed foreground support exclusions in native source pixels."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
import json,hashlib
R=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement'
O=R/'coordinator-audit/terrain-independent'
O.mkdir(parents=True,exist_ok=True)
polygons={
 'wooden bridge full deck edge':[(1918,2723),(1945,2710),(1968,2729),(1987,2740),(2004,2752),(2027,2768),(2024,2777),(2011,2787),(1970,2768),(1954,2758),(1943,2752),(1927,2741)],
 'wooden bridge near hanging support':[(1912,2723),(1919,2722),(1920,2758),(1917,2761),(1914,2741)],
 'wooden bridge deck underside left':[(1923,2728),(1932,2733),(1934,2747),(1929,2748),(1925,2737)],
 'stream fence left post':[(1932,2968),(1938,2968),(1937,3003),(1932,3003)],
 'stream fence middle post':[(1953,2941),(1959,2941),(1959,2979),(1952,2981)],
 'stream fence upper post':[(1974,2917),(1980,2916),(1981,2960),(1974,2962)],
 'stream fence descending main rail':[(1935,2976),(1976,2937),(2009,2918),(2012,2921),(1979,2941),(1936,2981)],
 'stream fence lower diagonal':[(1936,2985),(1978,2945),(2007,2928),(2010,2932),(1981,2950),(1936,2990)],
 'stream fence lower return rail':[(1956,2969),(1983,2963),(1985,2967),(1956,2973)],
 'churchyard raised grave front and sides':[(2208,738),(2225,727),(2251,747),(2251,760),(2235,769),(2208,748)],
 'small wooden grave cross':[(2218,783),(2235,793),(2234,796),(2229,793),(2231,809),(2228,810),(2226,791),(2217,785)],
 'eastern grave slab front':[(2284,746),(2303,743),(2303,752),(2293,758),(2285,752)],
 'churchyard tomb fence feet':[(2180,1075),(2194,1059),(2205,1059),(2213,1070),(2245,1070),(2252,1077),(2252,1094),(2241,1109),(2225,1110),(2212,1103),(2200,1100),(2192,1091),(2180,1096)],
}
mask=Image.new('L',(2304,3520));draw=ImageDraw.Draw(mask)
for name,p in polygons.items():
 if name not in ['wooden bridge near hanging support','wooden bridge deck underside left']:draw.polygon(p,fill=255)
# Only add exclusions in the previously admitted complement. This keeps the
# supplement focused on observed remaining ownership errors.
previous=Image.open(R/'mask-review/inventory-terrain-complete-v3/ground-source-domain.png').convert('L')
mask=ImageChops.multiply(mask,previous);mask.save(O/'supplemental-exclusions.png')
s=Image.open(R/'source-states/covered.png').convert('RGB');tint=Image.blend(s,Image.new('RGB',s.size,(255,0,128)),.65);overlay=s.copy();overlay.paste(tint,mask=mask)
for name,box in [('bridge',(1880,2710,2050,2800)),('fence',(1900,2880,2040,3020)),('grave',(2180,708,2304,812)),('tomb',(2170,1030,2290,1140))]:
 a=Image.new('RGB',((box[2]-box[0])*2,box[3]-box[1]));a.paste(s.crop(box),(0,0));a.paste(overlay.crop(box),(box[2]-box[0],0));a.resize((a.width*4,a.height*4)).save(O/f'supplemental-{name}.png')
(O/'supplemental-exclusions.json').write_text(json.dumps(dict(status='awaiting-independent-review',source_sha256=hashlib.sha256((R/'source-states/covered.png').read_bytes()).hexdigest(),mask_sha256=hashlib.sha256((O/'supplemental-exclusions.png').read_bytes()).hexdigest(),polygons=polygons,omitted_polygons=['wooden bridge near hanging support','wooden bridge deck underside left'],omission_reason='These verticals are likely bank reeds, so no structural rejection was authored for them without stronger ownership evidence.',coordinate_system='native2304x3520 source pixels',uncertainty='1–3 native pixels at blurred rail/post edges; conservative silhouettes include dark structural borders.',rationale='Explicitly observed wood deck edges, rail/post supports, raised grave sides, and iron fence feet. Mask difference is only used to limit output to prior misses, not to establish ownership.'),indent=2)+'\n')
