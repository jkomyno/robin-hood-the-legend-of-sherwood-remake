"""Render full-scene grouping checks and export exact mesh triangles for the gallery."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'level-editor/work/york-refinement'


def main():
    import bpy
    sys.path.insert(0,str(ROOT/'level-editor/refinement'))
    from render_slots import acquire
    acquire()
    sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'grouped/york-grouped.blend'))
    scene=bpy.data.scenes['york Refinement']
    bpy.context.window.scene=scene
    records={}
    for obj in bpy.data.collections['york Working'].objects:
        if obj.type!='MESH' or obj.hide_render:
            continue
        group=obj.get('asset_group','york-terrain')
        record=records.setdefault(group,{'name':obj.get('asset_name','York river and background terrain'),'parts':[]})
        obj.data.calc_loop_triangles()
        record['parts'].append({'source_node':obj['source_node'],
             'component':obj.get('projection_component'),
             'positions':[list(obj.matrix_world@v.co) for v in obj.data.vertices],
             'triangles':[list(t.vertices) for t in obj.data.loop_triangles]})
        color=hashlib.sha256(group.encode()).digest()
        obj.color=tuple(.18+.65*c/255 for c in color[:3])+(1,)
    output=OUT/'review'
    output.mkdir(exist_ok=True)
    (output/'geometry.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
    scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.color_type='OBJECT'
    scene.display.shading.light='STUDIO'
    scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True
    scene.display.shading.cavity_type='BOTH'
    scene.render.resolution_percentage=100
    scene.render.resolution_x=1600
    scene.render.resolution_y=1183
    scene.render.image_settings.file_format='PNG'
    for label in ['reference','east','west','plan']:
        scene.camera=bpy.data.objects['york '+label]
        scene.render.filepath=str(output/(label+'.png'))
        bpy.ops.render.render(write_still=True)
    print(json.dumps({'groups':len(records),'review':str(output)}))


if __name__=='__main__':
    main()
