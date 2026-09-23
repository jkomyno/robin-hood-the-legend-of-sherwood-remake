"""Align the exposed right platform foot to its source-artwork timber."""
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Vector
 import refinement_workspace as rw
 from refine_village_secondary import digest
 asset='nottingham-southwest-prison-road-props';old=WORK/'round-5/assets'/asset;new=WORK/'round-26/assets'/asset
 c=json.loads((old/'workspace.json').read_text())
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=384,context_padding=48,framing_padding=1.15)
 bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'))
 before={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'}
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and o.get('source_node')=='building-482')
 # The frame recipe stores the deck, two posts, three boards, then four feet.
 # The second foot is the exposed right-hand support (vertices56..63).
 assert len(obj.data.vertices)==112
 s=math.sin(math.radians(35));co=math.cos(math.radians(35));inv=obj.matrix_world.inverted();rows=[]
 for i in range(56,64):
  v=obj.data.vertices[i];p=obj.matrix_world@v.co;oldp=list(p);p.x+=712-724.53094;p.y-= (2323-2319.763)/s;v.co=inv@p
  rows.append(dict(vertex=i,before=oldp,after=list(p)))
 changed=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and before[o.name]!=digest(o)]
 assert changed==[obj.name],changed
 report=dict(asset_id=asset,changed_objects=changed,changed_vertices=rows,source_targets=dict(right_foot_center_top=[712,2294],right_foot_center_ground=[712,2323],uncertainty_pixels=2),changes=['Moved only the exposed right support foot inward to the painted timber; deck, uprights, crossboards, steps and other feet are unchanged.'],outside_objects_preserved=len(before)-1,limitations=['Concealed support depth remains inferred; the source-visible foot is measured to approximately two pixels.'])
 (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
 (new/'inspection').mkdir(exist_ok=True)
 rw.modified(new)
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 restore_foreign_uv_schema(new,apply=True)
 from PIL import Image,ImageDraw
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'))
 obj=bpy.data.objects[changed[0]]
 source=Image.open(new/'reference/source.png').convert('RGB');box=(630,2200,745,2350);crop=source.crop(box).resize((460,600),Image.Resampling.NEAREST)
 panels=[]
 for label,records in [('Source',None),('Before',[r['before'] for r in rows]),('After',[list(obj.matrix_world@obj.data.vertices[i].co) for i in range(56,64)])]:
  im=crop.copy();d=ImageDraw.Draw(im);d.text((4,4),label,fill='white')
  if records:
   points=[((p[0]-box[0])*4,(-p[1]*s-p[2]*co-box[1])*4) for p in records]
   for edge in obj.data.edges:
    a,b=edge.vertices
    if 56<=a<64 and 56<=b<64:d.line([points[a-56],points[b-56]],fill='cyan',width=2)
  panels.append(im)
 sheet=Image.new('RGB',(1380,600))
 for i,im in enumerate(panels):sheet.paste(im,(460*i,0))
 sheet.save(new/'inspection/foot-source-comparison.png')
 from audit_stored_materials import run
 audit=run(new,new/'inspection/stored-material',render=True,export=False)
 assert audit['status']=='STRUCTURAL-PASS',audit['problems']
 (new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=asset,status='refinement-in-progress',recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
