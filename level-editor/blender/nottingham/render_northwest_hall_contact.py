"""Render a disposable paired roof/tower inspection without regrouping either asset."""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]


def main():
    import bpy
    from render_slots import acquire
    from refinement_review import render_review
    from audit_stored_materials import run
    from correct_spire_metal_ridges import sha
    parent = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    source = parent / 'paired-source-audit'
    output = parent / 'paired-visual-review'
    output.mkdir(exist_ok=False)
    acquire(slots=2)
    bpy.ops.wm.open_mainfile(filepath=str(source / 'model.blend'))
    config = json.loads((source / 'workspace.json').read_text())
    original_groups = {}
    for obj in bpy.data.collections[config['collection_name']].all_objects:
        if obj.type == 'MESH' and obj.get('asset_group') in ['nottingham-castle-main-hall', 'nottingham-castle-northwest-spire']:
            original_groups[obj.name] = obj['asset_group']
            obj['asset_group'] = 'nottingham-paired-hall-northwest-contact'
    config['asset_id'] = 'nottingham-paired-hall-northwest-contact'
    config['source_mask_manifest'] = str(source / 'source-masks.json')
    (output / 'workspace.json').write_text(json.dumps(config, indent=2) + '\n')
    (output / 'original-groups.json').write_text(json.dumps(original_groups, indent=2) + '\n')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'))
    render_review(output / 'modified', scene_name=config['scene_name'], collection_name=config['collection_name'],
                  asset_id=config['asset_id'], source_path=config['source_path'], width=512, height=512,
                  context_padding=25, framing_padding=1.08, lighting=config['lighting'],
                  source_mask_manifest=config['source_mask_manifest'])
    audit = run(output, output / 'actual', render=True, export=False)
    assert not audit['problems'], audit['problems']
    from mathutils import Matrix, Vector
    from PIL import Image, ImageDraw
    box = (245, 465, 318, 605)
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    toward, down = Vector((0, -cosine, sine)), Vector((0, -sine, -cosine))
    scene = bpy.context.scene
    camera = bpy.data.objects.new('Paired contact source camera', bpy.data.cameras.new('Paired contact source camera'))
    scene.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_end = 20000
    rotation = Matrix(((1, 0, 0), (0, sine, -cosine), (0, cosine, sine))).to_4x4()
    rotation.translation = Vector(((box[0]+box[2])/2, 0, 0)) + down*((box[1]+box[3])/2) + toward*10000
    camera.matrix_world = rotation
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = box[2]-box[0], box[3]-box[1]
    camera.data.ortho_scale = 1
    frame = camera.data.view_frame(scene=scene)
    scale_x = (box[2]-box[0]) / (max(v.x for v in frame)-min(v.x for v in frame))
    scale_y = (box[3]-box[1]) / (max(v.y for v in frame)-min(v.y for v in frame))
    assert abs(scale_x-scale_y) < 1e-3
    camera.data.ortho_scale = scale_x
    scene.render.filepath = str(output / 'source-actual.png')
    bpy.ops.render.render(write_still=True)
    source_image = Image.open(config['source_path']).convert('RGB').crop(box)
    actual_image = Image.open(output / 'source-actual.png').convert('RGB')
    comparison = Image.new('RGB', (source_image.width*2, source_image.height+18))
    draw = ImageDraw.Draw(comparison)
    for index, (panel, label) in enumerate([(source_image, 'Original art'), (actual_image, 'Paired saved model')]):
        comparison.paste(panel, (index*source_image.width, 18))
        draw.text((index*source_image.width+2, 2), label, fill='white')
    comparison.resize((comparison.width*4, comparison.height*4), Image.Resampling.NEAREST).save(output / 'source-comparison.png')
    (output / 'scope.json').write_text(json.dumps(dict(
        source_pair_sha256=sha(source / 'model.blend'), model_sha256=sha(output / 'model.blend'),
        purpose='Inspection-only display grouping; original canonical asset groups retained in original-groups.json.',
        geometry_and_materials_changed=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
