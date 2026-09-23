"""Create a fixed-camera local terrain review packet using shared review helpers.

Ground is a canonical terrain receiver outside the building catalog. This
adapter frames only the local stream edit while preserving the entire map in
baseline/model files and ownership-ray context. Ground source pixels require
an explicit reviewed receiver assignment, or remain unknown.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
TOOLING = select_tooling()
from refinement_review import render_review
from review_sunlight import configuration
from setup_map import fit_camera
from refinement_workspace import _ownership, _files, _freeze_masks, validate
import refine_terrain


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def install_ground_source_material(ground, source_path, masks, output):
    """Store the explicit terrain ownership image without draping scenery."""
    from PIL import Image, ImageChops
    inventory_path=Path(masks['mask_inventory'])
    inventory=json.loads(inventory_path.read_text())
    entries={row['index']:row for row in inventory['masks']}
    assignment,=[row for row in masks['projections']['exterior']['assignments'] if row['source_node']=='ground']
    source=Image.open(source_path).convert('RGB')
    known=Image.new('L',source.size)
    for index in assignment['mask_indices']:
        row=entries[index]
        image=Image.open(inventory_path.parent/row['png']).convert('L')
        layer=Image.new('L',source.size)
        layer.paste(image,tuple(row['box_top_left']))
        known=ImageChops.lighter(known,layer)
    atlas=Image.new('RGB',source.size,(128,128,128))
    atlas.paste(source,mask=known)
    atlas.putalpha(known)
    folder=output/'projection';folder.mkdir(exist_ok=True)
    path=folder/'ground-source-owned.png';atlas.save(path)
    image=bpy.data.images.load(str(path),check_existing=False)
    # Ownership alpha is data, not transparency. Straight-alpha loading can
    # discard neutral RGB in alpha-zero texels during actual material rendering.
    image.alpha_mode='CHANNEL_PACKED';image.reload();image.pack()
    material=bpy.data.materials.new('Terrain / reviewed earth and grass source ownership')
    material.use_nodes=True
    material['source_ownership_bake']=True
    material['source_ownership_label']='exterior'
    material['source_ownership_fill']='neutral'
    material['source_ownership_alpha']='one=observed,zero=inferred;material remains opaque'
    material['projection_preserve']=True
    material['reprojection_source_sha256']=sha(source_path)
    nodes,links=material.node_tree.nodes,material.node_tree.links;nodes.clear()
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map=ground.data.uv_layers.active.name
    texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.interpolation='Closest'
    surface=nodes.new('ShaderNodeOutputMaterial')
    links.new(uv.outputs['UV'],texture.inputs['Vector'])
    links.new(texture.outputs['Color'],surface.inputs['Surface'])
    ground.data.materials.append(material)
    for face in ground.data.polygons:face.material_index=len(ground.data.materials)-1
    report={'status':'PASS','source_sha256':sha(source_path),'stored_atlas_sha256':sha(path),
            'receiver':ground.name,'uv_layer':uv.uv_map,
            'ownership_alpha':'observed source only; opacity remains opaque',
            'known_source_pixels':sum(1 for p in known.getdata() if p>127)}
    (folder/'ground-material.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-blend',required=True,type=Path)
    parser.add_argument('--source-image',required=True,type=Path)
    parser.add_argument('--source-masks',required=True,type=Path)
    authority=parser.add_mutually_exclusive_group(required=True)
    authority.add_argument('--unknown-mask-index',type=int)
    authority.add_argument('--reviewed-ground-assignment',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--frame-manifest',type=Path)
    parser.add_argument('--width',default=384,type=int)
    parser.add_argument('--height',default=384,type=int)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    from render_slots import acquire
    acquire()
    source=args.source_blend.resolve(strict=True)
    output=args.output.resolve()
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    reference=output/'reference';reference.mkdir()
    image=reference/'source.png';shutil.copy2(args.source_image,image)
    masks=json.loads(args.source_masks.read_text())
    masks['mask_inventory']=str((args.source_masks.resolve().parent/masks['mask_inventory']).resolve(strict=True))
    old_assignments=masks['projections']['exterior']['assignments']
    ground_assignments=[a for a in old_assignments if a.get('source_node')=='ground']
    if args.reviewed_ground_assignment:
        if len(ground_assignments)!=1 or not ground_assignments[0].get('reviewed') or not ground_assignments[0].get('mask_indices'):
            raise ValueError('Expected one explicit reviewed ground assignment')
    elif ground_assignments:
        raise ValueError('Ground already has an assignment; use --reviewed-ground-assignment')
    # Only ground is rendered. Other meshes participate exclusively as occluders.
    assignments=[]
    masks['projections']['exterior']['assignments']=assignments
    if args.reviewed_ground_assignment:
        assignments.extend(ground_assignments)
    else:
        assignments.append({'source_node':'ground','mask_indices':[args.unknown_mask_index],
                            'reviewed':True,'review_note':'No reviewed receiver-specific terrain source ownership; unknown remains neutral.'})
    mask_path=output/'source-masks.json';mask_path.write_text(json.dumps(masks,indent=2,sort_keys=True)+'\n')
    source_hash=sha(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.data.scenes['nottingham Refinement'];bpy.context.window.scene=scene
    objects=list(bpy.data.collections['nottingham Working'].all_objects)
    ground=next(obj for obj in objects if obj.type=='MESH' and obj.get('source_node')=='ground')
    ground['asset_group']='nottingham-terrain-ground'
    ground['asset_name']='Village bridge stream terrain'
    config={'version':1,'asset_id':'nottingham-terrain-ground','scene_name':scene.name,
            'collection_name':'nottingham Working','map_name':'nottingham','part_ids':['ground'],
            'source_blend':str(source),'source_blend_sha256':source_hash,'source_path':str(image),
            'source_mask_manifest':str(mask_path),'projection_manifest':None,
            'width':args.width,'height':args.height,'elevation_degrees':35,'context_padding':24,
            'terrain_role':'Separate canonical terrain receiver; outside building catalog',
            'tooling':TOOLING,'source_mask_parent_manifest':str(args.source_masks.resolve()),
            'source_mask_parent_sha256':sha(args.source_masks)}
    _,config['outside_geometry']=_ownership(config)
    _freeze_masks(output,config)
    outside={obj.name:(refine_terrain._hash(refine_terrain._geometry(obj)),[list(r) for r in obj.matrix_world])
             for obj in objects if obj.type=='MESH' and obj!=ground}
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'baseline.blend'),copy=True)
    config['baseline_sha256']=sha(output/'baseline.blend')
    # The local edit's complete before/after bounds define all eight fixed cameras.
    points=[]
    for x,y in [p for outer,inner in refine_terrain.BASINS for p in outer]:
        for z in (0,refine_terrain.DEPTH):
            points.append(Vector((x,(-y-z*refine_terrain.COSINE)/refine_terrain.SINE,z)))
    target=sum(points,Vector((0,0,0)))/len(points)
    views=[]
    for index in range(8):
        data=bpy.data.cameras.new('Terrain frozen framing')
        camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
        yaw=math.radians(index*45)
        camera.location=target+Vector((math.sin(yaw)*refine_terrain.COSINE,-math.cos(yaw)*refine_terrain.COSINE,refine_terrain.SINE))*10000
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        data.type='ORTHO';data.clip_end=100000
        fit_camera(camera,[ground],args.width/args.height,points=points,padding=1.1)
        views.append({'index':index,'camera_location':list(camera.location),
                      'camera_rotation_euler':list(camera.rotation_euler),'ortho_scale':data.ortho_scale})
        bpy.data.objects.remove(camera,do_unlink=True);bpy.data.cameras.remove(data)
    nodes=sorted({obj.get('source_node') for obj in objects if obj.type=='MESH' and not obj.hide_render})
    layers=[{'source_path':str(image),'projection_label':'exterior','receiver_nodes':nodes,'occluder_nodes':nodes}]
    framing={'version':1,'asset_id':'nottingham-terrain-ground','tile_size':[args.width,args.height],
             'elevation_degrees':35,'source_sha256':sha(image),'views':views,'lighting':configuration(),
             'context_crop':{'left':460,'top':2750,'right':1710,'bottom':3520},
             'projection_layers':[dict(layers[0],source_sha256=sha(image))],
             'framing':'Frozen local stream edit before/after bounds, all eight azimuths'}
    if args.frame_manifest:
        old=json.loads(args.frame_manifest.read_text())
        for key in ['views','tile_size','elevation_degrees','lighting','context_crop','framing']:
            framing[key]=old[key]
        config['framing_source']=str(args.frame_manifest.resolve())
        config['framing_source_sha256']=sha(args.frame_manifest)
    (output/'framing.json').write_text(json.dumps(framing,indent=2)+'\n')
    options=dict(scene_name=scene.name,collection_name='nottingham Working',asset_id='nottingham-terrain-ground',
                 source_path=image,projection_layers=layers,source_mask_manifest=mask_path)
    baseline=render_review(output/'input',frame_manifest=framing,**options)
    config['input_files']=_files(output/'input')
    config['reference_files']=_files(output/'reference')
    (output/'workspace.json').write_text(json.dumps(config,indent=2)+'\n')
    report=refine_terrain.refine()
    stored_material=install_ground_source_material(ground,image,masks,output) if args.reviewed_ground_assignment else None
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
    modified=render_review(output/'modified',frame_manifest=output/'input/views.json',**options)
    after={obj.name:(refine_terrain._hash(refine_terrain._geometry(obj)),[list(r) for r in obj.matrix_world])
           for obj in objects if obj.type=='MESH' and obj!=ground}
    if outside!=after or sha(source)!=source_hash:raise ValueError('Terrain worker changed outside geometry or frozen source')
    for a,b in zip(baseline['views'],modified['views']):
        if any(a[key]!=b[key] for key in ('camera_location','camera_rotation_euler','ortho_scale')):
            raise ValueError('Terrain comparison cameras differ')
    shared_validation=validate(output)
    validation={**shared_validation,'outside_objects_preserved':len(outside),
                'source_blend_sha256':source_hash,'baseline_sha256':sha(output/'baseline.blend'),
                'model_sha256':sha(output/'model.blend'),'source_image_sha256':sha(image),
                'fixed_cameras_preserved':True,'geometry':report,'tooling':TOOLING,
                'stored_ground_material':stored_material,
                'ownership':('Explicit reviewed terrain source assignment; native exclusions and scene visibility retained' if args.reviewed_ground_assignment else 'No approved terrain source pixels; known masks must remain empty'),
                'approval':'pending','texture_generation':'not started'}
    if not args.reviewed_ground_assignment and any(v['counts']['source'] for v in modified['views']+baseline['views']):
        raise ValueError('Unknown terrain mask permitted unreviewed source pixels')
    (output/'geometry-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    binding={**validation,'version':1,'input_files':_files(output/'input'),
             'reference_files':_files(output/'reference'),'modified_files':_files(output/'modified'),
             'workspace_sha256':sha(output/'workspace.json'),
             'recipe_sha256':sha(refine_terrain.__file__),'packet_script_sha256':sha(__file__),
             'argv':sys.argv,'accepted_known_pixels':sum(v['counts']['source'] for v in modified['views'])}
    (output/'terrain-packet.json').write_text(json.dumps(binding,indent=2)+'\n')
    print(json.dumps(validation))


if __name__=='__main__':main()
