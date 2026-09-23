"""Reopen a split wall and overlay its actual crown edges on source artwork."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
w=Path(sys.argv[sys.argv.index('--')+1]).resolve();bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();c=json.loads((w/'workspace.json').read_text());out=w/'inspection';out.mkdir(exist_ok=True)
rows=[];lines=[]
for o in bpy.data.collections[c['collection_name']].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('asset_group')!=c['asset_id']:continue
 points=[o.matrix_world@v.co for v in o.data.vertices]
 projected=[(p.x,-p.y*math.sin(math.radians(35))-p.z*math.cos(math.radians(35)))for p in points]
 for e in o.data.edges:
  a,b=e.vertices
  if min(points[a].z,points[b].z)>180:lines.append((projected[a],projected[b]))
 rows.append({'object':o.name,'source_node':o.get('source_node'),'component':o.get('projection_component'),'projected_vertices':projected})
xs=[p[0]for line in lines for p in line];ys=[p[1]for line in lines for p in line];box=(math.floor(min(xs))-10,math.floor(min(ys))-10,math.ceil(max(xs))+10,math.ceil(max(ys))+10)
source=Image.open(c['source_path']).convert('RGB').crop(box);overlay=source.copy();draw=ImageDraw.Draw(overlay)
for a,b in lines:draw.line((a[0]-box[0],a[1]-box[1],b[0]-box[0],b[1]-box[1]),fill=(255,0,255),width=1)
result=Image.new('RGB',(source.width*2,source.height));result.paste(source,(0,0));result.paste(overlay,(source.width,0));result.resize((result.width*3,result.height*3),Image.Resampling.NEAREST).save(out/'independent-crown-overlay.png')
(out/'independent-crown-projection.json').write_text(json.dumps({'model_sha256':hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),'source_box':box,'objects':rows},indent=2)+'\n')
print(out/'independent-crown-overlay.png',flush=True)
