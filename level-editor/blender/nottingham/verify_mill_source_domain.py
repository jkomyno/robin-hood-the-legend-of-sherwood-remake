"""Compare exact source coverage before and after the derived mill correction."""
import sys,json,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
 import bpy
 from mathutils import Vector
 from refinement_review import _tree
 from occlusion_constraints import SourceMaskConstraints
 from source_visibility import first_source_hit
 from PIL import Image
 old=WORK/'round-1/assets/nottingham-village-mill';new=WORK/('round-34/assets/nottingham-village-mill' if '--final' in sys.argv else 'texture-generation/projection-corrections/nottingham-village-mill');box=(1525,2455,1760,2790);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));states=[]
 for w in [old,new]:
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));config=json.loads((w/'workspace.json').read_text());bpy.context.window.scene=bpy.data.scenes[config['scene_name']];bpy.context.view_layer.update();objs=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];targets=[o for o in objs if o.get('asset_group')=='nottingham-village-mill'];tree,owners,_=_tree(objs);own,ownowners,_=_tree(targets);constraints=SourceMaskConstraints(w/'source-masks.json','exterior',sha(w/'reference/source.png'),(2304,3520));pixels={}
  for y in range(box[1],box[3]):
   for x in range(box[0],box[2]):
    origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,_=own.ray_cast(origin,-toward)
    if i is None:pixels[x,y]='no-body';continue
    body=ownowners[i]
    if not constraints.allowed_pixel(body,x,y):pixels[x,y]='mask-rejected:'+str(body.get('source_node'));continue
    if n.dot(toward)<=float(body.get('projection_min_cosine',.05)):pixels[x,y]='grazing';continue
    _,_,j,_=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=body,source_pixel=(x,y));first=owners[j]if j is not None else None
    pixels[x,y]='accepted'if first==body else 'blocked:'+str(first.get('source_node')if first else None)
  states.append(pixels)
 a,b=states;kept=[p for p in a if a[p]=='accepted'and b[p]=='accepted'];removed=[p for p in a if a[p]=='accepted'and b[p]!='accepted'];added=[p for p in b if b[p]=='accepted'and a[p]!='accepted'];counts=collections.Counter(b[p]for p in removed)
 classified=collections.defaultdict(list)
 for p in removed:
  reason='unresolved-'+b[p]
  classified[reason].append(p)
 ins=new/'inspection';ins.mkdir(exist_ok=True);source=Image.open(new/'reference/source.png').convert('RGB');left=source.crop(box);right=left.copy()
 for p in kept:right.putpixel((p[0]-box[0],p[1]-box[1]),(0,160,0))
 for p in added:right.putpixel((p[0]-box[0],p[1]-box[1]),(0,255,255))
 for reason,points in classified.items():
  for p in points:right.putpixel((p[0]-box[0],p[1]-box[1]),(255,0,0)if reason.startswith('unresolved')else(255,200,0))
 sheet=Image.new('RGB',(left.width*2,left.height));sheet.paste(left,(0,0));sheet.paste(right,(left.width,0));sheet.resize((sheet.width*3,sheet.height*3)).save(ins/'source-domain-difference.png')
 report=dict(status='PASS'if not any(k.startswith('unresolved')for k in classified)else'NEEDS-REVIEW',model_sha256=sha(new/'model.blend'),original_model_sha256=sha(old/'model.blend'),source_sha256=sha(new/'reference/source.png'),retained_source_pixel_count=len(kept),added_source_pixel_count=len(added),removed_source_pixel_count=len(removed),original_state_counts=dict(collections.Counter(a.values())),modified_state_counts=dict(collections.Counter(b.values())),added_source_pixels=added,removed_source_pixels=dict(classified),removed_state_counts=dict(counts),legend='Green retained; cyan newly covered source; yellow source-classified removal; red unresolved original source loss.',method='Exact saved whole-asset source rays with native domain, cosine, complete-scene first-hit ownership. Pixel centers compared in original source coordinates, independently of review camera framing.')
 (ins/'source-domain-difference.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items()if k not in ['added_source_pixels','removed_source_pixels']}, {k:len(v)for k,v in classified.items()},flush=True)
if __name__=='__main__':main()
