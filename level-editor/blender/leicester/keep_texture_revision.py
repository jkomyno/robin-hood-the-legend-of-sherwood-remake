"""Rebuild cached keep textures and guard covered/revealed material variants.

Blender CLI:
  --python keep_texture_revision.py -- bake EXP SOURCE OUTPUT MANIFEST
  --python keep_texture_revision.py -- finalize COVERED_EXP COVERED_BAKE REVEALED_EXP REVEALED_BAKE OUTPUT

Bake manifests bind the approved source/cameras, explicit polygon scope,
best-facing-single policy, and optional coherent preferred cameras. Source
pixels stay protected. Generated colors are used directly, without the optional
raw-prediction tone adjustment. All prior UV layers/packed atlases and unselected
face materials are checked. Finalization restores the externally visible faces
explicitly audited in shared-exterior-face-scope.json in both states, then requires
all eight covered renders to match and the revealed assignments to round-trip.
Outputs must be fresh; no live asset or gallery is modified.
"""
import sys,json,hashlib
from pathlib import Path
import bpy
sys.path.insert(0,str(Path.cwd()/'level-editor/blender/leicester'))
from architecture_texture_packets import original_layers,digest
from tower_texture_scope import verify
from verify_staged_handoffs import snapshot
from bake_reviewed_asset import stage

