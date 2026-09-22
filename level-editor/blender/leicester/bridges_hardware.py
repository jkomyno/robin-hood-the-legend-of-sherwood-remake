"""Measured south drawbridge lifting beams and chains, without packet renders.

Endpoint silhouettes establish projected anchors. Hinge elevation, timber
section and reverse depth are explicit geometric hypotheses, not source facts.
"""
import hashlib
import json
import math
from pathlib import Path

TAG = 'south-lifting-hardware-v1'
ASSET = 'leicester-south-drawbridge'
SINE, COSINE = math.sin(math.radians(35)), math.cos(math.radians(35))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def refine_hardware(workspace, asset_id, state):
    import bpy
    from mathutils import Vector
    from bridges import beam

    if asset_id != ASSET or state not in ('initial', 'applied'):
        raise ValueError('South hardware recipe requires its explicit endpoint')
    workspace = Path(workspace).resolve()
    root = next((p for p in workspace.parents if p.name == 'leicester-refinement'), None)
    if root is None:
        raise ValueError('Cannot resolve frozen Leicester evidence')
    config = json.loads((workspace / 'workspace.json').read_text())
    if config['asset_id'] != asset_id:
        raise ValueError('Wrong hardware workspace')
    collection = bpy.data.collections[config['collection_name']]
    node = 'building-391' if state == 'initial' else 'building-390'
    targets = [o for o in collection.all_objects if o.type == 'MESH' and o.get('asset_group') == asset_id]
    templates = [o for o in targets if o.get('source_node') == node and not o.get('bridge_hardware_generated')]
    if len(templates) != 1:
        raise ValueError('Expected one canonical active leaf template')
    template = templates[0]
    states_file = root / 'bridge-evidence/native-states/states.json'
    patch = next(p for p in json.loads(states_file.read_text())['patches'] if p['id'] == 'patch-010')
    graphic = patch[state + '_graphic']
    native_file = root / 'source-audit/Leicester.rhp.json'
    native = json.loads(native_file.read_text())
    lower_height = native['sight_obstacles'][391 if state == 'initial' else 390]['points'][0]['z_top']
    masks = [459, 460] if state == 'initial' else [453, 454]
    # The native masks are already frozen in the endpoint inventories. All
    # initial pixels lie inside sprite alpha. Applied outside-alpha pixels are
    # only x742 / x802; those unsupported wall-end columns receive no geometry.
    additions = [o for o in targets if o.get('bridge_hardware_generated') == TAG]
    expected = {f'south {state} lifting beam {n}' for n in (1, 2)} | {
        f'south {state} chain {n}' for n in (1, 2)}
    if additions and {o.get('projection_component') for o in additions} != expected:
        raise ValueError('Incomplete previous hardware revision; preserve for diagnosis')
    reused = bool(additions)
    specifications = []
    # Source-coordinate centre anchors measured on endpoint sprites. Hidden
    # hinge height150game places the applied beam approximately horizontal.
    for side, mask in enumerate(masks):
        ox, oy = side*60, side*20
        hinge = (739.+ox, 1283.+oy)
        if state == 'initial':
            tip, top, bottom = (716.+ox, 1225.+oy), (715.+ox, 1233.+oy), (724.+ox, 1318.+oy)
            # Continue the lowered lever's native plan direction while raised.
            tip_height = 150. + (hinge[0]-tip[0])*55./53. + hinge[1]-tip[1]
        else:
            tip, top, bottom = (686.+ox, 1338.+oy), (690.+ox, 1341.+oy), (683.+ox, 1438.+oy)
            tip_height = 150.
        def point(pixel, height):
            return Vector((pixel[0], -(pixel[1]+height)/SINE, height/COSINE))
        for kind, start, end, heights, width in (
            ('lifting beam', hinge, tip, (150., tip_height), 9.),
            ('chain', top, bottom, (tip_height-2., lower_height), 2.6),
        ):
            component = f'south {state} {kind} {side+1}'
            if not reused:
                obj = beam(f'South Drawbridge / {component}', point(start, heights[0]),
                           point(end, heights[1]), template, collection, width=width)
                obj['projection_component'] = component
                obj['bridge_hardware_generated'] = TAG
                obj['drawbridge_state'] = state
                obj['drawbridge_patch_id'] = 'patch-010'
                obj.hide_render = False
                obj.hide_viewport = False
                if state == 'applied' and kind == 'lifting beam':
                    # Trim the unsupported farthest wall-attachment column.
                    inverse = obj.matrix_world.inverted()
                    for vertex in obj.data.vertices:
                        world = obj.matrix_world @ vertex.co
                        world.x = min(world.x, 741. + ox)
                        vertex.co = inverse @ world
                    obj.data.update()
                additions.append(obj)
            specifications.append(dict(source_node=node, projection_component=component,
                mask_indices=[mask], reviewed=True, evidence='Native hardware silhouette audited against exact endpoint sprite alpha; applied unsupported far wall-end column lies beyond geometry.',
                source_start=list(start), source_end=list(end), inferred_game_heights=list(heights), inferred_world_width=width))
    bpy.context.view_layer.update()
    # Return assignment records for the endpoint owner to append through its
    # existing frozen inventory. No source inventory or worker manifest is edited.
    return dict(recipe=TAG, reused=reused, asset_id=asset_id, state=state,
                components=[o.name for o in additions], source_node=node,
                assignments=[{k:v for k,v in spec.items() if k in ('source_node','projection_component','mask_indices','reviewed','evidence')} for spec in specifications],
                measured_components=specifications, native_mask_indices=masks,
                endpoint_frame_sha256=graphic['sha256'], endpoint_frame_source_sha256=graphic['source_sha256'],
                endpoint_evidence_sha256=sha(states_file), native_level_sha256=sha(native_file),
                endpoint_source_sha256=sha(root / f'bridge-evidence/native-states/patch-010/{state}-map.png'),
                limitations=['Hinge height150game, square timber section9world and chain envelope2.6world are explicit depth/section hypotheses.',
                             'Chains are continuous slender envelopes; individual interlocking links are not reconstructed.',
                             'Hardware is separate endpoint geometry; rotation/chain motion between endpoints is not validated.',
                             'Applied wall-end mask columns x742/x802 have15 pixels outside sprite alpha and are excluded by geometric extent.',
                             'Native457 duplicates454; coupled winch/mechanism masks461/456 are outside this helper.'],
                status='geometry candidate; requires topology, fixed-view and stored-material validation')
