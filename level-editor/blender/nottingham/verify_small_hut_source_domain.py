"""Audit every native forge pixel against geometry, ownership and source occlusion."""
import sys,json,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 import bpy
 from mathutils import Vector
 from refinement_review import _tree
 from occlusion_constraints import SourceMaskConstraints
 from source_visibility import first_source_hit
 from projection_context import ground_exclusion
 from PIL import Image
 w=Path(sys.argv[sys.argv.index('--')+1]).resolve();bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update()
 c=json.loads((w/'workspace.json').read_text());objs=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and not o.hide_render]
 exclude=ground_exclusion(c,objs)
 if exclude:objs=[o for o in objs if o.name!=exclude['object_name']]
 targets=[o for o in objs if o.get('asset_group')==c['asset_id']];tree,owners,_=_tree(objs);own,ownowners,_=_tree(targets)
 constraints=SourceMaskConstraints(w/'source-masks.json','exterior',sha(w/'reference/source.png'),(2304,3520));s,co=math.sin(math.radians(35)),math.cos(math.radians(35));tow=Vector((0,-co,s))
 mask=ROOT/'level-editor/work/nottingham-refinement/mask-review/inventory-v6/000210.png';m=Image.open(mask).convert('L');counts=collections.Counter();rejected=collections.defaultdict(list);src=Image.open(w/'reference/source.png').convert('RGB');box=(340,2745,470,2910);overlay=src.crop(box)
 for dy in range(m.height):
  for dx in range(m.width):
   if not m.getpixel((dx,dy)):continue
   x,y=dx+352,dy+2755;origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*co))+tow*10000
   hit,n,i,_=own.ray_cast(origin,-tow);reason='accepted'
   if i is None:reason='missing-receiver'
   else:
    body=ownowners[i]
    if not constraints.allowed_pixel(body,x,y):reason='mask-rejected'
    elif n.dot(tow)<=float(body.get('projection_min_cosine',.05)):reason='grazing'
    else:
     _,_,j,_=first_source_hit(tree,owners,origin,-tow,constraints=constraints,receiver=body,source_pixel=(x,y))
     if j is None or owners[j]!=body:reason='blocked:'+str(owners[j].get('source_node') if j is not None else None)
   counts[reason]+=1
   if reason!='accepted':rejected[reason].append([x,y]);overlay.putpixel((x-box[0],y-box[1]),(255,0,255)if reason=='missing-receiver'else(255,70,0))
 ins=w/'inspection';ins.mkdir(exist_ok=True);overlay.resize((780,990),Image.Resampling.NEAREST).save(ins/'full-native-source-coverage.png')
 report=dict(status='PASS'if not rejected else'NEEDS-REVIEW',asset_id=c['asset_id'],model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),source_sha256=sha(w/'reference/source.png'),domain_sha256=sha(mask),native_pixels=sum(counts.values()),counts=dict(counts),rejected_pixels=dict(rejected),ground_exclusion=exclude,method='Every nonzero native210 pixel center, independent of candidate masks; exact saved target first-hit geometry, source-facing cosine, native ownership and complete-scene foreground occlusion. Only the explicitly evidenced generic ground proxy is excluded.')
 (ins/'full-native-source-coverage.json').write_text(json.dumps(report,indent=2)+'\n');print(dict(counts),flush=True)
if __name__=='__main__':main()