def bake(args):
    p,source,output=map(lambda x:Path(x).resolve(),args[:3])
    manifest_path=p/args[3];manifest=json.loads(manifest_path.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.window.scene=bpy.data.scenes[manifest['scene_name']];bpy.context.view_layer.update()
    records={r['name']:r['value'] for r in snapshot(manifest['collection_name'],True)}
    selected=manifest['texture_receiver_face_indices'];protected={};before_assignments={}
    for name in manifest['object_names']:
     obj=bpy.data.objects[name];record=records[name]
     if name in selected:
      before_assignments[name]={str(f.index):{'slot':f.material_index,'material':obj.data.materials[f.material_index].name} for f in obj.data.polygons}
     for face in obj.data.polygons:
      if face.index in selected.get(name,[]):continue
      protected.setdefault(name,{})[str(face.index)]={'material':record['materials'][face.index],'vertices':list(face.vertices),'uv':{uv:[coords[i] for i in face.loop_indices] for uv,coords in record['uv'].items()}}
    original=original_layers(manifest);source_sha=digest(source)
    gen=p/'generation-short-no-mask-with-lighting'
    report=stage(manifest_path,gen/'generated-preserved.png',output,texels_per_unit=2)
    result=verify(manifest,protected)
    if original!=original_layers(manifest,original):raise RuntimeError('Original UV layers or packed atlases changed')
    result.update(status='PASS',asset_id=manifest['asset_id'],source_blend=str(source),source_blend_sha256=source_sha,baked_model_sha256=digest(output/'worker.blend'),original_uv_and_packed_atlases_preserved=True,selected_faces=selected,diagnosis_sha256=digest(p/'back-view-diagnostic.json') if (p/'back-view-diagnostic.json').exists() else digest(p/'exterior-gap-diagnosis.json'))
    (output/'protected-materials.json').write_text(json.dumps(result,indent=2)+'\n')
    variants=[]
    for name,before in before_assignments.items():
     obj=bpy.data.objects[name];after={str(f.index):{'slot':f.material_index,'material':obj.data.materials[f.material_index].name} for f in obj.data.polygons}
     variants.append({'object':name,'covered_face_materials':before,'revealed_face_materials':after})
    (output/'material-variant.json').write_text(json.dumps({'base_model':str(source),'base_model_sha256':source_sha,'variant_model_sha256':digest(output/'worker.blend'),'state':'revealed' if 'revealed' in p.name else 'covered-repair','records':variants},indent=2)+'\n')
    return result

def paired_variants(covered, source):
    """Compose earliest covered and latest revealed assignments across two passes."""
    outside = json.loads((source / 'material-variant.json').read_text())
    intermediate = Path(outside['base_model'])
    if digest(intermediate) != outside['base_model_sha256']:
        raise ValueError('Intermediate revealed model changed')
    inside = json.loads((intermediate.parent / 'material-variant.json').read_text())
    if digest(covered / 'worker.blend') != inside['base_model_sha256']:
        raise ValueError('Revealed passes do not derive from the final covered model')
    if digest(source / 'worker.blend') != outside['variant_model_sha256']:
        raise ValueError('Final revealed model changed')
    records = {record['object']: record for record in inside['records']}
    for record in outside['records']:
        if record['object'] in records:
            records[record['object']]['revealed_face_materials'] = record['revealed_face_materials']
        else:
            records[record['object']] = record
    return {'covered_model': str(covered / 'worker.blend'),
            'covered_model_sha256': digest(covered / 'worker.blend'),
            'revealed_model': str(source / 'worker.blend'),
            'revealed_model_sha256': digest(source / 'worker.blend'),
            'records': list(records.values())}


def finalize(args):
    from array import array
    import numpy as np
    from material_states import apply_material_state
    from render_multiview_asset import render
    from refinement_review import _tile
    from refinement_workspace import _geometry
    a, covered_name, b, revealed_name, output = args
    a, b, output = Path(a).resolve(), Path(b).resolve(), Path(output).resolve()
    source = b / revealed_name
    covered = a / covered_name
    output.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(source / 'worker.blend'))
    manifest_path = b / 'views-single-exterior-v4.json'
    manifest = json.loads(manifest_path.read_text())
    variant = paired_variants(covered, source)
    if variant['covered_model_sha256'] != digest(covered / 'worker.blend'):
        raise ValueError('Covered variant changed after the state record was captured')
    if variant['revealed_model_sha256'] != digest(source / 'worker.blend'):
        raise ValueError('Revealed variant changed after the state record was captured')
    scope_path = a / 'shared-exterior-face-scope.json'
    scope = json.loads(scope_path.read_text())['selected_faces']
    mappings = {record['object']: record for record in variant['records']}
    geometry = {obj.name: _geometry(obj) for obj in bpy.data.objects}
    original = original_layers(manifest)
    records = {r['name']: r['value'] for r in snapshot(manifest['collection_name'], True)}
    protected = {}
    for name in manifest['object_names']:
        obj, record = bpy.data.objects[name], records[name]
        for face in obj.data.polygons:
            if face.index in scope.get(name, []):
                continue
            protected.setdefault(name, {})[str(face.index)] = {
                'material': record['materials'][face.index], 'vertices': list(face.vertices),
                'uv': {uv: [coords[i] for i in face.loop_indices]
                       for uv, coords in record['uv'].items()}}
    changed = []
    for name, indices in scope.items():
        obj = bpy.data.objects[name]
        for index in indices:
            assignment = mappings[name]['covered_face_materials'][str(index)]
            slot = assignment['slot']
            if obj.data.materials[slot].name != assignment['material']:
                raise ValueError('Covered face material slot changed')
            obj.data.polygons[index].material_index = slot
            changed.append([name, index])
    preservation = verify(manifest, protected)
    if geometry != {obj.name: _geometry(obj) for obj in bpy.data.objects}:
        raise ValueError('Material assignment changed geometry')
    if original != original_layers(manifest, original):
        raise ValueError('Material assignment changed an original UV or atlas')
    for record in variant['records']:
        obj = bpy.data.objects[record['object']]
        record['revealed_face_materials'] = {
            str(face.index): {'slot': face.material_index,
                             'material': obj.data.materials[face.material_index].name}
            for face in obj.data.polygons}
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'worker.blend'))
    variant['revealed_model'] = str(output / 'worker.blend')
    variant['revealed_model_sha256'] = digest(output / 'worker.blend')
    (output / 'paired-material-variants.json').write_text(json.dumps(variant, indent=2) + '\n')
    width, height = manifest['tile_size']
    render(manifest_path, output / 'actual', width=width)
    buffers = []
    for index in range(8):
        image = bpy.data.images.load(str(output / 'actual' / f'view-{index}-textured.png'), check_existing=False)
        values = array('f', [0]) * len(image.pixels)
        image.pixels.foreach_get(values)
        buffers.append(values)
        bpy.data.images.remove(image)
    _tile(buffers, width, height, output / 'actual/textured.png')
    before = {obj.name: [f.material_index for f in obj.data.polygons]
              for obj in bpy.data.objects if obj.type == 'MESH'}
    for record in variant['records']:
        apply_material_state(bpy.data.objects, record, 'covered')
    render(a / 'views-single-exterior-v4.json', output / 'covered-state-check', width=width)
    for index in range(8):
        values = []
        for directory in [covered / 'actual', output / 'covered-state-check']:
            image = bpy.data.images.load(str(directory / f'view-{index}-textured.png'), check_existing=False)
            pixels = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(pixels)
            values.append(pixels)
            bpy.data.images.remove(image)
        if not np.array_equal(*values):
            raise ValueError('Covered state render changed: view ' + str(index))
    for record in variant['records']:
        apply_material_state(bpy.data.objects, record, 'revealed')
    if before != {obj.name: [f.material_index for f in obj.data.polygons]
                  for obj in bpy.data.objects if obj.type == 'MESH'}:
        raise ValueError('Revealed state did not round-trip')
    evidence = dict(status='PASS', geometry_verified=True, source_model_sha256=digest(source / 'worker.blend'),
                    final_model_sha256=digest(output / 'worker.blend'), changed_faces=changed,
                    scope_sha256=digest(scope_path), original_uv_and_packed_atlases_preserved=True,
                    covered_views_byte_identical_pixels=list(range(8)), revealed_material_assignments_round_trip_exact=True,
                    preservation=preservation, variant_record_sha256=digest(output / 'paired-material-variants.json'))
    (output / 'state-switch-validation.json').write_text(json.dumps(evidence, indent=2) + '\n')
    for filename in ['report.json', 'validation.json', 'protected-materials.json']:
        report = json.loads((source / filename).read_text())
        report['subsequent_material_state_assignment'] = {
            'validation': str(output / 'state-switch-validation.json'),
            'validation_sha256': digest(output / 'state-switch-validation.json'),
            'final_model_sha256': evidence['final_model_sha256']}
        (output / filename).write_text(json.dumps(report, indent=2) + '\n')
    return evidence


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:]
    if arguments[0] == 'bake' and len(arguments) == 5:
        result = bake(arguments[1:])
    elif arguments[0] == 'finalize' and len(arguments) == 6:
        result = finalize(arguments[1:])
    else:
        raise ValueError('Expected bake EXP SOURCE OUTPUT MANIFEST or finalize COVERED_EXP COVERED_BAKE REVEALED_EXP REVEALED_BAKE OUTPUT')
    print(json.dumps({'status': result['status'], 'asset': result.get('asset_id', 'leicester-great-keep')}), flush=True)
