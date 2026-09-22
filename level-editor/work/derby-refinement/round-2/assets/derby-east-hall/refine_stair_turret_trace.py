"""Correct observed outer notch shoulders/floors; retain concealed inner gap."""
import bpy,json,math
from pathlib import Path
W=Path(__file__).parent;D=W/'next-zigzag-v3'
o=next(o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render and o.get('source_node')=='building-198')
world=o.matrix_world.copy();inverse=world.inverted();changes=[]
for v in o.data.vertices:
    p=world@v.co;old=p.copy()
    if abs(p.z-451.0903)<.01:
        if p.x<1271:p.z=465.60
        elif p.y>-2030:p.z=462.65
    if p.z>=451 and abs(p.x-1263)<.12 and p.y>-2030:
        p.x+=1;p.y+=.872
    elif p.z>=451 and abs(p.x-1291.06)<.12 and p.y>-2030:
        p.x+=2;p.y-=2.296
    elif p.z>=451 and abs(p.x-1309.09)<.15 and p.y>-2030:
        p.x+=1;p.y-=1.148
    if (p-old).length>.00001:
        v.co=inverse@p;changes.append(dict(index=v.index,before=list(old),after=list(p)))
o.data.update()
o['stair_turret_trace']='Outer shoulder source x1264,1293,1310; outer floor levels fitted; inner stair-facing floor inherited'
bpy.ops.wm.save_as_mainfile(filepath=str(D/'traced-runs-candidate.blend'))
(D/'stair-trial-validation.json').write_text(json.dumps(dict(changes=changes,
  measured_source_corners='source-corners.json: stair-turret-silhouette',
  unresolved='Inner stair-facing gap floor is not part of native silhouette; retained pending separate internal-edge trace'),indent=2))
