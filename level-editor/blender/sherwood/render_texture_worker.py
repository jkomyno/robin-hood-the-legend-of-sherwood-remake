"""Inspect packed texture bytes on the real worker geometry, without saving edits."""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

EDITOR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EDITOR/'refinement'))
from render_slots import acquire


def main(worker, output):
    acquire()
    bpy.ops.wm.open_mainfile(filepath=str(Path(worker).resolve()))
    scene = bpy.data.scenes['Sherwood Editor Migration']
    bpy.context.window.scene = scene
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    replacements = {}
    for obj in bpy.data.collections['Sherwood Working'].objects:
        if obj.type != 'MESH':
            continue
        for slot in {face.material_index for face in obj.data.polygons}:
            original = obj.data.materials[slot]
            if original not in replacements:
                material = original.copy()
                nodes, links = material.node_tree.nodes, material.node_tree.links
                texture = next(n for n in nodes if n.type == 'TEX_IMAGE' and n.image)
                emission = nodes.new('ShaderNodeEmission')
                links.new(texture.outputs['Color'], emission.inputs['Color'])
                shader = emission.outputs[0]
                if original.get('foliage_physical_opacity'):
                    threshold = nodes.new('ShaderNodeMath')
                    threshold.operation = 'GREATER_THAN'
                    threshold.inputs[1].default_value = .499999
                    links.new(texture.outputs['Alpha'], threshold.inputs[0])
                    transparent = nodes.new('ShaderNodeBsdfTransparent')
                    mix = nodes.new('ShaderNodeMixShader')
                    links.new(threshold.outputs[0], mix.inputs[0])
                    links.new(transparent.outputs[0], mix.inputs[1])
                    links.new(shader, mix.inputs[2])
                    shader = mix.outputs[0]
                target = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
                links.new(shader, target.inputs['Surface'])
                replacements[original] = material
            obj.data.materials[slot] = replacements[original]
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.transparent_max_bounces = 128
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1088
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    camera = bpy.data.objects.new('Texture inspection camera', bpy.data.cameras.new('Texture inspection camera'))
    scene.collection.objects.link(camera)
    camera.data.type, camera.data.clip_end = 'ORTHO', 12000
    scene.camera = camera
    target = Vector((960, -544/math.sin(math.radians(35)), 0))
    for name, yaw, elevation, span in [('source', 0, 35, 1920), ('east', 40, 45, 2200), ('west', -40, 45, 2200)]:
        yaw, elevation = math.radians(yaw), math.radians(elevation)
        camera.location = target + Vector((math.sin(yaw)*math.cos(elevation),
                                           -math.cos(yaw)*math.cos(elevation), math.sin(elevation)))*3000
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = span
        scene.render.filepath = str(output/(name+'.png'))
        bpy.ops.render.render(write_still=True)
        print('RENDERED '+scene.render.filepath, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    main(args.worker, args.output)
