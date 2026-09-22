"""Replace the hut's chimney wedge with a tapered, open-topped shaft.

The measured upper edge and original footprint remain fixed. Hidden shaft
returns and the shallow opening depth are explicitly inferred.
"""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-village-small-hut'
sys.path.insert(0,str(Path(__file__).resolve().parent))


def refine():
    import bpy
    from mathutils import Vector
    from refine_village_secondary import native,point,replace
    p=native(284)
    bottom=[point(v,66.189) for v in p]
    a=point(p[0],p[0]['z_top']);b=point(p[3],p[3]['z_top'])
    q=(bottom[1]-bottom[0])*.25
    top=[a,a+q,b+q,b]
    center=sum(top,Vector())/4
    inner=[center+(v-center)*.68 for v in top]
    lower=[v-Vector((0,0,6)) for v in inner]
    vertices=bottom+top+inner+lower
    faces=[(3,2,1,0),(12,13,14,15)]
    for i in range(4):
        j=(i+1)%4
        faces.extend([(i,j,4+j,4+i),(4+i,4+j,8+j,8+i),(8+i,8+j,12+j,12+i)])
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==ASSET and o.get('source_node')=='building-284')
    report=replace(obj,vertices,faces,'Small hut / tapered hollow chimney')
    report.update(recipe='tapered-hollow-chimney',inference=[
        'Chimney top depth is one quarter of its existing front-back footprint, constrained by the visible opening silhouette.',
        'Hidden wall thickness is 16 percent of the top width per side; opening depth is six world units.',
        'Shaft returns and roof-intersecting base close the visible masonry body; no internal flue continuation is claimed.'],
        observed_upper_edge_preserved=True,source_detail='village-secondary-audit/small-hut-detail.png')
    return report


def main():
    from render_slots import acquire
    acquire(slots=2)
    from freeze_tooling import select_tooling
    tooling=select_tooling(R/'tooling/315d227e98d52a78')
    import bpy
    from refinement_workspace import modified,initialize_working_masks
    from refine_village_secondary import digest
    workspace=R/'round-1/assets'/ASSET
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    def outside():return {o.name:(digest(o),[list(row) for row in o.matrix_world]) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')!=ASSET}
    before=outside();report=refine()
    if before!=outside():raise ValueError('Outside geometry changed')
    state=[(o.name,digest(o)) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==ASSET]
    refine()
    if state!=[(o.name,digest(o)) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==ASSET]:raise ValueError('Idempotence failed')
    report.update(outside_objects_preserved=len(before),idempotence='PASS',tooling=tooling,recipe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    (workspace/'geometry-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    initialize_working_masks(workspace)
    print(modified(workspace),flush=True)


if __name__=='__main__':main()
