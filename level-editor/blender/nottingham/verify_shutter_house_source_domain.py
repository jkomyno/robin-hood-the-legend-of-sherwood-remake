"""Compare accepted source pixels on the exact old and revised shutter-house body."""
import sys,json,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Vector
 from refinement_review import _tree
 from occlusion_constraints import SourceMaskConstraints
 from source_visibility import first_source_hit
 from PIL import Image
 old=WORK/'round-1/assets/nottingham-southeast-shutter-house';new=WORK/'round-33/assets/nottingham-southeast-shutter-house';box=(1810,1680,2000,2020);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));states=[]
 for w in [old,new]:
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();config=json.loads((w/'workspace.json').read_text());objs=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];body=next(o for o in objs if o.get('source_node')=='building-036');tree,owners,_=_tree(objs);own,ownowners,_=_tree([body]);constraints=SourceMaskConstraints(w/'source-masks.json','exterior',sha(w/'reference/source.png'),(2304,3520));pixels={}
  for y in range(box[1],box[3]):
   for x in range(box[0],box[2]):
    if not constraints.allowed_pixel(body,x,y):pixels[x,y]='mask-rejected';continue
    origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,_=own.ray_cast(origin,-toward)
    if i is None:pixels[x,y]='no-body';continue
    if n.dot(toward)<=float(body.get('projection_min_cosine',.05)):pixels[x,y]='grazing';continue
    _,_,j,_=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=body,source_pixel=(x,y));first=owners[j]if j is not None else None
    pixels[x,y]='accepted'if first==body else 'blocked:'+str(first.get('source_node')if first else None)
  states.append(pixels)
 a,b=states;kept=[p for p in a if a[p]=='accepted'and b[p]=='accepted'];removed=[p for p in a if a[p]=='accepted'and b[p]!='accepted'];added=[p for p in b if b[p]=='accepted'and a[p]!='accepted'];counts=collections.Counter(b[p]for p in removed)
 maskmanifest=json.loads((new/'source-masks.json').read_text());inventory=Path(maskmanifest['mask_inventory']);meta=json.loads(inventory.read_text())['masks'];native={}
 for index in [32,33,37,38,40]:
  entry=meta[index];native[index]=(entry,Image.open(inventory.parent/entry['png']).convert('L'))
 def contains(index,p):
  entry,im=native[index];x=p[0]-entry['box_top_left'][0];y=p[1]-entry['box_top_left'][1];return 0<=x<im.width and 0<=y<im.height and im.getpixel((x,y))>0
 classified=collections.defaultdict(list)
 for p in removed:
  owners=[i for i in [32,33,40]if contains(i,p)]
  if owners:reason='foreign-native-'+','.join(map(str,owners))
  elif not contains(37,p)and contains(38,p):reason='roof-art-outside-facade37'
  else:reason='unresolved-'+b[p]
  classified[reason].append(p)
 ins=new/'inspection';ins.mkdir(exist_ok=True);source=Image.open(new/'reference/source.png').convert('RGB');left=source.crop(box);right=left.copy()
 for p in kept:right.putpixel((p[0]-box[0],p[1]-box[1]),(0,160,0))
 for p in added:right.putpixel((p[0]-box[0],p[1]-box[1]),(0,255,255))
 for reason,points in classified.items():
  for p in points:right.putpixel((p[0]-box[0],p[1]-box[1]),(255,0,0)if reason.startswith('unresolved')else(255,200,0))
 sheet=Image.new('RGB',(left.width*2,left.height));sheet.paste(left,(0,0));sheet.paste(right,(left.width,0));sheet.resize((sheet.width*3,sheet.height*3)).save(ins/'source-domain-difference.png')
 report=dict(status='PASS'if not any(k.startswith('unresolved')for k in classified)else'NEEDS-REVIEW',model_sha256=sha(new/'model.blend'),original_model_sha256=sha(old/'model.blend'),source_sha256=sha(new/'reference/source.png'),retained_source_pixel_count=len(kept),added_source_pixels=added,removed_source_pixels=dict(classified),removed_state_counts=dict(counts),legend='Green retained; cyan newly covered source; yellow proven foreign/roof-domain removal; red unresolved original source loss.',method='Exact saved body source rays with native domain, cosine, complete-scene first-hit ownership. Pixel centers compared in original source coordinates, independently of review camera framing.')
 (ins/'source-domain-difference.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items()if k not in ['added_source_pixels','removed_source_pixels']}, {k:len(v)for k,v in classified.items()},flush=True)
if __name__=='__main__':main()
