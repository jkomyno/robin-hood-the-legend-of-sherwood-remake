"""Create a searchable, self-contained source/geometry review for every York group."""
import hashlib
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'level-editor/work/york-refinement'


def triangles(record):
    for part in record['parts']:
        for triangle in part['triangles']:
            yield [part['positions'][v] for v in triangle]


def projected(point,yaw=0,elevation=35):
    x,y,z=point
    a,e=math.radians(yaw),math.radians(elevation)
    return (x*math.cos(a)+y*math.sin(a),
            x*math.sin(a)*math.sin(e)-y*math.cos(a)*math.sin(e)-z*math.cos(e),
            x*math.sin(a)*math.cos(e)-y*math.cos(a)*math.cos(e)+z*math.sin(e))


def solid(record,yaw):
    tris=list(triangles(record))
    transformed=[[projected(p,yaw,40) for p in tri] for tri in tris]
    pts=[p for tri in transformed for p in tri]
    lo=[min(p[i] for p in pts) for i in range(2)]
    hi=[max(p[i] for p in pts) for i in range(2)]
    scale=min(360/max(hi[0]-lo[0],1),270/max(hi[1]-lo[1],1))
    image=Image.new('RGB',(400,300),'#20262d')
    draw=ImageDraw.Draw(image)
    order=sorted(range(len(tris)),key=lambda i:sum(p[2] for p in transformed[i]))
    for i in order:
        tri=tris[i]
        u=[tri[1][j]-tri[0][j] for j in range(3)]
        v=[tri[2][j]-tri[0][j] for j in range(3)]
        n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        length=math.hypot(*n)
        shade=.5+.5*abs(sum(a*b for a,b in zip(n,[-.35,-.45,.82]))/max(length,1e-10))
        color=tuple(int(c*shade) for c in (174,202,214))
        xy=[(200+(p[0]-(lo[0]+hi[0])/2)*scale,150+(p[1]-(lo[1]+hi[1])/2)*scale) for p in transformed[i]]
        draw.polygon(xy,fill=color)
    return image


