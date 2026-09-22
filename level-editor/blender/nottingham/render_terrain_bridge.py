"""Render paired bridge/stream clearance close-ups with unchanged cameras."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
TOOLING=select_tooling()
from review_sunlight import render_solids,configuration
from setup_map import fit_camera
import refine_terrain
import refine_village


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    from render_slots import acquire
    acquire()
    workspace=args.workspace.resolve()
    output=workspace/'inspection/bridge-clearance'
    output.mkdir(parents=True,exist_ok=False)
    frame_records=[]
    clearance=None
    for state,file in [('input','baseline.blend'),('modified','model.blend')]:
        bpy.ops.wm.open_mainfile(filepath=str(workspace/file))
        scene=bpy.data.scenes['nottingham Refinement'];bpy.context.window.scene=scene
        sources={obj.get('source_node'):obj for obj in bpy.data.collections['nottingham Working'].all_objects if obj.type=='MESH'}
        result=refine_village._bridge(sources)
        bridge=bpy.data.objects[result['component']]
        objects=[sources['ground'],sources['building-290'],sources['building-291'],bridge]
        if state=='modified':clearance=refine_terrain.validate_bridge_clearance(sources['ground'],bridge)
        cameras=[];records=[]
        target=Vector((1485,-5465,-35))
        points=[Vector((x,(-y-z*refine_terrain.COSINE)/refine_terrain.SINE,z))
                for x,y in refine_terrain.OUTER for z in (0,refine_terrain.DEPTH)]
        scene.render.resolution_x=512;scene.render.resolution_y=384;scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=1
        for index,angle in enumerate([0,45,135]):
            data=bpy.data.cameras.new('Bridge clearance view');camera=bpy.data.objects.new(data.name,data)
            scene.collection.objects.link(camera);data.type='ORTHO';data.clip_end=100000
            yaw=math.radians(angle)
            camera.location=target+Vector((math.sin(yaw)*refine_terrain.COSINE,-math.cos(yaw)*refine_terrain.COSINE,refine_terrain.SINE))*10000
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            fit_camera(camera,objects,512/384,points=points,padding=1.15)
            cameras.append(camera);records.append({'angle':angle,'matrix_world':[list(row) for row in camera.matrix_world],'ortho_scale':data.ortho_scale})
        bpy.context.view_layer.update()
        # Capture evaluated matrices after dependency-graph update.
        for record,camera in zip(records,cameras):record['matrix_world']=[list(row) for row in camera.matrix_world]
        folder=output/state;folder.mkdir()
        render_solids(scene,cameras,objects,folder,lighting=configuration())
        frame_records.append(records)
    if frame_records[0]!=frame_records[1]:raise ValueError('Paired bridge cameras changed')
    (output/'evidence.json').write_text(json.dumps({'version':1,'cameras':frame_records[0],
        'camera_equality':True,'bridge_clearance':clearance,'tooling':TOOLING,
        'limitations':['Diagnostic bridge is rebuilt from the measured village recipe in memory.',
                       'Source texture ownership is not shown in this neutral solid comparison.',
                       'Bridge abutments outside the local stream remain embedded in unchanged banks.']},indent=2)+'\n')
    print(json.dumps({'output':str(output),'clearance':clearance}))


if __name__=='__main__':main()
