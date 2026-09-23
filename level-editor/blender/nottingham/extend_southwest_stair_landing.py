"""Recover the source-visible upper landing behind the southwest wall stair."""
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
 import refinement_workspace as rw
 from refine_village_secondary import digest
 from PIL import Image,ImageDraw
 asset='nottingham-southwest-wall-stair';old=WORK/'round-1/assets'/asset;new=WORK/'round-31/assets'/asset;c=json.loads((old/'workspace.json').read_text())
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=448,context_padding=48,framing_padding=1.9)
 bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'))
 before={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'}
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and not o.hide_render);name=obj.name
 assert len(obj.data.vertices)==76
 s=math.sin(math.radians(35));co=math.cos(math.radians(35));inv=obj.matrix_world.inverted();rows=[]
 # Extend the existing rear profile; every tread/riser vertex stays fixed.
 # The measured back-right landing corner is (725.5,1513.5) in the source image.
 for i in [0,1,38,39]:
  v=obj.data.vertices[i];p=obj.matrix_world@v.co;oldp=list(p);p.x+=725.5-736.12054;p.y-=(1673.501-1699.4706)/s;v.co=inv@p;rows.append(dict(vertex=i,before=oldp,after=list(p)))
 obj.data.update();changed=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and before[o.name]!=digest(o)];assert changed==[name]
 (new/'inspection').mkdir(exist_ok=True)
 report=dict(asset_id=asset,changed_objects=changed,changed_vertices=rows,source_targets=dict(back_right=[725.5,1513.5],front_right_existing=[738.2573,1544.1202],manual_uncertainty_pixels=2),changes=['Extended the stair upper landing 25.97 source pixels backward to receive the painted landing previously absent from the stair mesh.','Preserved all eighteen existing tread/riser pairs, lower foot and side footprint beyond the upper landing.'],outside_objects_preserved=len(before)-1,limitations=['The existing user-reviewed eighteen-step continuation and concealed lower structure are unchanged.','The landing back edge is inferred across its wall-occluded portion; visible right edge is measured from the artwork.'])
 (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));rw.modified(new)
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 restore_foreign_uv_schema(new,apply=True)
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'));obj=bpy.data.objects[name]
 source=Image.open(new/'reference/source.png').convert('RGB');box=(665,1495,755,1570);crop=source.crop(box).resize((540,450),Image.Resampling.NEAREST);panels=[]
 for label,prior in [('Source',None),('Before',True),('Actual saved landing',False)]:
  im=crop.copy();d=ImageDraw.Draw(im);d.text((4,4),label,fill='white')
  if prior is not None:
   pts=[]
   for i in [1,2,40,39]:
    p=list(obj.matrix_world@obj.data.vertices[i].co)
    if prior and i in [1,39]:p=next(row['before'] for row in rows if row['vertex']==i)
    pts.append(((p[0]-box[0])*6,(-p[1]*s-p[2]*co-box[1])*6))
   d.line(pts+[pts[0]],fill='cyan',width=2)
  panels.append(im)
 sheet=Image.new('RGB',(1620,450))
 for i,im in enumerate(panels):sheet.paste(im,(540*i,0))
 sheet.save(new/'inspection/landing-source-comparison.png')
 from audit_stored_materials import run
 audit=run(new,new/'inspection/stored-material',render=True,export=False);assert audit['status']=='STRUCTURAL-PASS',audit['problems']
 (new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=asset,status='refinement-in-progress',recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
