"""Open the hatch chute and retain only its three source-visible ladder rungs."""
import json,sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from towers import write_mesh,diagnostics
from towers_ladders import beam

def join_beams(beams):
 verts=[];faces=[]
 for a,b,w,d in beams:
  v,f=beam(a,b,w,d);n=len(verts);verts+=v;faces +=[tuple(i+n for i in face) for face in f]
 return verts,faces

def refine(workspace):
 c=json.loads((workspace/'workspace.json').read_text());objs={o.get('source_node'):o for o in bpy.data.collections[c['collection_name']].all_objects if o.get('asset_group')==c['asset_id']}
 if c['asset_id']!='leicester-northwest-tower':raise ValueError(c['asset_id'])
 top=Vector((810.6,-806.7,280.78));bottom=Vector((784.87,-874.2,170.86));width=Vector((18.9,-7.2,0));beams=[]
 for sign in [-1,1]:beams.append((top+sign*width/2,bottom+sign*width/2,2.4,3))
 for t in [.06,.145,.23]:
  p=top.lerp(bottom,t);beams.append((p-width/2,p+width/2,3,3))
 write_mesh(objs['building-330'],*join_beams(beams),'NW open ladder chute')
 corners=[Vector(v) for v in [(794.6,-877.9,280.8),(775.5,-870.7,280.8),(801.0,-803.4,280.8),(820.0,-810.5,280.8)]]
 write_mesh(objs['building-349'],*join_beams([(a,b,2,2) for a,b in zip(corners,corners[1:]+corners[:1])]),'NW hatch perimeter frame')
 p=Path(c['projection_manifest']);m=json.loads(p.read_text());r=m['projection_reviews']['patch-007']
 for key in ['receiver_nodes','covered_hidden_nodes']:
  if 'building-330' not in r[key]:r[key].append('building-330')
 if 'building-330' not in r['render_visibility']['covered']['hidden_nodes']:r['render_visibility']['covered']['hidden_nodes'].append('building-330')
 r['evidence']+='; Ray diagnostic identifies330 as sloped chute proxy blocking top rung; replaced by two rails and three visible rungs.349 becomes open perimeter frame.';p.write_text(json.dumps(m,indent=2)+'\n')
 report={'recipe':'nw-hatch-open-chute-v2','source_node_roles':{'building-330':'sloped ladder rails and three visible rungs','building-349':'open hatch perimeter frame'},'top_anchor':list(top),'bottom_anchor':list(bottom),'visible_rungs':3,'rung_fractions':[.06,.145,.23],'evidence':'nw-hatch-close.png and stored source330 top/bottom rail endpoints; rays at802,240 previously hit330 proxy first.','limitations':['Lower ladder rails continue to measured endpoint but hidden rungs are not invented.','Frame/rail thickness is inferred from narrow source contours.'],'mesh':{n:diagnostics(objs[n]) for n in ['building-330','building-349']}}
 (workspace/'inspection/hatch-ladder-v2.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
if __name__=='__main__':refine(Path(sys.argv[sys.argv.index('--')+1]).resolve())
