"""Bind reviewed material and visibility alternatives into a covered worker.

Run with -- <handoff.json> <output.blend>. Visibility is read from the two
reviewed workers for the exact review-manifest objects, never sight obstacles.
"""
import hashlib
import json
from pathlib import Path
import sys
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from material_states import apply_material_state


def bind(handoff_path, output):
    handoff=json.loads(Path(handoff_path).read_text())
    record=json.loads(Path(handoff['state_record']).read_text())
    for key in ('worker','revealed_worker'):
        if hashlib.sha256(Path(handoff[key]).read_bytes()).hexdigest()!=handoff[key+'_sha256']:
            raise ValueError('Reviewed state worker changed')
    packet=json.loads(Path(handoff['review_manifest']).read_text())
    names=set(packet['object_names'])
    bpy.ops.wm.open_mainfile(filepath=handoff['revealed_worker'])
    revealed={name:bpy.data.objects[name].hide_render for name in names}
    bpy.ops.wm.open_mainfile(filepath=handoff['worker'])
    apply_material_state(bpy.data.objects,record,'revealed')
    apply_material_state(bpy.data.objects,record,'covered')
    obj=bpy.data.objects[record['object']]
    obj['reveal_material_states']=json.dumps({'version':1,'patch':record['state_trigger'],
        **{state:[record[state+'_face_materials'][str(face.index)]['slot'] for face in obj.data.polygons]
           for state in ('covered','revealed')}})
    covers=[]
    for name in names:
        source=bpy.data.objects[name]
        if source.hide_render and not revealed[name]:
            raise ValueError('State binding requires an explicitly exported inactive receiver: '+name)
        if not source.hide_render and revealed[name]:
            source['reveal_hide_when_applied']=[record['state_trigger']]
            covers.append(name)
    if not covers:
        raise ValueError('No reviewed covers found for patch state')
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(output).resolve()))
    report={'status':'PASS','patch':record['state_trigger'],'receiver':obj.name,'covers':sorted(covers),
            'source_handoff':str(Path(handoff_path).resolve()),'output':str(Path(output).resolve())}
    Path(output).with_suffix('.binding.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    bind(*sys.argv[sys.argv.index('--')+1:])