def main():
    records=json.loads((OUT/'review/geometry.json').read_text())
    catalog=json.loads((ROOT/'level-editor/refinement/catalogs/york.json').read_text())
    scene=json.loads((OUT/'review/scene.json').read_text())
    grounding=json.loads((OUT/'grounding/report.json').read_text()) if scene['grounded'] else None
    source=Image.open(OUT/'baseline/covered.png').convert('RGB')
    folder=OUT/'review/assets'
    folder.mkdir(exist_ok=True)
    font=ImageFont.load_default(size=16)
    cards=[]
    sheets=[]
    manifest=[]
    for number,(key,record) in enumerate(sorted(records.items(),key=lambda item:item[1]['name']),1):
        pts=[projected(p) for tri in triangles(record) for p in tri]
        box=[max(0,math.floor(min(p[0] for p in pts))-18),max(0,math.floor(min(p[1] for p in pts))-18),
             min(source.width,math.ceil(max(p[0] for p in pts))+18),min(source.height,math.ceil(max(p[1] for p in pts))+18)]
        crop=source.crop(box).convert('RGBA')
        overlay=Image.new('RGBA',crop.size)
        d=ImageDraw.Draw(overlay)
        for tri in triangles(record):
            poly=[projected(p) for p in tri]
            d.polygon([(p[0]-box[0],p[1]-box[1]) for p in poly],fill=(20,205,255,48))
        crop=Image.alpha_composite(crop,overlay).convert('RGB')
        crop.thumbnail((600,450))
        crop.save(folder/(key+'-source.jpg'),quality=92)
        left,right=solid(record,-35),solid(record,40)
        left.save(folder/(key+'-west.jpg'),quality=92)
        right.save(folder/(key+'-east.jpg'),quality=92)
        small=Image.new('RGB',(400,370),'#20262d')
        small.paste(left,(0,50))
        label=f'{number:03} '+record['name']
        words=label.split();lines=['']
        for word in words:
            if len(lines[-1])+len(word)>43:lines.append('')
            lines[-1]+=(' ' if lines[-1] else '')+word
        ImageDraw.Draw(small).multiline_text((7,5),'\n'.join(lines),fill='white',font=font)
        sheets.append(small)
        names=sorted({p['source_node'] for p in record['parts']})
        note='Shared surface partitioned at the building junction; hidden continuations are inferred.' if any(p.get('component') for p in record['parts']) else ''
        if grounding and key in grounding['anchors']:
            note+=' Buried surfaces trimmed against raised terrain; exposed terrace-edge walls retained.'
        cards.append(f'''<article id="{key}" data-search="{html.escape(record['name'].lower()+' '+' '.join(names))}">
<h2>{number:03} · {html.escape(record['name'])}</h2><div class="images">
<a href="assets/{key}-source.jpg"><img loading="lazy" src="assets/{key}-source.jpg" alt="Source artwork with selected geometry tinted cyan"></a>
<a href="assets/{key}-west.jpg"><img loading="lazy" src="assets/{key}-west.jpg" alt="Selected geometry from the west"></a>
<a href="assets/{key}-east.jpg"><img loading="lazy" src="assets/{key}-east.jpg" alt="Selected geometry from the east"></a></div>
<p>{html.escape(note)}</p><p><a href="../stage/map-assets/3d-assets/york/{key}/model.glb">Asset model</a> · <a href="../stage/map-assets/3d-assets/york/{key}/asset.json">Asset descriptor</a></p><details><summary>{len(names)} source parts</summary><p>{', '.join(names)}</p><code>{key}</code></details></article>''')
        manifest.append({'id':key,'name':record['name'],'sources':names,'source_bounds':box,'notes':note})
    for start in range(0,len(sheets),12):
        image=Image.new('RGB',(1600,1110),'#20262d')
        for i,card in enumerate(sheets[start:start+12]):image.paste(card,((i%4)*400,(i//4)*370))
        image.save(OUT/f'review/contact-{start//12:02}.jpg',quality=92)
    body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>York — named asset grouping review</title><style>
body{margin:0;background:#151a20;color:#e8edf3;font:16px system-ui}header,main{max-width:1400px;margin:auto;padding:24px}header{position:sticky;top:0;background:#151a20ed;z-index:2;border-bottom:1px solid #435260}h1{margin:0 0 8px}h2{font-size:20px}input{padding:12px;width:90%;max-width:650px;background:#26313e;color:white;border:1px solid #8294a7;border-radius:6px}.images{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.images img{width:100%;height:300px;object-fit:contain;background:#20262d}article{padding:18px;border:1px solid #45505c;border-radius:8px;margin:20px 0}a{color:#8fe0ff}summary{cursor:pointer}details p{line-height:1.7}nav{display:flex;gap:20px;margin:12px 0}code{overflow-wrap:anywhere}.notice{color:#bfcbd8;font-size:14px}@media(max-width:700px){.images{grid-template-columns:1fr}.images img{height:240px}}
</style><header><h1>York · named asset grouping</h1>
<p>GROUP_COUNT named groups + background terrain · 972 visible source records · 9 non-rendering records accounted for</p>
<input id="search" placeholder="Find a house, castle, bridge, prop or source number…" aria-label="Filter assets"><span id="count"></span>
<nav><a href="reference.png">Map view</a><a href="east.png">East overview</a><a href="west.png">West overview</a><a href="plan.png">Plan view</a><a href="../stage/york.rhlos-map.json">Staged map JSON</a></nav>
<p class="notice">Grouping review: source crop (cyan = selected geometry), west and east geometry diagrams. Mesh shape and textures are still the reconstruction baseline. Grouping does not repair missing walls, floating geometry, unseen textures or state-only sprites. Mission doors and patch-only mechanisms are separately inventoried. The market-front foundations and castle hall/tower junction include inferred hidden partition boundaries.</p></header><main>'''+''.join(cards)+'''</main><script>
const input=document.querySelector('#search'),cards=[...document.querySelectorAll('article')];function filter(){const q=input.value.toLowerCase();let n=0;for(const c of cards){c.hidden=!c.dataset.search.includes(q);if(!c.hidden)n++;}document.querySelector('#count').textContent=` ${n} assets`;}input.addEventListener('input',filter);filter();</script></html>'''
    body = body.replace('GROUP_COUNT', str(len(catalog['groups'])))
    if grounding:
        body=body.replace('Mesh shape and textures are still the reconstruction baseline.',
            'Buried surfaces have been trimmed against raised terrain. Visible surfaces and texture coordinates are preserved.')
    (OUT/'review/inspection.html').write_text(body)
    (OUT/'review/manifest.json').write_text(json.dumps({'groups':manifest,'scene':scene,'catalog_sha256':hashlib.sha256((ROOT/'level-editor/refinement/catalogs/york.json').read_bytes()).hexdigest()},indent=2)+'\n')
    from build_grouping_review import build
    build()
    print(json.dumps({'cards':len(cards),'gallery':str(OUT/'review/index.html')}))


if __name__=='__main__':
    main()
