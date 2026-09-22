"""Closed approach-ramp envelopes and source-phased rounded stone coping."""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).resolve().parent))

def apply(workspace):
 import bpy
 from mathutils import Vector
 from refine_castle_secondary import replace_mesh,sha,write
 from refinement_workspace import _geometry,modified,initialize_working_masks
 from refine_castle_packets import apply_masks
 native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'];config=json.loads((workspace/'workspace.json').read_text());objects=list(bpy.data.collections[config['collection_name']].all_objects);targets=[o for o in objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']];before={o.name:_geometry(o) for o in objects}
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));rows=[]
 joints_left=[(890,1500),(910,1518),(930,1537),(950,1555),(974,1587),(999,1623.5),(1023,1656),(1046,1687),(1067,1717.5),(1086,1742.5)]
 joints_right=[(1005.5,1476.5),(1025.5,1496.5),(1045.5,1517.5),(1065.5,1547.5),(1087,1577.5),(1108.5,1606),(1130.5,1635.5),(1152.5,1667),(1177,1699)]
 for obj in targets:
  num=int(obj['source_node'][9:]);p=native[num]['points'];v=[];f=[]
  if num in [342,343,344,346,347,348]:
   # Opposite short edges define start/end; their midpoints retain source depth.
   pairs=[(0,1,3,2),(0,3,1,2)]
   a,b,d,e=min(pairs,key=lambda q:sum((p[q[i]]['x']-p[q[i+1]]['x'])**2+((p[q[i]]['y']-p[q[i+1]]['y'])/s)**2 for i in [0,2]))
   start=[p[a],p[b]];end=[p[d],p[e]]
   def center(pair):return (sum(z['x'] for z in pair)/2,sum(z['y']-z['z_top'] for z in pair)/2)
   A,B=center(start),center(end);dx,dy=B[0]-A[0],B[1]-A[1];length=math.hypot(dx,dy);joints=[]
   for x,y in joints_left if num in [342,343,344] else joints_right:
    t=((x-A[0])*dx+(y-A[1])*dy)/(length*length);dist=abs((x-A[0])*dy-(y-A[1])*dx)/length
    if .015<t<.985 and dist<15:joints.append(t)
   samples=[(0,0),(1,0)]
   for t in joints:samples += [(t-.6/length,0),(t,.6),(t+.6/length,0)]
   samples=sorted(samples);cross=11
   for t,drop in samples:
    edge=[{k:a[k]+t*(b[k]-a[k]) for k in ['x','y','z_top','z_bottom']} for a,b in zip(start,end)]
    v.extend([(edge[0]['x'],edge[0]['y'],edge[0]['z_bottom']),(edge[1]['x'],edge[1]['y'],edge[1]['z_bottom'])])
    for i in range(cross):
     q=1-i/(cross-1);v.append((edge[0]['x']+(edge[1]['x']-edge[0]['x'])*q,edge[0]['y']+(edge[1]['y']-edge[0]['y'])*q,edge[0]['z_top']+(edge[1]['z_top']-edge[0]['z_top'])*q-5+5*math.sin(math.pi*q)-drop))
   n=cross+2;f=[tuple(reversed(range(n))),tuple((len(samples)-1)*n+i for i in range(n))]
   for j in range(len(samples)-1):f.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
   detail={'change':'Rounded stone coping with measured joint phase','measured_joint_count':len(joints),'joint_fractions':joints,'cap_rise':5,'groove_depth':.6}
  else:
   n=len(p);v=[(q['x'],q['y'],q[z]) for z in ['z_bottom','z_top'] for q in p];f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)];detail={'change':'Close inherited ramp/deck face seams at native anchors'}
  inv=obj.matrix_world.inverted();result=replace_mesh(obj,[inv@Vector((x,-y/s,z/c)) for x,y,z in v],f);obj['castle_ramp_recipe']='rounded-source-phased-v1';rows.append({'source_node':obj['source_node'],**detail,**result})
 assert all(before[o.name]==_geometry(o) for o in objects if o not in targets)
 initialize_working_masks(workspace);apply_masks(workspace,WORK/'mask-review/castle-secondary-overrides-v11.json')
 write(workspace/'ramp-detail-report.json',{'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'changes':rows,'source_evidence':'castle-audit/ramp-source-measure.png','limitations':['Source-hidden undersides retain native depth anchors. Five-unit rounded cap section and shallow joint depth are inferred inside the measured silhouette.']})
 bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)

if __name__=='__main__':
 from freeze_tooling import select_tooling
 select_tooling()
 from render_slots import acquire
 acquire()
 import bpy
 w=WORK/'round-1/assets/nottingham-castle-approach-ramp';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));apply(w)
