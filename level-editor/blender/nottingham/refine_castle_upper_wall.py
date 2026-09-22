"""Round the upper-courtyard turret while preserving measured crown phase."""
import json,math,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).resolve().parent))

def geometry(native):
 from ribbon_crown import arc_ribbon_geometry
 pts=copy.deepcopy(native[360]['points']);oldpairs=[(0,15),(1,14),(2,13),(3,12),(4,11),(5,10),(6,9),(7,8)]
 measured={0:[(987,1001),(1028,1040),(1068,1081)],3:[(930,946)]};partial={1:[(.25,.72)],5:[(.15,.7)]};notches=[]
 for segment in range(7):
  cuts=list(partial.get(segment,[]));a,c=pts[oldpairs[segment][0]],pts[oldpairs[segment+1][0]]
  for x0,x1 in measured.get(segment,[]):cuts.append(tuple(sorted(((x0-a['x'])/(c['x']-a['x']),(x1-a['x'])/(c['x']-a['x'])))))
  notches.extend((segment+max(0,a),segment+min(1,b)) for a,b in cuts if a<b)
 def curve(side,segment,t):
  ring=[pts[p[side]] for p in oldpairs];a,b=ring[segment],ring[segment+1]
  if segment in [0,6]:return {k:a[k]+(b[k]-a[k])*t for k in ['x','y','z_top']}
  prev=ring[segment-1] if segment>1 else a;following=ring[segment+2] if segment<5 else b
  v={}
  for k in ['x','y']:
   ma=(b[k]-prev[k])/(2 if segment>1 else 1);mb=(following[k]-a[k])/(2 if segment<5 else 1)
   v[k]=(2*t**3-3*t*t+1)*a[k]+(t**3-2*t*t+t)*ma+(-2*t**3+3*t*t)*b[k]+(t**3-t*t)*mb
  v['z_top']=281.924;return v
 positions=sorted(set([i+j/12 for i in range(7) for j in range(12)]+[7.]+[x for pair in notches for x in pair]));points=[];pairs=[]
 for t in positions:
  segment=min(6,int(t));fraction=t-segment;pairs.append((len(points),len(points)+1));points += [curve(side,segment,fraction) for side in [0,1]]
 mids=[((points[a]['x']+points[b]['x'])/2,(points[a]['y']+points[b]['y'])/2) for a,b in pairs];lengths=[0.]
 for a,b in zip(mids,mids[1:]):lengths.append(lengths[-1]+math.dist(a,b))
 total=lengths[-1];lookup={t:l/total for t,l in zip(positions,lengths)}
 v,f=arc_ribbon_geometry(points,pairs,[(lookup[a],lookup[b]) for a,b in notches],base=0,notch_depth=13)
 return v,f,notches

def apply(workspace):
 import bpy
 from refine_castle_secondary_details import native_mesh
 from refinement_workspace import _geometry,modified
 from refine_castle_secondary import sha,write
 native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'];config=json.loads((workspace/'workspace.json').read_text());objects=list(bpy.data.collections[config['collection_name']].all_objects);target=next(o for o in objects if o.type=='MESH' and o.get('asset_group')==config['asset_id'] and o.get('source_node')=='building-360');before={o.name:_geometry(o) for o in objects}
 v,f,cuts=geometry(native);topology=native_mesh(target,v,f);target['castle_upper_curve_recipe']='source-anchor-hermite-v1'
 # Preserve the separately selectable lower landing while closing import seams.
 landing=next(o for o in objects if o.type=='MESH' and o.get('asset_group')==config['asset_id'] and o.get('source_node')=='building-362');p=native[362]['points'];n=len(p);v=[(q['x'],q['y'],q[z]) for z in ['z_bottom','z_top'] for q in p];f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)];native_mesh(landing,v,f)
 assert all(before[o.name]==_geometry(o) for o in objects if o not in [target,landing])
 write(workspace/'upper-curve-report.json',{'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'change':'Smooth paired turret contour through measured native anchors; retain six source-phased upper-wall/turret crenels','crenels':len(cuts),'original_path_intervals':cuts,'curved_samples_per_segment':12,**topology,'limitations':['Concealed arc thickness interpolates native anchors. Fine arrow-loop recesses and masonry joints remain source texture detail.']})
 bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)

if __name__=='__main__':
 from freeze_tooling import select_tooling
 select_tooling()
 from render_slots import acquire
 acquire()
 import bpy
 w=WORK/'round-1/assets/nottingham-castle-upper-wall';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));apply(w)
