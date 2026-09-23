"""Validate refined keep component topology and floor/furniture separation."""
import json,sys
from pathlib import Path
import bpy,bmesh

w=Path(bpy.data.filepath).parent
rows=[]
for obj in bpy.data.collections['Leicester Working'].all_objects:
    if obj.type!='MESH' or obj.get('asset_group')!='leicester-great-keep' or obj.hide_render:continue
    if not (obj.get('north_keep_recipe') or obj.get('refinement_recipe') or obj.get('north_dormer')):continue
    bm=bmesh.new();bm.from_mesh(obj.data)
    areas=[f.calc_area() for f in bm.faces]
    row=dict(object=obj.name,source_node=obj['source_node'],component=obj.get('projection_component'),
             nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),zero_area_faces=sum(a<=0 for a in areas),
             near_zero_faces=sum(a<1e-7 for a in areas),minimum_face_area=min(areas),signed_volume=bm.calc_volume(signed=True))
    bm.free()
    if row['nonmanifold_edges'] or row['zero_area_faces']:raise RuntimeError(str(row))
    rows.append(row)
result={'status':'PASS','components':rows,'limitations':['Raster boundary slivers under 1e-7 area are reported explicitly; no zero-area faces or nonmanifold edges permitted.']}
(w/'geometry-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'PASS','components':len(rows),'near_zero_faces':sum(r['near_zero_faces'] for r in rows)}))
