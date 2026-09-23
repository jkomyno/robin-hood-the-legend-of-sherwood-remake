"""Correct the source identities of the stream rock spur and courtyard shelter."""
import json,math,sys,hashlib
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
TAG='nottingham_identity_feedback_v4'
ROCK=[(2110,2451),(2118,2444),(2125,2447),(2130,2459),(2133,2467),(2139,2451),(2150,2436),(2158,2434),(2161,2440),(2157,2456),(2151,2471),(2144,2480),(2136,2486),(2128,2480),(2121,2476),(2116,2464)]
ROOF=[(625,2763),(657,2764),(697,2794),(665,2809)]
def pixel(p,z):return Vector((p[0],(-p[1]-z*C)/S,z))
def refine(asset):
 from refine_village_secondary import native,point,replace,digest
 n=235 if asset.endswith('stream-trough') else 260
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==asset and o.get('source_node')==f'building-{n}')
 if obj.get(TAG):return json.loads(obj[TAG])
 vertices=[];faces=[]
 def prism(poly,offset):
  start=len(vertices);count=len(poly);vertices.extend(poly+[p+offset for p in poly]);faces.extend([tuple(start+i for i in range(count)),tuple(start+count+i for i in reversed(range(count)))]);faces.extend([(start+i,start+(i+1)%count,start+(i+1)%count+count,start+i+count) for i in range(count)])
 if n==235:
  # The collision rectangle crosses the painted low ledge. Follow the
  # actual diagonal silhouette while leaving the adjoining upper cliff alone.
  front=[]
  for x,y in ROCK:
   ground_y=2490;wy=-ground_y/S
   front.append(Vector((x,wy,(ground_y-y)/C)))
  prism(front,Vector((0,C,-S))*18)
  changes=['Removed the invented trough cavity and rectangular basin rim.','Rebuilt the narrow low rock spur as a jagged ridge following 16 measured source silhouette points instead of the inaccurate collision rectangle.']
  inference=['The visible silhouette fixes the low ledge; its eighteen-unit concealed depth along the source viewing ray and rock face plane are inferred; the hidden extrusion preserves the full source silhouette.','Upper adjoining cliff and timber crossing belong to other assets and are not added.']
  label='Streamside low rock spur';trace=ROCK
 else:
  top=[pixel(p,z/C) for p,z in zip(ROOF,[44,46,42,42])]
  prism(top,Vector((0,0,-3.5)))
  # Narrow support timbers provide a readable open shelter, with no invented
  # solid walls where the source shows shadow and foreground wattle.
  center=sum(top,Vector())/4
  for p in top:
   p=p.lerp(center,.10);p.z-=3.5
   q=[Vector((p.x+dx,p.y+dy,0)) for dx,dy in [(-1.1,-1.1),(1.1,-1.1),(1.1,1.1),(-1.1,1.1)]]
   prism(q,Vector((0,0,p.z)))
  changes=['Replaced the invented round straw mound with a four-corner thatched shelter roof and open timber supports.','Traced the visible straight roof/eave edges; retained conservative straw-only ownership, excluding foreground wattle and foliage.']
  inference=['Four support timbers and underside thickness are structural inference; much of the shelter is hidden by foliage and wattle.','No solid walls, doorway, floor, or unseen interior furnishing is claimed.']
  label='Village courtyard thatched shelter';trace=ROOF
 report=replace(obj,vertices,faces,label);obj['projection_min_cosine']=.05
 report.update(status='refined',asset_id=asset,recipe='source-identity-correction',changes=changes,inference=inference,source_trace=trace,source_trace_uncertainty_pixels=2,source_fit_note='Trace targets are manual observations; target fit is construction evidence, not independent identification proof.')
 obj[TAG]=json.dumps(report);return report

def main():
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from refinement_workspace import prepare,modified
 from refine_village_secondary import digest
 operation,asset=sys.argv[sys.argv.index('--')+1:]
 old=WORK/('round-1' if asset.endswith('stream-trough') else 'round-5')/'assets'/asset
 w=WORK/'round-21/assets'/asset
 if operation=='prepare':
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  prepare(w,asset_id=asset,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=384,height=384,context_padding=55,framing_padding=2.0)
  (w/'tooling.json').write_text(json.dumps(tooling,indent=2)+'\n')
 else:
  bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update()
  def snapshot(outside=False):return {o.name:(digest(o),[list(row) for row in o.matrix_world],o.hide_render) for o in bpy.context.scene.objects if o.type=='MESH' and (not outside or o.get('asset_group')!=asset)}
  outside=snapshot(True);report=refine(asset);assert snapshot(True)==outside
  state=snapshot();refine(asset);assert state==snapshot()
  report.update(idempotence='PASS',outside_objects_preserved=len(outside),recipe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
  (w/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
  bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));modified(w)
if __name__=='__main__':main()
