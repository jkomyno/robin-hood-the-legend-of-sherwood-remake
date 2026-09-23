"""Restore closed wall winding and the wholly removable church tower front."""
import json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from towers import native_shell,write_mesh,split_mesh,diagnostics
w=Path(sys.argv[sys.argv.index('--')+1]).resolve();c=json.loads((w/'workspace.json').read_text())
if c['asset_id']!='leicester-church-side-tower':raise ValueError(c['asset_id'])
reports=[]
for o in bpy.data.collections[c['collection_name']].all_objects:
 if o.get('asset_group')!=c['asset_id'] or o.get('source_node') not in ['building-199','building-220']:continue
 v,f=native_shell(o)
 if o.get('source_node')=='building-199':
  o['projection_component']='tower-cover';o['reveal_component_patch_id']='patch-003';o['reveal_component_role']='removable-cover'
 else:v,f=split_mesh(v,f,1,-1494,o.get('projection_component')=='tower-retained')
 write_mesh(o,v,f,o.name+' closed wall');d=diagnostics(o)
 if d['nonmanifold_edges'] or d['degenerate_faces']:raise RuntimeError(str(d))
 reports.append(dict(object=o.name,mesh=d))
p=Path(c['projection_manifest']);m=json.loads(p.read_text());r=m['projection_reviews']['patch-003'];s={'source_node':'building-199','projection_component':'tower-cover','patch_id':'patch-003'}
for field in [r['exclude_occluder_components'],r['render_visibility']['revealed']['hidden_components']]:
 if s not in field:field.append(s)
selector={'source_node':'building-199','projection_components':['tower-cover'],'patch_id':'patch-003'}
if selector not in r['receiver_components']['exterior']:r['receiver_components']['exterior'].append(selector)
r['evidence']+='; Source199 is wholly in front of the measured ring center and is removed entirely in the reveal; closed source contour winding restored.'
p.write_text(json.dumps(m,indent=2)+'\n');(w/'inspection/church-wall-repair.json').write_text(json.dumps(reports,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
