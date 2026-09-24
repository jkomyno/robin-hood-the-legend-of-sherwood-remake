"""Compare accepted source pixels on the exact old and revised church-house roof return."""
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
 old=WORK/'round-9/assets/nottingham-church-north-house';new=WORK/'round-51/assets/nottingham-church-north-house';box=(1810,450,2050,750);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));states=[];face_states=[]
 for w in [old,new]:
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();config=json.loads((w/'workspace.json').read_text());objs=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];body=next(o for o in objs if o.get('source_node')=='building-130');tree,owners,_=_tree(objs);own,ownowners,_=_tree([body]);constraints=SourceMaskConstraints(w/'source-masks.json','exterior',sha(w/'reference/source.png'),(2304,3520));pixels={};face_pixels={};body.data.calc_loop_triangles();triangle_faces=[t.polygon_index for t in body.data.loop_triangles]
  for y in range(box[1],box[3]):
   for x in range(box[0],box[2]):
    if not constraints.allowed_pixel(body,x,y):pixels[x,y]='mask-rejected';continue
    origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,_=own.ray_cast(origin,-toward)
    if i is None:pixels[x,y]='no-body';continue
    if n.dot(toward)<=float(body.get('projection_min_cosine',.05)):pixels[x,y]='grazing';continue
    _,_,j,_=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=body,source_pixel=(x,y));first=owners[j]if j is not None else None
    pixels[x,y]='accepted'if first==body else 'blocked:'+str(first.get('source_node')if first else None)
    if first==body:face_pixels[x,y]=triangle_faces[i]
  states.append(pixels);face_states.append(face_pixels)
 a,b=states;kept=[p for p in a if a[p]=='accepted'and b[p]=='accepted'];removed=[p for p in a if a[p]=='accepted'and b[p]!='accepted'];added=[p for p in b if b[p]=='accepted'and a[p]!='accepted'];counts=collections.Counter(b[p]for p in removed)
 ins=new/'inspection';ins.mkdir(exist_ok=True);source=Image.open(new/'reference/source.png').convert('RGB');left=source.crop(box);right=left.copy()
 for p in kept:right.putpixel((p[0]-box[0],p[1]-box[1]),(0,160,0))
 for p in added:right.putpixel((p[0]-box[0],p[1]-box[1]),(0,255,255))
 for p in removed:right.putpixel((p[0]-box[0],p[1]-box[1]),(255,0,0))
 sheet=Image.new('RGB',(left.width*2,left.height));sheet.paste(left,(0,0));sheet.paste(right,(left.width,0));sheet.resize((sheet.width*2,sheet.height*2)).save(ins/'source-domain-difference.png')
 report=dict(status='PASS'if not removed else'NEEDS-REVIEW',model_sha256=sha(new/'model.blend'),original_model_sha256=sha(old/'model.blend'),retained_source_pixel_count=len(kept),transferred_to_added_return=[p for p in kept if face_states[0][p]<10 and face_states[1][p]>=10],remaining_original_faces=[p for p in kept if face_states[1][p]<10],added_source_pixels=added,removed_source_pixels=removed,removed_states=dict(counts),method='Exact saved building130 source rays, native mask and complete-scene first-hit ownership; original source coordinates.')
 (ins/'source-domain-difference.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
if __name__=='__main__':main()
