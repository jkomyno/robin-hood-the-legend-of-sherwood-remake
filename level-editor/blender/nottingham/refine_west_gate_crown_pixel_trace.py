"""Fit all eight western gate capstones to independent source observations."""
import json,math,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from trace_west_gate_crown import CAPS
HEIGHT=357.59802
# Notch-floor observations at each outer start/end. None denotes an occluded corner.
FLOORS=[(1291,None),(None,None),(1235,1224),(1223,1228),(1235,1250),(None,None),(1290,1302),(1304,1301)]
def main():
 acquire();select_tooling(R/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from refinement_workspace import prepare,modified
 from refine_castle_secondary import replace_mesh
 from correct_source_projection import geometry
 old=R/'round-28/assets/nottingham-castle-gate-west-tower';w=R/'round-38/assets/nottingham-castle-gate-west-tower';c=json.loads((old/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();before=geometry()
 prepare(w,asset_id=c['asset_id'],scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=256,height=320,context_padding=35,framing_padding=1.1)
 native=json.loads((R/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][331]['points'];outer=native[:8];inner=[native[i]for i in [15,14,13,12,11,10,9,8]]
 def curve(ring,t):
  edge=int(t)%8;f=t%1
  return tuple(.5*(2*b+(-a+cc)*f+(2*a-5*b+4*cc-d)*f*f+(-a+3*b-3*cc+d)*f*f*f)for key in ['x','y']for a,b,cc,d in [[ring[i%8][key]for i in [edge-1,edge,edge+1,edge+2]]])
 def lower(ring,t):
  a=math.floor(t*8)/8;b=a+1/8;f=(t-a)*8;p=curve(ring,a);q=curve(ring,b)
  return tuple(p[i]+(q[i]-p[i])*f for i in range(2))
 samples=[(i/1000,curve(outer,i/1000))for i in range(8000)];knots=[];trace=[]
 for j,(name,outs,ins) in enumerate(CAPS):
  for k,(out,inside) in enumerate(zip(outs,ins)):
   x,y=out;t=min(samples,key=lambda e:math.dist(e[1],(x,y+HEIGHT)))[0];floor=FLOORS[j][k];drop=(floor-y)if floor is not None else 12
   point=dict(t=t,floor=HEIGHT-drop,outer=(x,y+HEIGHT),inner=(inside[0],inside[1]+HEIGHT))
   # Discontinuous heights share exact XY, yielding connected vertical shoulders.
   for z in ([HEIGHT-drop,HEIGHT]if k==0 else[HEIGHT,HEIGHT-drop]):knots.append(dict(**point,z=z))
   trace.append(dict(cap=name,endpoint=k,t=t,outer_source=list(out),inner_source=list(inside),notch_floor_source=[x,y+drop],notch_floor_visibility='measured'if floor is not None else'inferred: occluded',uncertainty_pixels=2))
 assert all(knots[i]['t']<=knots[i+1]['t']for i in range(len(knots)-1))
 def at(t):
  ext=[dict(knots[-1],t=knots[-1]['t']-8)]+knots+[dict(knots[0],t=knots[0]['t']+8)]
  for a,b in zip(ext,ext[1:]):
   if a['t']<=t<=b['t'] and a['t']!=b['t']:
    f=(t-a['t'])/(b['t']-a['t']);return dict(t=t,z=a['z']+(b['z']-a['z'])*f,floor=a['floor']+(b['floor']-a['floor'])*f,**{key:tuple(a[key][i]+(b[key][i]-a[key][i])*f for i in range(2))for key in ['outer','inner']})
  raise ValueError(t)
 # Include all old native spline sample positions, retaining lower wall curvature exactly.
 allknots=sorted(knots+[at(i/8)for i in range(65)if not any(abs(k['t']-i/8)<1e-8 for k in knots)],key=lambda k:k['t'])
 s,co=math.sin(math.radians(35)),math.cos(math.radians(35));changed=[];topology=[]
 for node,start,end in [(331,0,7),(332,7,8)]:
  obj=next(o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH'and o.get('asset_group')==c['asset_id']and o.get('source_node')==f'building-{node}');inv=obj.matrix_world.inverted();rows=[k for k in allknots if start<=k['t']<=end];verts=[];faces=[]
  # Ring sides run bottom outer, lower-wall shoulder outer, top outer, top inner, shoulder inner, bottom inner.
  for k in rows:
   lo=lower(outer,k['t']);li=lower(inner,k['t']);coords=[(*lo,0),(*lo,330.001),(*k['outer'],k['floor']),(*k['outer'],k['z']),(*k['inner'],k['z']),(*k['inner'],k['floor']),(*li,330.001),(*li,0)]
   verts.extend(inv@Vector((x,-y/s,z/co))for x,y,z in coords)
  # Weld coincident lower vertices on either side of the vertical notch risers.
  for i in range(len(rows)-1):
   for j in range(8):faces.append((i*8+j,i*8+(j+1)%8,(i+1)*8+(j+1)%8,(i+1)*8+j))
  faces.extend([tuple(range(7,-1,-1)),tuple((len(rows)-1)*8+j for j in range(8))]);replace_mesh(obj,verts,faces)
  bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);volume=bm.calc_volume(signed=True);assert volume>0;bm.to_mesh(obj.data);bm.free();changed.append(obj.name);topology.append(dict(node=node,volume=volume,vertices=len(obj.data.vertices),faces=len(obj.data.polygons)))
 after=geometry();assert {k:v for k,v in before.items()if k not in changed}=={k:v for k,v in after.items()if k not in changed}
 bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));modified(w);(w/'inspection').mkdir(exist_ok=True)
 report=dict(status='awaiting-independent-review',model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),previous_workspace=str(old),source_sha256=hashlib.sha256((w/'reference/source.png').read_bytes()).hexdigest(),cap_count=8,corners=trace,changed_nodes=[331,332],protected_other_geometry=len(before)-2,topology=topology,limitations=['Hidden notch-floor corners use twelve-unit rise inferred from adjoining measured notches.','Cap footprints derive from source corner pixels at retained native crown datum; hidden depth below the rim transitions into preserved lower-wall contours.'])
 (w/'crown-correction.json').write_text(json.dumps(report,indent=2)+'\n');(w/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=c['asset_id'],status='refinement-in-progress',geometry_reviewed=False,geometry_refined=True,inspected_views=[],recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
