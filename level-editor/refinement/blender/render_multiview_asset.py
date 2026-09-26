"""Render the current asset with the exact cameras used for texture generation."""
import json
from pathlib import Path
import bpy
from mathutils import Matrix
import render_views
from texture_camera import depth_clip_range


def render(manifest_path, output_dir, modes=("textured",), width=384):
    manifest=json.loads(Path(manifest_path).read_text())
    scene=bpy.data.scenes[manifest.get('scene_name','Derby Refinement')]
    hidden=[(o,o.hide_render) for o in scene.objects if o.type=='MESH']
    from reviewed_texture_scope import displayed_objects
    selected=set(displayed_objects(manifest,[o for o,value in hidden if not value and o.get('asset_group')==manifest['asset_id']]))
    previous_size=(scene.render.resolution_x,scene.render.resolution_y)
    previous_scene=bpy.context.window.scene
    cameras=[];views={}
    try:
        bpy.context.window.scene=scene
        for obj,value in hidden:
            obj.hide_render=value or obj not in selected
        crop=manifest['views'][0]['crop']
        scene.render.resolution_x=crop['width'];scene.render.resolution_y=crop['height']
        bpy.context.view_layer.update()
        depsgraph=bpy.context.evaluated_depsgraph_get()
        points=[]
        for obj in selected:
            if obj.type=='MESH':
                evaluated=obj.evaluated_get(depsgraph)
                points.extend(evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices)
        for view in manifest['views']:
            data=bpy.data.cameras.new('Multiview review '+str(view['index']))
            data.type='ORTHO';data.ortho_scale=view['ortho_scale']
            # Excessive depth range can draw a hidden rear wall over a nearby
            # textured surface. Enclose every displayed vertex, with margin.
            inverse=Matrix(view['camera_matrix_world']).inverted()
            data.clip_start,data.clip_end=depth_clip_range(-(inverse @ point).z for point in points)
            camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
            camera.matrix_world=Matrix(view['camera_matrix_world']);cameras.append(camera)
            views['view-'+str(view['index'])]=camera.name
        return render_views.render_views(scene.name,views,output_dir,modes=modes,width=width)
    finally:
        for obj,value in hidden:obj.hide_render=value
        scene.render.resolution_x,scene.render.resolution_y=previous_size
        bpy.context.window.scene=previous_scene
        for camera in cameras:
            data=camera.data;bpy.data.objects.remove(camera,do_unlink=True);bpy.data.cameras.remove(data)
