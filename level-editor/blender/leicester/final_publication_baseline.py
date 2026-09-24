"""Build an isolated, approval-bound baseline with two absent canonical parts.

This recipe changes no live files. Existing mesh geometry, materials, UVs and
visibility are guarded; the sole ownership migration is the lifting canopy.
"""
import hashlib
import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement/blender'))
from bake_reviewed_asset import _materials
from group_assets import _renamed_part


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(obj):
    return {'world': [list(row) for row in obj.matrix_world],
            'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'materials_uv': _materials(obj),
            'visibility': [obj.hide_render, obj.hide_viewport, obj.hide_get()]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    root = Path('level-editor/work/leicester-refinement').resolve()
    output = root / 'publication-final-17/baseline'
    output.mkdir(parents=True, exist_ok=True)
    assert not any(output.iterdir()), "Output must be empty"
    source = root / 'main/leicester.blend'
    catalog_path = root / 'church-ownership-v1/catalog.json'
    decisions_path = root / 'round-1/texture-review/decisions.json'
    source_hash = sha(source)
    catalog = json.loads(catalog_path.read_text())
    owners = {f"building-{p['obstacle']:03}": (g, p)
              for g in catalog['groups'] for p in g['parts']}
    assert len(owners) == 392
    decisions = json.loads(decisions_path.read_text())['decisions']
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.window.scene = bpy.data.scenes['Leicester Refinement']
    working = bpy.data.collections['Leicester Working']
    original = [o for o in working.all_objects if o.type == 'MESH']
    before = {o: state(o) for o in original}
    names = {o: o.name for o in original}
    properties = {o: dict(o) for o in original}
    images = {im: sha_bytes(im.packed_file.data) for im in bpy.data.images if im.packed_file}
    sources = {o.get('source_node') for o in original}
    assert set(owners) - sources == {'building-273', 'building-342'}
    assert sources - set(owners) == {'ground'}
    parents = {o['asset_group']: o for o in working.all_objects
               if o.type == 'EMPTY' and o.get('asset_group')}
    added = []
    specs = [(273, 'leicester-west-moat-tower', '3e546af726cbe5dd',
              'West Moat Tower / West Moat Tower component 273'),
             (342, 'leicester-northwest-tower', '07581dfb64aa2ca2',
              'Northwest Tower / Northwest Tower component 342')]
    for number, asset, revision, object_name in specs:
        matches = [d for d in decisions if d['asset_id'] == asset and
                   d['review_revision'].startswith(revision) and d['decision'] == 'approved']
        assert len(matches) == 1
        decision = matches[0]
        donor = Path(decision['evidence_paths']['model'])
        assert sha(donor) == decision['evidence_sha256']['model']
        review = Path(decision['evidence_paths']['review'])
        assert sha(review) == decision['evidence_sha256']['review']
        manifest = json.loads((review.parent / 'views.json').read_text())
        assert object_name in manifest['object_names']
        with bpy.data.libraries.load(str(donor), link=False) as (src, dst):
            assert object_name in src.objects
            dst.objects = [object_name]
        obj = dst.objects[0]
        assert obj.type == 'MESH' and obj.get('source_node') == f'building-{number:03}'
        assert obj.get('asset_group') == asset
        working.objects.link(obj)
        bpy.context.view_layer.update()
        matrix = obj.matrix_world.copy()
        donor_state = state(obj)
        obj.parent = parents[asset]
        obj.matrix_world = matrix
        bpy.context.view_layer.update()
        assert state(obj) == donor_state, ("Donor state drift", object_name, [list(r) for r in matrix], [list(r) for r in obj.matrix_world])
        added.append({'source_node': obj['source_node'], 'asset_id': asset,
                      'object_name': obj.name, 'approved_object_name': object_name,
                      'review_revision': decision['review_revision'], 'donor': str(donor),
                      'donor_sha256': sha(donor), 'world_transform': [list(row) for row in matrix],
                      'state_sha256': digest(state(obj))})
    moves = []
    for obj in original:
        if obj.get('source_node') == 'ground':
            continue
        group, part = owners[obj['source_node']]
        if obj.get('asset_group') == group['id']:
            continue
        assert obj['source_node'] == 'building-221'
        assert obj.get('asset_group') == 'leicester-church-side-tower'
        assert group['id'] == 'leicester-east-moat-drawbridge'
        old = {'object': obj.name, 'from': obj['asset_group'], 'source_node': obj['source_node']}
        matrix = obj.matrix_world.copy()
        obj.name = _renamed_part(obj, group, part)
        obj.parent = parents[group['id']]
        obj.matrix_world = matrix
        obj['asset_group'], obj['asset_name'], obj['part_name'] = group['id'], group['name'], part['name']
        moves.append({**old, 'to': group['id'], 'renamed_object': obj.name})
    bpy.context.view_layer.update()
    assert len(moves) == 1
    for obj in original:
        assert state(obj) == before[obj], 'Existing mesh changed: ' + names[obj]
        if obj['source_node'] != 'building-221':
            assert obj.name == names[obj], (names[obj], obj.name)
            assert repr(dict(obj)) == repr(properties[obj]), (obj.name, repr(dict(obj)), repr(properties[obj]))
    assert all(sha_bytes(im.packed_file.data) == value for im, value in images.items())
    assert sha(source) == source_hash
    (output / 'catalog.json').write_text(catalog_path.read_text())
    target = output / 'leicester.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    assert sha(source) == source_hash
    report = {'status': 'PASS', 'baseline': str(source), 'baseline_sha256': source_hash,
              'grouped_baseline': str(target), 'grouped_sha256': sha(target),
              'catalog_source': str(catalog_path), 'catalog_source_sha256': sha(catalog_path),
              'catalog_sha256': sha(output / 'catalog.json'), 'canonical_parts': 392,
              'scene_name': bpy.context.scene.name, 'collection_name': working.name,
              'reference_camera': bpy.context.scene.camera.name,
              'decisions': str(decisions_path), 'decisions_sha256': sha(decisions_path),
              'existing_meshes': len(original), 'existing_mesh_state_identical': True,
              'existing_packed_images_identical': True, 'added_parts': added,
              'moved_components': moves, 'preserved_mesh_states': [
                  {'original_name': names[o], 'name': o.name, 'source_node': o.get('source_node'),
                   'state_sha256': digest(before[o])} for o in original]}
    (output / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'preserved_mesh_states'}))


def sha_bytes(data):
    return hashlib.sha256(bytes(data)).hexdigest()


if __name__ == '__main__':
    main()
