"""Inspect the entire receiver silhouette, including pixels rejected by its masks."""
import sys,json,math,hashlib,collections
from pathlib import Path
import bpy
from mathutils import Vector
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints
from source_visibility import first_source_hit
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for arg in sys.argv[sys.argv.index('--')+1:]:
 w=Path(arg).resolve();cfg=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes[cfg['scene_name']];bpy.context.view_layer.update()
 allobs=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH' and not o.hide_render]
 names=json.loads((w/'modified/views.json').read_text())['object_names'];targets=[bpy.data.objects[n] for n in names];tree,owners,_=_tree(allobs);own,ownowners,points=_tree(targets)
 source=Image.open(cfg['source_path']).convert('RGB');sw,sh=source.size;s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));con=SourceMaskConstraints(w/'source-masks.json','exterior',sha(cfg['source_path']),(sw,sh))
 box=(max(0,int(min(p.x for p in points))-2),max(0,int(min(-p.y*s-p.z*c for p in points))-2),min(sw,math.ceil(max(p.x for p in points))+2),min(sh,math.ceil(max(-p.y*s-p.z*c for p in points))+2));orig=source.crop(box);overlay=orig.copy();counts=collections.Counter();witnesses=collections.defaultdict(list);domains=collections.defaultdict(list)
 for y in range(box[1],box[3]):
  for x in range(box[0],box[2]):
   origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,normal,idx,_=own.ray_cast(origin,-toward)
   if idx is None:continue
   o=ownowners[idx];ok=con.allowed_pixel(o,x,y);other,n,j,_=first_source_hit(tree,owners,origin,-toward,constraints=con,receiver=o,source_pixel=(x,y));first=owners[j] if j is not None else None
   key=('allowed' if ok else 'rejected')+(':visible' if first==o else ':blocked:'+str(first.get('source_node') if first else None));counts[key]+=1;domains[key].append([x,y])
   if len(witnesses[key])<20:witnesses[key].append(dict(pixel=[x,y],receiver=o.name,node=o.get('source_node'),normal=list(normal),first=first.name if first else None))
   if not ok:overlay.putpixel((x-box[0],y-box[1]),(255,0,255) if first==o else (50,100,255))
   elif first!=o:overlay.putpixel((x-box[0],y-box[1]),(255,190,0))
 materials={o.name:[dict(name=m.name,properties=dict(m.items()),images=[dict(name=n.image.name,path=n.image.filepath,packed=bool(n.image.packed_file),size=list(n.image.size)) for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]) for m in o.data.materials if m and m.use_nodes] for o in targets};out=w/'inspection/source-domain-audit';out.mkdir(parents=True,exist_ok=True);canvas=Image.new('RGB',(orig.width*2,orig.height));canvas.paste(orig,(0,0));canvas.paste(overlay,(orig.width,0));canvas.save(out/'source-vs-domains.png');(out/'domains.json').write_text(json.dumps(dict(model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),source_sha256=sha(cfg['source_path']),mask_sha256=sha(w/'source-masks.json'),materials=materials,crop=list(box),counts=dict(counts),witnesses=dict(witnesses),domains=dict(domains)),indent=2)+'\n');print(cfg['asset_id'],dict(counts),flush=True)
