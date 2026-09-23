"""Export reviewed face-material alternatives under one canonical editor part.

The alternatives share surface positions but retain their own UV/material
primitive partitioning. Only one is visible in the editor for a patch state.
"""
import json


def state_record(source):
    value = source.get('reveal_material_states')
    if not value:
        return None
    record = json.loads(value) if isinstance(value, str) else value
    if record.get('version') != 1 or not record.get('patch'):
        raise ValueError('Invalid patch material state record')
    faces = len(source.data.polygons)
    for state in ('covered', 'revealed'):
        slots = record.get(state)
        if not isinstance(slots, list) or len(slots) != faces:
            raise ValueError('Patch material face inventory changed')
        if any(type(slot) is not int or not 0 <= slot < len(source.data.materials)
               or source.data.materials[slot] is None for slot in slots):
            raise ValueError('Patch material slot is absent')
    return record


def export_states(source, mesh):
    record = state_record(source)
    if record is None:
        return [('default', mesh, {})]
    if len(mesh.polygons) != len(source.data.polygons):
        raise ValueError('Patch material export cannot change topology through modifiers')
    revealed = mesh.copy()
    for state, target in (('covered', mesh), ('revealed', revealed)):
        for face, slot in zip(target.polygons, record[state]):
            face.material_index = slot
    return [(state, target, {'reveal_material_patch': record['patch'], 'reveal_material_state': state})
            for state, target in (('covered', mesh), ('revealed', revealed))]
