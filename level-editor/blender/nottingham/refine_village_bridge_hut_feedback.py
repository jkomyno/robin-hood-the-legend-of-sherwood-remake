"""Repair reviewed western bridge paving ownership and forge chimney profile."""
import hashlib,json,math,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def authority(old):
 from PIL import Image,ImageDraw
 original=json.loads((old/'source-masks.json').read_text());src=Path(original['mask_inventory']).parent
 target=WORK/'mask-review/inventory-west-bridge-feedback-v1'
 if not target.exists():shutil.copytree(src,target)
 data=json.loads((src/'manifest.json').read_text());index=len(data['masks'])
 polygon=[(445,2980),(631,2900),(664,2921),(477,3003)]
 mask=Image.new('L',(2304,3520));ImageDraw.Draw(mask).polygon(polygon,fill=255);mask.save(target/f'{index:06}.png')
 data['masks'].append(dict(index=index,layer=-1,layer_index=-1,png=f'{index:06}.png',mask_type='authored-source-floor',box_top_left=[0,0],box_size=[2304,3520],obstacle_indices=[],source_sha256=sha(old/'reference/source.png'),source_polygons=[polygon],limitation='Conservative paving between parapets. Source-camera visibility additionally excludes the parapets and foreground.'))
 write(target/'manifest.json',data);original['mask_inventory']=str(target/'manifest.json')
 original['projections']['exterior']['assignments'].append(dict(source_node='building-280',projection_component='Western stream bridge / arch masonry and deck',mask_indices=[212,213,index],exclude_mask_indices=[216],exclusions_reviewed=True,reviewed=True,constraint_kind='reviewed-native-and-authored-deck',review_note='Native bridge masonry plus separately traced paving between parapets; only the arch/deck component receives the extra paving domain.'))
 out=WORK/'mask-review/source-masks-west-bridge-feedback-v1.json';write(out,original);return out

def chimney():
 import bpy
 from mathutils import Vector
 from refine_village_secondary import native,point,replace
 asset='nottingham-village-small-hut';obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==asset and o.get('source_node')=='building-284')
 # Traced source top corners: the upper shaft remains almost vertical while
 # the lower hood expands to meet its existing roof intersection.
 top_pixels=[(417.5,2759),(411.5,2765),(398,2761),(404,2755)]
 top_z=102.381004/C
 top=[Vector((x,(-y-top_z*C)/S,top_z)) for x,y in top_pixels]
 mid=[v-Vector((0,0,25/C)) for v in top]
 pts=native(284);bottom=[point(p,66.189) for p in pts]
 center=sum(top,Vector())/4;inner=[center+(v-center)*.66 for v in top];lower=[v-Vector((0,0,5)) for v in inner]
 vertices=bottom+mid+top+inner+lower;faces=[(3,2,1,0),(16,17,18,19)]
 for i in range(4):
  j=(i+1)%4
  faces.extend([(i,j,4+j,4+i),(4+i,4+j,8+j,8+i),(8+i,8+j,12+j,12+i),(12+i,12+j,16+j,16+i)])
 report=replace(obj,vertices,faces,'Forge chimney / vertical shaft and flared hood');obj['projection_min_cosine']=.05
 report.update(source_top_corners=top_pixels,upper_shaft_drop_pixels=25,changes=['Replaced continuously slanted chimney with a near-vertical upper shaft and lower flared hood.','Narrowed the mouth to the observed source silhouette; retained the native roof intersection.'],limitations=['Hidden shaft returns, rim thickness and five-unit shallow cavity are inferred.','Manual source trace uncertainty is approximately two pixels.'])
 return report

def main():
 sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,refinement_workspace as rw
 from refine_village_secondary import digest
 asset=sys.argv[sys.argv.index('--')+1];old=WORK/f'round-{5 if asset.endswith("stream-wall") else 1}/assets'/asset;new=WORK/'round-21/assets'/asset
 config=json.loads((old/'workspace.json').read_text());bridge=asset.endswith('stream-wall')
 if bridge:
  from western_bridge_projection import install
  install(rw)
 if not new.exists():
  masks=authority(old) if bridge else old/'source-masks.json'
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=config['scene_name'],collection_name=config['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=masks,width=384,height=448,context_padding=48,framing_padding=1.15)
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'));bpy.context.view_layer.update()
 def snap():return {o.name:(digest(o),[list(row) for row in o.matrix_world]) for o in bpy.context.scene.objects if o.type=='MESH'}
 before=snap();report=chimney() if not bridge else {'changes':['Added independently traced deck paving domain to the existing bridge deck component. Geometry remains unchanged.'],'geometry_refined':False}
 after=snap();outside=[k for k in before if before[k]!=after[k] and bpy.data.objects[k].get('asset_group')!=asset];assert not outside,outside
 if not bridge:chimney();assert after==snap(),'Non-idempotent recipe'
 report.update(asset_id=asset,previous_workspace=str(old),tooling=tooling,idempotence='PASS',outside_objects_preserved=sum(o.type=='MESH' and o.get('asset_group')!=asset for o in bpy.context.scene.objects),recipe_sha256=sha(__file__))
 write(new/'geometry-report.json',report);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));rw.modified(new)
 write(new/'candidate.json',dict(version=1,asset_id=asset,status='refinement-in-progress',model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),recipe=str(Path(__file__).resolve())))
if __name__=='__main__':main()
