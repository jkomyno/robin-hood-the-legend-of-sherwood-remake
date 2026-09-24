"""Restore source-visible courtyard paving, coping and masonry with foreground separation."""
import sys,json,hashlib,shutil
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';old=WORK/'round-38/assets/nottingham-castle-west-courtyard-wall';new=WORK/'round-39/assets'/old.name
scope=WORK/'mask-review/courtyard-visible-domains';scope.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((old/'source-masks.json').read_text());path=Path(m['mask_inventory']);inventory=json.loads(path.read_text());size=(2304,3520)
def native(index):
 row=next(r for r in inventory['masks'] if r['index']==index);mask=Image.new('L',size);mask.paste(Image.open(path.parent/row['png']).convert('L'),tuple(row['box_top_left']));return mask
# These source-traced crown limits supplement sparse native foreground leaf masks.
# The native masks omit the orange upper crown above y1539; never paint it onto masonry.
left_crown=[(226,1597),(234,1578),(243,1573),(245,1545),(264,1542),(281,1549),(289,1543),(302,1548),(309,1553),(322,1546),(329,1533),(342,1526),(348,1520),(357,1516),(369,1519),(379,1511),(388,1507),(400,1519),(408,1513),(418,1516),(428,1512),(437,1504),(447,1507),(445,1518),(431,1524),(427,1532),(420,1540),(414,1547),(422,1556),(445,1549),(457,1549),(471,1541),(482,1543),(493,1555),(493,1704),(226,1704)]
right_crown=[(563,1570),(579,1587),(584,1592),(596,1594),(599,1602),(610,1597),(617,1606),(626,1603),(637,1611),(650,1610),(674,1640),(697,1704),(553,1704)]
foreground=Image.new('L',size);draw=ImageDraw.Draw(foreground)
for poly in [left_crown,right_crown]:draw.polygon(poly,fill=255)
for index in [377,415,422,133,135,65,67]:foreground=ImageChops.lighter(foreground,native(index))
wall=ImageChops.subtract(native(278),foreground)
for row in inventory['masks']:row['png']=str((path.parent/row['png']).resolve())
index=max(row['index'] for row in inventory['masks'])+1;wall.save(scope/'wall-visible278.png');foreground.save(scope/'foreground.png');inventory['masks'].append(dict(index=index,layer=-1,layer_index=-1,png='wall-visible278.png',box_top_left=[0,0],box_size=list(size),mask_type='reviewed-source-wall-minus-foreground',source_sha256=sha(old/'reference/source.png')))
(scope/'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n');m['mask_inventory']=str(scope/'manifest.json')
for a in m['projections']['exterior']['assignments']:
 node=a['source_node']
 if node in ['building-327','building-328','building-379']:
  a.update(mask_indices={'building-327':[280,283],'building-328':[279,282,index],'building-379':[279]}[node],reviewed=True,native_ownership_reviewed=True,constraint_kind='reviewed-native-silhouette',review_note='Independent source-face audit:327 walkway283+280,379 coping279,328 masonry278 minus explicit foreground/native silhouettes. Existing geometry preserved.',review_evidence=str(WORK/'coordinator-audit/props/westwall-walkway-source.png'));a.pop('accepted_source_pixels',None)
(scope/'source-masks.json').write_text(json.dumps(m,indent=2)+'\n');(scope/'trace.json').write_text(json.dumps(dict(source_sha256=sha(old/'reference/source.png'),foliage_crown_polygons=[left_crown,right_crown],uncertainty_pixels=3,native_foreground_masks=[377,415,422,133,135,65,67],reason='Conservative source-visible masonry boundary around foreground foliage; retain leaf silhouettes and foreground structures.'),indent=2)+'\n')
source=Image.open(old/'reference/source.png').convert('RGB');box=(220,1420,810,1720);crop=source.crop(box);overlay=crop.copy();tint=Image.new('RGB',crop.size,'cyan');overlay=Image.blend(overlay,Image.composite(tint,overlay,wall.crop(box)),.35);canvas=Image.new('RGB',(1180,300));canvas.paste(crop,(0,0));canvas.paste(overlay,(590,0));canvas.save(scope/'source-visible-domain.png')
if '--preview' in sys.argv:sys.exit(0)
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
import refinement_workspace as rw
from audit_stored_materials import run
bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));c=json.loads((old/'workspace.json').read_text())
rw.prepare(new,asset_id=old.name,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=scope/'source-masks.json',width=384,height=448,context_padding=150,framing_padding=1.08)
(new/'inspection').mkdir(exist_ok=True);rw.modified(new)
from restore_foreign_uv_schema import restore_foreign_uv_schema
restore_foreign_uv_schema(new,apply=True)
for name in ['support-recovery.json','native352-first-hits.json','identity-source-comparison.png']:shutil.copy2(old/'inspection'/name,new/'inspection'/name)
for name in ['source-visible-domain.png','trace.json']:shutil.copy2(scope/name,new/'inspection'/name)
audit=run(new,new/'inspection/stored-material',render=True,export=False);assert audit['status']=='STRUCTURAL-PASS',audit['problems']
(new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=new.name,status='refinement-in-progress',geometry_refined=False,geometry_reviewed=False,recipe=str(Path(__file__).resolve()),model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json')),indent=2)+'\n')
