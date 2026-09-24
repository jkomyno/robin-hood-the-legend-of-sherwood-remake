"""Separate painted masonry ownership from the dovecote's thatch silhouette."""
import sys,json,hashlib,math,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-village-dovecote'
WALL=[(2038,3021),(2049,3027),(2058,3032),(2070,3036),(2080,3038),(2090,3036),(2101,3031),(2112,3029),(2134,3029),(2152,3030),(2170,3026),(2185,3018),(2201,3005),(2202,3020),(2203,3070),(2304,3070),(2304,3520),(0,3520),(0,3070),(2030,3070),(2031,3055),(2033,3045),(2035,3034)]
RIM_X={52:2209.9,53:2211.3,54:2211.2,55:2210.5,0:2209.1,1:2207.7,2:2205.8,3:2204.03,4:2199.33,5:2195.6,6:2191.65,7:2187.41,8:2182.71,9:2177.43,28:2035.8,29:2032.0,30:2029.5,31:2027.5,32:2026.5,33:2026.5,34:2025.5,35:2022.,36:2021.5,37:2022.5,38:2028.0,39:2034.0}
RIM_SOURCE_Y_OFFSET={37:-2.7,38:-3.8,8:.3,9:.6,10:.9,11:1.,12:1.1,13:1.1,14:.6}
SHOULDER_RISE_SOURCE={35: 10.7265, 36: 10.8323, 37: 11.0362, 38: 11.2858, 39: 9.7044, 40: 8.9004, 41: 9.3308, 42: 10.5473, 43: 12.4492, 44: 12.7484, 45: 11.918, 46: 11.2998, 47: 6.5419, 48: 2.8541, 49: 0.7552, 28: 0.5, 29: 1.0, 30: 2.0, 31: 3.5, 32: 5.5, 33: 7.5, 34: 9.5}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Vector
 from PIL import Image,ImageDraw,ImageChops
 from refinement_workspace import prepare,modified,_geometry
 from audit_stored_materials import run
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 old=WORK/'round-24/assets'/ASSET;out=WORK/'round-50/assets'/ASSET;scope=WORK/'dovecote-projection-audit/wall-authority-v7';scope.mkdir(parents=True,exist_ok=True)
 m=json.loads((old/'source-masks.json').read_text());ip=Path(m['mask_inventory']);inv=json.loads(ip.read_text());native=Image.new('L',(2304,3520));r=next(r for r in inv['masks']if r['index']==260);native.paste(Image.open(ip.parent/r['png']).convert('L'),tuple(r['box_top_left'][:2]));wall=Image.new('L',native.size);ImageDraw.Draw(wall).polygon(WALL,fill=255);wall=ImageChops.darker(wall,native)
 if not out.exists():
  wall.save(scope/'painted-masonry-native260.png')
  for r in inv['masks']:r['png']=str((ip.parent/r['png']).resolve());r['box_top_left']=r['box_top_left'][:2]
  index=max(r['index']for r in inv['masks'])+1;inv['masks'].append(dict(index=index,png='painted-masonry-native260.png',box_top_left=[0,0],box_size=list(native.size),mask_type='reviewed-native-intersection',description='Painted masonry silhouette intersected with native260; roof and landing retain original native ownership.'))
  (scope/'mask-inventory.json').write_text(json.dumps(inv,indent=2)+'\n');m['mask_inventory']=str(scope/'mask-inventory.json');(scope/'source-masks.json').write_text(json.dumps(m,indent=2)+'\n')
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));c=json.loads((old/'workspace.json').read_text());prepare(out,asset_id=ASSET,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=scope/'source-masks.json',width=c['width'],height=c['height'],context_padding=c['context_padding'],framing_padding=c['framing_padding'])
 else:bpy.ops.wm.open_mainfile(filepath=str(out/'baseline.blend'));index=max(r['index']for r in json.loads((scope/'mask-inventory.json').read_text())['masks'])
 bpy.context.view_layer.update();coll=bpy.data.collections['nottingham Working'];before={o.name:_geometry(o)for o in coll.all_objects if o.type=='MESH'};owned=[o for o in coll.all_objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==ASSET];body=next(o for o in owned if o.get('source_node')=='building-293');ring=[body.matrix_world@v.co for v in list(body.data.vertices)[56:112]];assert len(ring)==56;apex=Vector((2113.12,-5380.54,240.67));templates=[]
 for k in range(1,6):
  t=k/5
  for j,p in enumerate(ring):templates.append((apex.lerp(p,t)+Vector((0,0,3*4*t*(1-t))),j,max(0,(t-.4)/.6),t))
 for j,p in enumerate(ring):templates.append((p-Vector((0,0,3)),j,1.0,1.0))
 changed=[]
 for o in owned:
  if o.get('source_node')not in [f'building-{i}'for i in range(294,300)]:continue
  invmatrix=o.matrix_world.inverted();count=0
  for v in o.data.vertices:
   p=o.matrix_world@v.co
   if (p-apex).length<.001:continue
   q,j,weight,t=min(templates,key=lambda row:(p-row[0]).length)
   assert (p-q).length<.002,(o.name,v.index,(p-q).length)
   dx=(RIM_X.get(j,ring[j].x)-ring[j].x)*weight
   dy=-RIM_SOURCE_Y_OFFSET.get(j,0)/math.sin(math.radians(35))*weight
   dz=SHOULDER_RISE_SOURCE.get(j,0)*4*t*(1-t)/math.cos(math.radians(35))
   if abs(dx)+abs(dy)+abs(dz)>1e-7:v.co=invmatrix@(p+Vector((dx,dy,dz)));count+=1
  if count:changed.append(dict(object=o.name,vertices=count))
 assert all(_geometry(bpy.data.objects[n])==value for n,value in before.items()if n not in {r['object']for r in changed})
 mp=out/'source-masks.json';m=json.loads(mp.read_text());row=next(r for r in m['projections']['exterior']['assignments']if r.get('source_node')=='building-293');row.update(mask_indices=[index],review_note='Only traced painted masonry intersect native260; excluded thatch belongs to actual roof, external cast shadow and ground are not masonry.',review_evidence=str(out/'inspection/source-authority-trace.png'));mp.write_text(json.dumps(m,indent=2)+'\n')
 (out/'inspection').mkdir(exist_ok=True)
 for name in ['upper-shoulder-fit.json','upper-shoulder-fit-proposal.png','left-wall-boundary-proposal.png']:
  evidence=WORK/'dovecote-projection-audit'/name
  if evidence.exists():shutil.copy2(evidence,out/'inspection'/name)
 source=Image.open(old/'reference/source.png').convert('RGB');box=(2010,2920,2220,3170);im=source.crop(box).resize((630,750),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im);project=lambda p:(p.x,-p.y*math.sin(math.radians(35))-p.z*math.cos(math.radians(35)));display=lambda p:((p[0]-box[0])*3,(p[1]-box[1])*3);draw.line([display(p)for p in WALL+[WALL[0]]],fill='cyan',width=2)
 for j,x in RIM_X.items():p=ring[j].copy();p.x=x;q=display(project(p));draw.ellipse((q[0]-2,q[1]-2,q[0]+2,q[1]+2),fill='red')
 im.save(out/'inspection/source-authority-trace.png');source.crop(box).resize((630,750),Image.Resampling.NEAREST).save(out/'inspection/source-unmarked.png')
 report=dict(status='candidate-needs-complete-source-review',source_sha256=sha(old/'reference/source.png'),changed_roof_objects=changed,unchanged_objects=len(before)-len(changed),body_and_stairs_geometry_unchanged=True,wall_authority_polygon=WALL,roof_rim_x=RIM_X,roof_rim_source_y_offset=RIM_SOURCE_Y_OFFSET,shoulder_rise_source=SHOULDER_RISE_SOURCE,maximum_rim_displacement=max(abs(x-ring[j].x)for j,x in RIM_X.items()),manual_pixel_uncertainty=2,roof_masks_unchanged=[260],limitations=['Source edge classification and all eight saved-material views must be reviewed before geometry readiness. Geometry revision requires fresh user review before texture generation.'])
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));modified(out);restore_foreign_uv_schema(out);run(out,out/'inspection/stored-materials',render=True,export=False);report['model_sha256']=sha(out/'model.blend');(out/'projection-boundary-report.json').write_text(json.dumps(report,indent=2)+'\n');print('DOVECOTE_CANDIDATE',str(out),flush=True)
if __name__=='__main__':main()
