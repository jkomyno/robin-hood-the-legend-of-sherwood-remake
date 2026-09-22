"""South gate: pitched middle roof, two shed dormers, vertical rear timber panel."""
import copy,json,math
from pathlib import Path
import bpy
from mathutils import Vector
from refine_town import native_point
from refine_town_contacts import install
ROOT=Path(__file__).resolve().parents[3];SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35));TAG='southgate_pitched_roof_and_vertical_panel_v1'

def plane(points,x,y):
 a,b,c=[Vector((p['x'],p['y'],p['z_top']))for p in points[:3]];n=(b-a).cross(c-a)
 return a.z-(n.x*(x-a.x)+n.y*(y-a.y))/n.z

def refine():
 asset='nottingham-south-gate-house';objs={int(o['source_node'][-3:]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==asset}
 if objs[23].get(TAG):return json.loads(objs[23][TAG])
 src=json.loads((ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles'];p={i:copy.deepcopy(src[i]['points'])for i in [23,24,25,35]};before={i:objs[i].matrix_world.copy()for i in p};pitch=40.;ratio=math.tan(math.radians(pitch))*COS/SIN
 for rear,front in [(0,1),(3,2)]:
  a,b=p[23][rear],p[23][front];projected_run=(b['y']-b['z_top'])-(a['y']-a['z_top']);run=projected_run/(1+ratio);a['y']=b['y']-run;a['z_top']=b['z_top']+ratio*run
 # A gabled volume supplies the hidden back slope; visible slope keeps its
 # measured source polygon and has an explicit architectural pitch.
 front=[native_point(p[23][i],p[23][i]['z_top'])for i in [2,1,0]]
 back=[]
 for i,y in [(0,1959.2498),(3,1956.4249)]:
  q=p[23][i];back.append(native_point({'x':q['x'],'y':y},130.))
 top=front+back+[native_point(p[23][3],p[23][3]['z_top'])];bottom=[Vector((v.x,v.y,0))for v in top];faces=[tuple(reversed(range(6))),(6,7,8,11),(11,8,9,10)]
 for i in range(6):j=(i+1)%6;faces.append((i,j,j+6,i+6))
 reports=[install(objs[23],bottom+top,faces)]
 # Two broad shed dormers, each with an actual recessed vertical window bank.
 # Their source silhouettes remain identical to the measured native polygons.
 for idx,bays in [(24,4),(25,3)]:
  for q in p[idx]:q['y']+=6;q['z_top']+=6
  top=[native_point(q,q['z_top'])for q in p[idx]];bottom=[native_point(q,plane(p[23],q['x'],q['y'])-.5)for q in p[idx]]
  a,b=top[2],top[1];al,bl=bottom[2],bottom[1];inward=((top[0]+top[3]-top[1]-top[2])/2);inward.z=0;inward.normalize();vertices=[];faces=[]
  def face(v):
   start=len(vertices);vertices.extend(v);faces.append(tuple(range(start,len(vertices))))
  cuts=[0.]
  for i in range(bays):cuts.extend([(i+.10)/bays,(i+.88)/bays])
  cuts.append(1.)
  def at(t,row):
   lo=al.lerp(bl,t);hi=a.lerp(b,t)
   if row==0:return lo
   if row==1:return lo+Vector((0,0,1.8/COS))
   if row==2:return hi-Vector((0,0,2.2/COS))
   return hi
  for i,(lo,hi)in enumerate(zip(cuts,cuts[1:])):
   for row in range(3):
    quad=[at(lo,row),at(hi,row),at(hi,row+1),at(lo,row+1)]
    if i%2==1 and row==1:
     # Right bank middle bay is boarded in the source, so retains its face.
     depth=0.6 if idx==25 and i==3 else 4.0
     recessed=[v+inward*depth for v in quad];face(recessed)
     for j in range(4):k=(j+1)%4;face([quad[j],quad[k],recessed[k],recessed[j]])
    else:face(quad)
  face([at(t,3)for t in cuts]+[top[0],top[3]])
  face([at(t,0)for t in reversed(cuts)]+[bottom[3],bottom[0]])
  face([at(0,row)for row in range(4)]+[top[3],bottom[3]])
  face([at(1,row)for row in reversed(range(4))]+[bottom[0],top[0]])
  face([bottom[3],top[3],top[0],bottom[0]])
  reports.append(install(objs[idx],vertices,faces))
 # The timber rectangle is the back house's facade. Stand its four source
 # anchors vertically on that house's front plane, never on the middle roof.
 panel=[];pa,pb=src[35]['points'][3],src[35]['points'][0]
 for q in p[35]:
  source_y=q['y']-q['z_top'];q['y']=pa['y']+(q['x']-pa['x'])*(pb['y']-pa['y'])/(pb['x']-pa['x']);q['z_top']=q['y']-source_y;panel.append(native_point(q,q['z_top']))
 inward=Vector((0,2,0));verts=panel+[v+inward for v in panel];faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)];reports.append(install(objs[35],verts,faces));objs[35]['architectural_role']='Rear house vertical timber facade';objs[23]['architectural_role']='Middle house pitched roof and supporting volume'
 drift=max(abs((q['y']-q['z_top'])-(old['y']-old['z_top']))for i in p for q,old in zip(p[i],src[i]['points']))
 assert drift<1e-6 and all(objs[i].matrix_world==before[i]for i in p)
 for i in p:objs[i]['projection_min_cosine']=.18
 report={'status':'refined','asset_id':asset,'objects':reports,'dormer_count':2,'window_bays':[4,3],'middle_roof_pitch_degrees':pitch,'source_anchor_max_drift_pixels':drift,'transform_drift':0,'changes':['Restored a clearly pitched middle roof with40-degree front slope and a closed hidden rear slope; source roof polygon remains fixed.','Built two shed dormers with recessed window banks: four left bays and three right bays; the middle right bay remains boarded.','Moved timber panel035 onto the rear house as a vertical facade, preserving all four source anchors.'],'inference':['The40-degree pitch, hidden rear roof slope and four-world-unit window recess depth are architectural reconstructions constrained by the source silhouette and explicit user revision.','Ten canonical selectable parts remain within one complete south-gate building group. Panel035 is semantically assigned to the rear house; no catalog node ownership changes.'],'user_revision':'The middle house must have a sloped roof with dormer windows; the wooden panel belongs vertically to the back house.'}
 objs[23][TAG]=json.dumps(report);return report
