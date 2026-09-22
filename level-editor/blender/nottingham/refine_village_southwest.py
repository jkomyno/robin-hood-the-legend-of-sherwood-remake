"""Close the southwest cottage rear roof without moving its measured front.

Run in Blender with -- [workspace]. Frozen framing includes the inferred rear
slope before either comparison packet is rendered. Source masks remain native.
"""
import json
import sys
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-village-southwest-cottage'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling


def shell():
    from mathutils import Vector
    from refine_village_secondary import native,point
    p=[point(v,v['z_top']) for v in native(272)]
    axis=p[3]-p[2];axis.z=0;axis.normalize()
    def reflect(v):
        d=v-p[2];d.z=0
        q=v+2*(axis*d.dot(axis)-d)
        return q
    p.extend(reflect(p[i]) for i in (0,1,4))
    boundary=[0,1,2,6,5,7,3,4]
    vertices=p+[Vector((p[i].x,p[i].y,0)) for i in boundary]
    faces=[(0,1,2,3,4),(2,6,5,7,3),tuple(reversed(range(8,16)))]
    faces.extend((boundary[i],8+i,8+(i+1)%8,boundary[(i+1)%8]) for i in range(8))
    return vertices,faces


def refine():
    import bpy
    from refine_village_secondary import replace
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.get('asset_group')==ASSET and o.get('source_node')=='building-272')
    vertices,faces=shell()
    result=replace(obj,vertices,faces,'Southwest cottage / closed rear cross-gable')
    result.update(recipe='reflected-rear-roof-and-closed-body',inference=[
        'Unseen rear slope reflects the measured front roof across its ridge in world XY; its eave heights match the observed front.',
        'Concealed rear walls continue to ground. No rear openings or decorations are inferred.',
        'The existing main-roof junction overlaps internally; canonical selectable source parts are retained.'],
        observed_front_vertices_preserved=5)
    return result


def main():
    from render_slots import acquire
    acquire(slots=2)
    tooling=select_tooling(R/'tooling/315d227e98d52a78')
    import bpy
    import refinement_review
    from refinement_workspace import prepare,modified
    from refine_village_secondary import digest
    workspace=Path(sys.argv[sys.argv.index('--')+1]).resolve() if '--' in sys.argv else R/'round-4/assets'/ASSET
    if not workspace.exists():
        bpy.ops.wm.open_mainfile(filepath=str(R/'grouped/nottingham-grouped-v5.blend'))
        old=refinement_review.fit_camera
        extra,_=shell()
        def fitted(camera,objects,aspect,*,points=None,padding=1.08):
            return old(camera,objects,aspect,points=list(points)+extra,padding=1.15)
        refinement_review.fit_camera=fitted
        prepare(workspace,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',
            source_path=R/'source-states/covered.png',grouping_manifest=R/'grouping/catalog-v5.json',inventory_path=R/'inventory/inventory-v2.json',
            review_path=R/'grouping/grouping-review-v5.json',source_mask_manifest=R/'mask-review/source-masks-v11-baseline.json',
            width=256,height=320,context_padding=24)
        refinement_review.fit_camera=old
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    def outside():return {o.name:(digest(o),[list(row) for row in o.matrix_world]) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')!=ASSET}
    before=outside();report=refine();after=outside()
    if before!=after:raise ValueError('Outside geometry changed')
    state=[(o.name,digest(o)) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==ASSET]
    refine()
    if state!=[(o.name,digest(o)) for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==ASSET]:raise ValueError('Recipe is not idempotent')
    report.update(outside_objects_preserved=len(before),idempotence='PASS',tooling=tooling,recipe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    (workspace/'geometry-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    print(modified(workspace),flush=True)


if __name__=='__main__':main()
