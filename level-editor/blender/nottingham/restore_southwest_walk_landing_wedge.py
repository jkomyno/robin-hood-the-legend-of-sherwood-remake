"""Restore the measured wall-walk paving wedge beside the separate stair landing."""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from PIL import Image,ImageDraw
import refinement_workspace as rw
from audit_stored_materials import run
old=WORK/'round-31/assets/nottingham-southwest-curtain-wall-north';new=WORK/'round-35/assets'/old.name;scope=WORK/'mask-review/southwest-walk-landing-wedge-final';scope.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Independent actual-scene ray and material checks identify this paving wedge
# as wall220, with no stair221 receiver hit. Keep its domain receiver-specific.
rows={1515:(681,711),1516:(681,705),1517:(682,698),1518:(682,691),1519:(682,685)}
mask=Image.new('L',(2304,3520));pixels=[]
for y,(lo,hi) in rows.items():
 for x in range(lo,hi+1):mask.putpixel((x,y),255);pixels.append([x,y])
assert len(pixels)==87;mask.save(scope/'paving-wedge.png')
m=json.loads((old/'source-masks.json').read_text());path=Path(m['mask_inventory']);inventory=json.loads(path.read_text())
for row in inventory['masks']:row['png']=str((path.parent/row['png']).resolve())
index=max(row['index'] for row in inventory['masks'])+1;inventory['masks'].append(dict(index=index,layer=-1,layer_index=-1,png='paving-wedge.png',box_top_left=[0,0],box_size=[2304,3520],mask_type='source-traced-wall-walk-paving',source_sha256=sha(old/'reference/source.png'),description='87 observed pale paving pixels between native133 walkway edge and separate221 landing; actual-scene first hits are220 and no221 receiver exists.'))
# Keep every preexisting blocker pixel outside the exact87-pixel addition.
from PIL import ImageChops
ImageChops.invert(mask).save(scope/'outside-wedge.png');blocker_index=index+1
inventory['masks'].append(dict(index=blocker_index,layer=-1,layer_index=-1,png='outside-wedge.png',box_top_left=[0,0],box_size=[2304,3520],mask_type='preserve-existing-occlusion-outside-reviewed-wedge',source_sha256=sha(old/'reference/source.png')))
(scope/'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n');m['mask_inventory']=str(scope/'manifest.json')
a=next(a for a in m['projections']['exterior']['assignments'] if a['source_node']=='building-220');a['mask_indices']=[133,index];a['review_note']='Native133 wall walk plus independently measured87-pixel paving wedge; no broad native135 union.';a['review_evidence']=str(old/'inspection/composite-final33/independent-144-atlas.json');m['projections']['exterior']['occluder_constraints']=[dict(reviewed=True,source_node=f'building-{node}',receiver_nodes=['building-220'],mask_indices=[279,282,blocker_index],reason='Measured87-pixel wall-walk continuation is outside accepted neighboring wall masks279/282;379 falsely blocks85 rays. Preserve own geometry and every other blocker.',review_evidence=str(WORK/'round-34/assets'/old.name/'inspection/source-domain-audit/domains.json')) for node in [328,379]];(scope/'source-masks.json').write_text(json.dumps(m,indent=2)+'\n')
bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));c=json.loads((old/'workspace.json').read_text())
# Verify every newly admitted source pixel before projection or packet rendering.
import math
from mathutils import Vector
from refinement_review import _tree
from source_visibility import first_source_hit
from occlusion_constraints import SourceMaskConstraints
bpy.context.window.scene=bpy.data.scenes[c['scene_name']];bpy.context.view_layer.update()
obs=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];tree,owners,_=_tree(obs)
con=SourceMaskConstraints(scope/'source-masks.json','exterior',sha(old/'reference/source.png'),(2304,3520));sin,cos=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-cos,sin));receiver=next(o for o in obs if o.get('source_node')=='building-220' and o.name in json.loads((old/'modified/views.json').read_text())['object_names']);proof=[]
for x,y in pixels:
 origin=Vector((x+.5,-(y+.5)*sin,-(y+.5)*cos))+toward*10000
 hit,n,j,d=first_source_hit(tree,owners,origin,-toward,constraints=con,receiver=receiver,source_pixel=(x,y));first=owners[j] if j is not None else None
 assert first==receiver and con.allowed_pixel(receiver,x,y),(x,y,first.name if first else None)
 proof.append(dict(pixel=[x,y],first_node=first.get('source_node'),receiver_allowed=True))
print('PREFLIGHT: all87 added paving pixels visible on wall220',flush=True)
(scope/'preflight.json').write_text(json.dumps(dict(status='PASS',pixels=proof,source_masks_sha256=sha(scope/'source-masks.json')),indent=2)+'\n')
rw.prepare(new,asset_id=new.name,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=scope/'source-masks.json',width=512,height=448,context_padding=48,framing_padding=1.1)
(new/'inspection').mkdir(exist_ok=True);shutil.copy2(scope/'preflight.json',new/'inspection/paving-preflight.json');rw.modified(new)
from restore_foreign_uv_schema import restore_foreign_uv_schema
restore_foreign_uv_schema(new,apply=True)
shutil.copy2(old/'geometry-report.json',new/'geometry-report.json');source=Image.open(new/'reference/source.png').convert('RGB');box=(675,1505,742,1560);crop=source.crop(box).resize((536,440),Image.Resampling.NEAREST);overlay=crop.copy();d=ImageDraw.Draw(overlay)
for x,y in pixels:d.rectangle(((x-box[0])*8,(y-box[1])*8,(x-box[0]+1)*8-1,(y-box[1]+1)*8-1),outline='cyan')
comparison=Image.new('RGB',(1072,440));comparison.paste(crop,(0,0));comparison.paste(overlay,(536,0));comparison.save(new/'inspection/paving-wedge-source.png')
(new/'inspection/paving-wedge.json').write_text(json.dumps(dict(status='PASS',pixels=pixels,count=87,source_sha256=sha(new/'reference/source.png'),geometry_unchanged_from=sha(old/'model.blend'),reason='Wall-walk continuation on actual220 surface, outside separate stair footprint; complete-native135 and actual-atlas audit establishes ownership.'),indent=2)+'\n')
audit=run(new,new/'inspection/stored-material',render=True,export=False);assert audit['status']=='STRUCTURAL-PASS',audit['problems']
(new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=new.name,status='refinement-in-progress',recipe=str(Path(__file__).resolve())),indent=2)+'\n')
