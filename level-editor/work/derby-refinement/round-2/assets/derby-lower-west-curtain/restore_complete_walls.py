"""Restore full closed wall meshes, leaving approved roofs/supports intact."""
import bpy, json, hashlib
from pathlib import Path
root=Path(bpy.data.filepath).parent
nodes={'building-023','building-025','building-042'}
targets={o['source_node']:o for o in bpy.data.objects if o.type=='MESH' and o.get('source_node') in nodes and 'modeled battlements' in o.name}
with bpy.data.libraries.load(str(root/'baseline.blend'),link=False) as (src,dst):
    dst.objects=[n for n in src.objects if n in {o.name for o in targets.values()}]
reports=[]
for source in dst.objects:
    target=targets[source['source_node']]
    oldverts=len(target.data.vertices);oldfaces=len(target.data.polygons)
    target.data=source.data.copy()
    target.matrix_world=source.matrix_world.copy()
    for key in ('lower_west_merlon_revision',):
        if key in target:del target[key]
    reports.append({'node':target['source_node'],'rejected_vertices':oldverts,'rejected_faces':oldfaces,'restored_vertices':len(target.data.vertices),'restored_faces':len(target.data.polygons)})
    bpy.data.objects.remove(source,do_unlink=True)
(root/'merlon-revision-retraction.json').write_text(json.dumps({'status':'RESTORED_BASELINE_WALLS_REVISION_PENDING','reason':'Entire wall bodies were mistakenly replaced with detached merlon boxes. Previous count and phase claims are unverified and withdrawn.','restored':reports},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'model.blend'))
