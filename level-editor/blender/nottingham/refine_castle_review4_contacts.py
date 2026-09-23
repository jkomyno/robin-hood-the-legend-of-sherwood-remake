"""Correct courtyard contact datums and source-traced symmetric entrance steps."""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def apply(asset):
 import bpy
 from mathutils import Vector
 from refine_castle_secondary import replace_mesh,entry_treads
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and not o.hide_render]
 targets={int(o['source_node'][9:]):o for o in objects};rows=[]
 if asset.endswith('upper-wall'):
  for o in objects:
   inv=o.matrix_world.inverted();count=0
   for v in o.data.vertices:
    p=o.matrix_world@v.co
    if p.z*C<99.99:p.z=100.00101/C;v.co=inv@p;count+=1
   rows.append(dict(source_node=o['source_node'],raised_base_vertices=count,contact_datum=100.00101))
  changes=['Raised buried wall and landing bottoms to the adjacent native courtyard elevation100; all crowns, visible upper edges and horizontal placement are unchanged.']
 elif asset.endswith('west-stair'):
  o=targets[351]
  # Individually observed right-hand pale tread bands, top to bottom.
  back_pixels=[(303,1210),(306,1224),(310,1240),(314,1255),(318,1271),(321,1286),(324,1301)]
  front_pixels=[(306,1215),(310,1229),(314,1245),(318,1260),(321,1276),(324,1291),(326,1306)]
  levels=[250,241,230,220,209,199,189]
  positions=[(x,y+z) for (x,y),z in zip(back_pixels,levels)]+[(326,1495)]
  profile=[(*positions[-1],100),(*positions[-1],179)]
  for i in reversed(range(7)):profile.extend([(*positions[i+1],levels[i]),(*positions[i],levels[i])])
  profile.extend([(303,1451.3,250),(303,1451.3,100)]);v=[]
  for dx,dy in [(-36,5),(0,0)]:
   for x,y,z in profile:v.append(Vector((x+dx,-(y+dy)/S,z/C)))
  n=len(profile);f=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  rows.append(dict(source_node='building-351',**replace_mesh(o,[o.matrix_world.inverted()@p for p in v],f),tread_back_pixels=back_pixels,tread_front_pixels=front_pixels,risers=7,lower_contact=179,upper_contact=250,tread_levels=levels,trace_uncertainty_pixels=2))
  for other in objects:
   if other==o:continue
   inv=other.matrix_world.inverted()
   for q in other.data.vertices:
    p=other.matrix_world@q.co
    if p.z*C<99.99:p.z=100.00101/C;q.co=inv@p
  changes=['Narrowed and steepened the seven-riser flight to the visible stair side edges, removing tread extensions beyond the artwork.','Closed concealed supports at courtyard100 instead of absolute0.']
 else:
  # A rectangular landing follows the portal axis. Both flanking flights have
  # matching depth and width, with shared corners preventing asymmetric wedges.
  a=Vector((533,1300));u=Vector((108,-38));v=Vector((32,32*108*S*S/38))
  landing=[a,a+u,a+u+.65*v,a+.86*u+v,a+.14*u+v,a+.65*v]
  center=a+u*.5
  outer=[center+(p-center)*1.13+(v*.20 if i not in [0,1] else Vector((0,0))) for i,p in enumerate(landing)]
  o=targets[373];inv=o.matrix_world.inverted();n=len(landing)
  vv=[inv@Vector((p.x,-p.y/S,z/C)) for z in [100,115] for p in landing]
  ff=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  rows.append(dict(source_node='building-373',**replace_mesh(o,vv,ff)))
  for node,indices in [(374,[3,4]),(375,[4,5,0]),(376,[1,2,3])]:
   o=targets[node];inv=o.matrix_world.inverted();vv=[]
   profile=[(0,100),(0,107.5),(.5,107.5),(.5,115),(1,115),(1,100)]
   for i in indices:
    for t,z in profile:
     p=outer[i]*(1-t)+landing[i]*t;vv.append(inv@Vector((p.x,-p.y/S,z/C)))
   ff=[tuple(reversed(range(6))),tuple(range((len(indices)-1)*6,len(indices)*6))]
   for j in range(len(indices)-1):
    for k in range(6):ff.append((j*6+k,j*6+(k+1)%6,(j+1)*6+(k+1)%6,(j+1)*6+k))
   rows.append(dict(source_node=f'building-{node}',**replace_mesh(o,vv,ff)))
  rows.append(dict(landing_native=[list(p) for p in landing],outer_native=[list(p) for p in outer],support=100,landing=115,symmetry='Exact reflection across the entrance depth axis, with matching chamfered front corners.'))
  changes=['Rebuilt the entrance landing as an axis-symmetric chamfered landing with equally expanded side flights and two continuous perimeter steps.','Corrected the landing underside to courtyard100 rather than subtracting100 from its115 top.']
 return dict(changes=changes,objects=rows,limitations=['Hidden support faces are inferred closed volumes terminating at the courtyard datum.','Source corner measurements have approximately two-pixel manual uncertainty; unknown and foreground-occluded surfaces remain neutral.'])
def main():
 sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
 acquire();from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,refinement_workspace as rw
 from refine_village_secondary import digest
 from refine_castle_secondary import sha
 asset=sys.argv[sys.argv.index('--')+1];old=WORK/f'round-{6 if asset.endswith("entry-steps") else 1}/assets'/asset;new=WORK/'round-23/assets'/asset
 config=json.loads((old/'workspace.json').read_text())
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=config['scene_name'],collection_name=config['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=448,context_padding=48,framing_padding=1.15)
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'));bpy.context.view_layer.update()
 before={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')!=asset};report=apply(asset)
 assert before=={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')!=asset}
 after={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'};apply(asset);assert after=={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'}
 report.update(asset_id=asset,previous_workspace=str(old),tooling=tooling,idempotence='PASS',outside_objects_preserved=len(before),recipe_sha256=sha(__file__))
 write(new/'geometry-report.json',report);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
 if '--preview' in sys.argv:return
 rw.modified(new)
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 restore_foreign_uv_schema(new,apply=True)
 write(new/'candidate.json',dict(version=1,asset_id=asset,status='refinement-in-progress',model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),recipe=str(Path(__file__).resolve())))
if __name__=='__main__':main()
