"""Apply an explicit reviewed face-material state without changing mesh surfaces.

Visibility belongs to the enclosing patch-state controller. This helper only
switches material slots whose UV maps and images already exist in the worker.
"""
import json
from pathlib import Path


def apply_material_state(objects, record, state):
    if isinstance(record, (str, Path)):
        record = json.loads(Path(record).read_text())
    if state not in ('covered', 'revealed'):
        raise ValueError('Material state must be covered or revealed')
    obj = objects.get(record['object'])
    if obj is None or obj.type != 'MESH':
        raise ValueError('Material-state receiver is absent')
    assignments = record[state + '_face_materials']
    if set(assignments) != {str(face.index) for face in obj.data.polygons}:
        raise ValueError('Material-state polygon inventory changed')
    planned = []
    for face in obj.data.polygons:
        assignment = assignments[str(face.index)]
        slot = assignment['slot']
        if type(slot) is not int or not 0 <= slot < len(obj.data.materials):
            raise ValueError('Material-state slot is absent')
        material = obj.data.materials[slot]
        if material is None or material.name != assignment['material']:
            raise ValueError('Material-state slot no longer names the reviewed material')
        planned.append((face, slot))
    # Validate the complete inventory before making the first mutation.
    for face, slot in planned:
        face.material_index = slot
    return {'object': obj.name, 'state': state, 'faces': len(planned)}


if __name__ == '__main__':
    import sys
    import bpy
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) != 3:
        raise ValueError('Expected -- state-record.json covered|revealed new-worker.blend')
    print(json.dumps(apply_material_state(bpy.data.objects, args[0], args[1])))
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args[2]).resolve()))
