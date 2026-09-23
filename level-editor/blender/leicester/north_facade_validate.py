"""Check the corrected church facade planarity, source anchors and closed stepped shells."""
import bpy,bmesh,json,sys,math
from pathlib import Path
w=Path(bpy.data.filepath).parent;r=json.loads((w/'facade-correction.json').read_text());left=r['facade_plane']['left'];right=r['facade_plane']['right'];slope=(right[1]-left[1])/(right[0]-left[0]);rows=[]
objects={o['source_node']:o for o in bpy.data.collections['Leicester Working'].all_objects if o.type=='MESH' and o.get('asset_group')=='leicester-church'}
for node,o in objects.items():
 bm=bmesh.new();bm.from_mesh(o.data);row={'source_node':node,'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces),'minimum_z':min((o.matrix_world@v.co).z for v in o.data.vertices)};bm.free();assert row['nonmanifold_edges']==row['degenerate_faces']==0;assert abs(row['minimum_z']-61.04)<.002;rows.append(row)
errors=[];roof_errors=[]
for node in ('building-355','building-356'):
 o=objects[node];vs=[o.matrix_world@v.co for v in o.data.vertices]
 for i in (0,1,4,5):
  p=vs[i];errors.append(abs(p.y-left[1]-(p.x-left[0])*slope))
 normal=(vs[1]-vs[0]).cross(vs[2]-vs[0]).normalized();roof_errors.append(abs((vs[3]-vs[0]).dot(normal)))
assert max(errors)<.002
assert max(roof_errors)<.002
result={'status':'PASS','components':rows,'facade_max_plane_error':max(errors),'roof_max_plane_error':max(roof_errors),'initial_flattening_max_source_pixel_drift':max(v['source_pixel_drift'] for v in r['facade_vertices']),'buttress_steps_per_side':2,'limitations':['Hidden buttress attachment depth is inferred; source upper profiles replaced intentionally to correct user-reported facade defects.']};(w/'geometry-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
