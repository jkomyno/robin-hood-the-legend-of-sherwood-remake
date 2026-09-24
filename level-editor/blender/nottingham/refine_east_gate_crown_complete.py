"""Restore the eastern gate crown's eighth cap and source-visible rim."""
import json,math,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-castle-gate-east-tower';sys.path.insert(0,str(Path(__file__).parent))
# Outer and inner endpoints observed independently in the original source.
CAPS=[('left-front',[(971,1209),(957,1190)],[(985,1201),(968,1188)]),('left-side',[(957,1181),(965,1163)],[(970,1180),(976,1166)]),('rear-left',[(978,1152),(1007,1143)],[(988,1158),(1007,1152)]),('rear-center',[(1029,1140),(1057,1144)],[(1029,1150),(1052,1153)]),('rear-right',[(1074,1153),(1091,1168)],[(1066,1159),(1080,1171)]),('right-side',[(1098,1182),(1091,1196)],[(1085,1180),(1080,1189)]),('right-front',[(1080,1204),(1049,1217)],[(1071,1197),(1049,1207)]),('front-center',[(1027,1220),(997,1218)],[(1027,1210),(1005,1208)])]
def proposal():
 from PIL import Image,ImageDraw
 out=R/'castle-audit/east43-crown';out.mkdir(exist_ok=True);src=R/'round-42/assets'/ASSET/'reference/source.png';box=(945,1120,1110,1255);im=Image.open(src).convert('RGB').crop(box).resize((990,810),Image.Resampling.NEAREST);d=ImageDraw.Draw(im);rows=[]
 for j,(name,outer,inner) in enumerate(CAPS):
  points=outer+list(reversed(inner));px=[((x-box[0])*6,(y-box[1])*6)for x,y in points];d.line(px+[px[0]],fill='cyan',width=2)
  for k,((x,y),(sx,sy))in enumerate(zip(points,px)):
   number=j*4+k+1;d.ellipse((sx-3,sy-3,sx+3,sy+3),fill='yellow');d.text((sx+4,sy+2),str(number),fill='yellow',stroke_width=1,stroke_fill='black');rows.append(dict(number=number,cap=name,source_pixel=[x,y],role=['outer-start','outer-end','inner-end','inner-start'][k],uncertainty_pixels=2))
 im.save(out/'numbered-corners.png');Image.open(src).crop(box).resize((990,810),Image.Resampling.NEAREST).save(out/'source.png');(out/'trace.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),corners=rows,cap_count=8),indent=2)+'\n')
def main():
 from render_slots import acquire
 from freeze_tooling import select_tooling
 acquire();select_tooling(R/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from refinement_workspace import prepare,modified
 from correct_source_projection import geometry
 from refine_church import replace_native
 old=R/'round-42/assets'/ASSET;w=R/'round-43/assets'/ASSET;c=json.loads((old/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();before=geometry()
 prepare(w,asset_id=ASSET,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',projection_manifest=old/'projection-layers.json',source_mask_manifest=old/'source-masks.json',width=c['width'],height=c['height'],context_padding=c['context_padding'],framing_padding=c['framing_padding'])
 native=json.loads((R/'source-states/level.json').read_text())['sight_obstacles'][337]['points'];pairs=[(5,6),(4,7),(3,8),(2,9),(1,10),(0,11),(17,12),(16,13),(15,14)];cumulative=[0.]
 for(a,b),(cc,d)in zip(pairs,pairs[1:]):cumulative.append(cumulative[-1]+math.dist((native[a]['x'],native[a]['y']),(native[cc]['x'],native[cc]['y'])))
 def nearest(x,y):
  best=None
  for seg,((a,b),(cc,d))in enumerate(zip(pairs,pairs[1:])):
   A=native[a];B=native[cc];vx=B['x']-A['x'];vy=B['y']-A['y'];t=max(0,min(1,((x-A['x'])*vx+(y-A['y'])*vy)/(vx*vx+vy*vy)));q=(A['x']+t*vx,A['y']+t*vy);inner=(native[b]['x']+t*(native[d]['x']-native[b]['x']),native[b]['y']+t*(native[d]['y']-native[b]['y']));r=(math.dist(q,(x,y)),q,inner,cumulative[seg]+t*(cumulative[seg+1]-cumulative[seg]))
   if best is None or r[0]<best[0]:best=r
  return best[1:]
 # C-shaped shell starts at rear-center's left edge, travels around front, ends at right edge.
 ordered=[(CAPS[3][1][0],CAPS[3][2][0])]
 for cap in [CAPS[i]for i in [2,1,0,7,6,5,4]]:ordered.extend(zip(reversed(cap[1]),reversed(cap[2])))
 ordered.append((CAPS[3][1][1],CAPS[3][2][1]));sections=[]
 for out,inside in ordered:
  top=(out[0],out[1]+375);innertop=(inside[0],inside[1]+375);lo,li,t=nearest(*( (1029,1516)if out==ordered[0][0]else(1056,1518)if out==ordered[-1][0]else top));sections.append(dict(t=t,outer=lo,inner=li,top=top,itop=innertop))
 assert all(a['t']<b['t']for a,b in zip(sections,sections[1:])),[s['t']for s in sections]
 original=list(sections)
 for j,(a,b)in enumerate(pairs[1:-1],1):
  t=cumulative[j]
  for left,right in zip(original,original[1:]):
   if left['t']+1e-5<t<right['t']-1e-5:
    f=(t-left['t'])/(right['t']-left['t']);sections.append(dict(t=t,outer=(native[a]['x'],native[a]['y']),inner=(native[b]['x'],native[b]['y']),**{k:tuple(left[k][i]+f*(right[k][i]-left[k][i])for i in range(2))for k in ['top','itop']}));break
 sections.sort(key=lambda s:s['t']);owned=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH'and o.get('asset_group')==ASSET];upper=next(o for o in owned if o.get('projection_component')=='mechanism-upper');rear=next(o for o in owned if o.get('source_node')=='building-338')
 # Measured right stone silhouette guides the supporting ring, preserving the lower235 datum.
 silhouette=[(1180,1098),(1200,1096),(1215,1092),(1230,1085),(1245,1080)]
 def edge(y):
  if y<=silhouette[0][0]:return silhouette[0][1]
  if y>=silhouette[-1][0]:return silhouette[-1][1]
  for(y0,x0),(y1,x1)in zip(silhouette,silhouette[1:]):
   if y0<=y<=y1:return x0+(x1-x0)*(y-y0)/(y1-y0)
 def point(s,inner,z):
  key='inner'if inner else'outer';top='itop'if inner else'top'
  if z<=315:xy=s[key]
  elif z>=362:xy=s[top]
  else:
   f=(z-315)/(362-315);xy=tuple(s[key][i]+(s[top][i]-s[key][i])*f for i in range(2))
   outy=s['outer'][1]+(s['top'][1]-s['outer'][1])*f
   if s['top'][0]>=1090:
    outx=s['outer'][0]+(s['top'][0]-s['outer'][0])*f;desired=min(s['top'][0],edge(outy-z));xy=(xy[0]+desired-outx,xy[1])
  return(*xy,z)
 def mesh(rows,base,allhigh=False):
  verts=[];indices={};faces={}
  def face(ps):
   ids=[]
   for p in ps:
    p=tuple(round(q,5)for q in p)
    if p not in indices:indices[p]=len(verts);verts.append(p)
    ids.append(indices[p])
   key=tuple(sorted(ids))
   if key in faces:del faces[key]
   else:faces[key]=tuple(ids)
  def cell(a,b,z0,z1):
   p=[point(a,0,z0),point(b,0,z0),point(b,1,z0),point(a,1,z0),point(a,0,z1),point(b,0,z1),point(b,1,z1),point(a,1,z1)]
   for ids in[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:face([p[i]for i in ids])
  for a,b in zip(rows,rows[1:]):
   for z0,z1 in zip([base,315,345],[315,345,362]):cell(a,b,z0,z1)
   mid=(a['t']+b['t'])/2;interval=next((j for j,(l,r)in enumerate(zip(original,original[1:]))if l['t']-1e-5<=mid<=r['t']+1e-5),0)
   if allhigh or interval in[1,3,5,7,9,11,13]:cell(a,b,362,375)
  return verts,list(faces.values())
 v,f=mesh(sections,235);replace_native(upper,v,f);v,f=mesh([sections[0],sections[-1]],110,True);replace_native(rear,v,f);topology=[]
 for obj in[upper,rear]:
  bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);vol=bm.calc_volume(signed=True);assert vol>0;bm.to_mesh(obj.data);bm.free();obj['measured_merlon_count']=8;topology.append(dict(name=obj.name,volume=vol,nonmanifold_edges=0,degenerate_faces=0))
 changed={upper.name,rear.name};after=geometry();assert {k:v for k,v in before.items()if k not in changed}=={k:v for k,v in after.items()if k not in changed};bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));modified(w);(w/'inspection').mkdir(exist_ok=True)
 report=dict(status='awaiting-independent-review',previous_workspace=str(old),model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),changed_objects=list(changed),changed_components=[dict(source_node=337,projection_component='mechanism-upper'),dict(source_node=338)],outside_geometry_preserved=len(before)-2,measured_cap_count=8,trace=str(R/'castle-audit/east43-crown/trace.json'),right_silhouette=silhouette,topology=topology,limitations=['Cap corner manual uncertainty2 pixels. Supporting ring depth between unchanged lower footprint and observed cap contours is inferred.','Notch-floor height362 is retained; cap height375 unchanged.'])
 (w/'crown-correction.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
 if '--proposal'in sys.argv:proposal()
 else:main()
