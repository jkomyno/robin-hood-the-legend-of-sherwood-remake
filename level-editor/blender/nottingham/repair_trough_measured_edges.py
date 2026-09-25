"""Repair six hash-bound cart atlas edge samples; retain every other saved value."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / 'level-editor/refinement/blender'))
from isolated_edge_texels import donor
from refinement_workspace import _geometry
from bake_reviewed_asset import _materials

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
EXP = ROOT / 'level-editor/work/nottingham-refinement/texture-generation/experiments/nottingham-village-bridge-trough'
OLD = EXP / 'repair-scoped-visible-support-v3/bake-v1'
OUT = EXP / 'repair-measured-edge-v1/bake-v2'
MANIFEST = EXP / 'repair-scoped-visible-support-v3/views.json'
NAME = 'Village bridge approach wooden handcart / Sloped structural component 289'
TARGETS = [(NAME, 19, (147, 221), 2, 1), (NAME, 19, (137, 223), 2, 1),
           (NAME, 19, (137, 224), 2, 1), (NAME, 1, (240, 14), 2, 1),
           (NAME, 263, (193, 639), 2, 1), (NAME, 474, (328, 740), 1, .5)]
EXPECTED = {
 (19, (147, 221)): [(147, 221)],
 (19, (137, 223)): [(137, 223), (137, 224)],
 (19, (137, 224)): [(137, 223), (137, 224)],
 (1, (240, 14)): [(240, 14)],
 (263, (193, 639)): [(193, 639)],
 (474, (328, 740)): [(328, 740), (328, 741)] + [(x,y) for x in range(329,333) for y in range(738,742)],
}



def pixels(image):
    values = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(values)
    return values.reshape(image.size[1], image.size[0], 4)


def rgba8(values):
    return np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)


def physical_face(obj, face, uv, shape):
    height, width = shape
    points = np.array([uv.data[i].uv[:] for i in face.loop_indices]) * [width, height]
    left, bottom = np.floor(points.min(0)).astype(int)
    right, top = np.ceil(points.max(0)).astype(int)
    yy, xx = np.mgrid[bottom:top, left:right]
    samples = np.c_[xx.ravel() + .5, yy.ravel() + .5]
    physical = np.zeros(len(samples), bool)
    positions = np.zeros((len(samples), 3))
    obj.data.calc_loop_triangles()
    for tri in obj.data.loop_triangles:
        if tri.polygon_index != face.index:
            continue
        coords = np.array([uv.data[i].uv[:] for i in tri.loops]) * [width, height]
        weights = np.c_[samples, np.ones(len(samples))] @ np.linalg.inv(np.c_[coords, np.ones(3)])
        inside = np.all(weights >= -1e-7, axis=1)
        world = np.array([tuple(obj.matrix_world @ obj.data.vertices[i].co) for i in tri.vertices])
        positions[inside] = weights[inside] @ world
        physical |= inside
    return (left, bottom), physical.reshape(xx.shape), positions.reshape(*xx.shape, 3)


def run():
    if OUT.exists():
        raise FileExistsError(OUT)
    validation = json.loads((OLD / 'validation.json').read_text())
    ray = json.loads((OLD / 'coverage/center-ray-classification.json').read_text())
    assert sha(OLD / 'worker.blend') == ray['model_sha256']
    bindings = {str(OLD / 'worker.blend'): ray['model_sha256']}
    bindings.update(validation['evidence_sha256'])
    for name in ['coverage/coverage.json', 'coverage/center-ray-classification.json', 'residual-sample-support.json']:
        bindings[str(OLD / name)] = sha(OLD / name)
    for path, expected in bindings.items():
        assert sha(path) == expected, path
    bpy.ops.wm.open_mainfile(filepath=str(OLD / 'worker.blend'))
    geometry = {o.name: _geometry(o) for o in bpy.data.objects}
    material_layout = {o.name: _materials(o) for o in bpy.data.objects if o.type == 'MESH'}
    image_hashes = {i.name: hashlib.sha256(i.packed_file.data).hexdigest() for i in bpy.data.images if i.packed_file and i.users > 0}
    reports = {p.name: json.loads(p.read_text()) for p in OLD.glob('layer-*.json')}
    proofs = {e['object']: e for r in reports.values() for e in r['objects'] if e.get('texel_provenance')}
    buffers, ownership, images, edits = {}, {}, {}, []
    for name, fid, (x, y), max_texels, max_world in TARGETS:
        obj = bpy.data.objects[name]
        face = obj.data.polygons[fid]
        mat = obj.data.materials[face.material_index]
        node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
        uv = obj.data.uv_layers[node.inputs['Vector'].links[0].from_node.uv_map]
        proof = proofs[name]['texel_provenance']
        assert hashlib.sha256(node.image.packed_file.data).hexdigest() == proof['packed_image_sha256']
        assert hashlib.sha256(json.dumps([list(e.uv) for e in uv.data]).encode()).hexdigest() == proof['uv_sha256']
        assert sha(proof['path']) == proof['sha256']
        bindings[proof['path']] = proof['sha256']
        if name not in buffers:
            buffers[name] = pixels(node.image)
            ownership[name] = np.load(proof['path'])['ownership'].copy()
            images[name] = node.image
        own = ownership[name]
        (left, bottom), physical, positions = physical_face(obj, face, uv, own.shape)
        local = own[bottom:bottom + physical.shape[0], left:left + physical.shape[1]]
        from scipy.ndimage import label
        labels, _ = label(physical & (local == 0))
        component_pixels = np.argwhere(labels == labels[y-bottom, x-left])
        print('Measured component', name, fid, (component_pixels + [bottom, left]).tolist(), flush=True)
        approved_component = [(py-bottom, px-left) for px,py in EXPECTED[(fid,(x,y))]]
        changed_in_component = 1 if fid == 474 else len(approved_component)
        assert changed_in_component / int(physical.sum()) <= .05
        assert fid != 474 or (len(approved_component) == 18 and (x,y) == (328,740))
        selected, texels, distance = donor(local, physical, positions, (y - bottom, x - left), max_texels=max_texels, max_world=max_world, expected_component=approved_component)
        sy, sx = selected[0] + bottom, selected[1] + left
        edits.append(dict(approved_component_xy=[[int(px+left), int(py+bottom)] for py,px in approved_component], object=name, face=fid, target=[x, y], donor=[int(sx), int(sy)], distance_texels=texels, distance_world=distance, packed_image_sha256=proof['packed_image_sha256'], uv_sha256=proof['uv_sha256'], original_provenance_sha256=proof['sha256']))
    # Every donor was selected from original class2, before any edit.
    originals = {name: rgba8(values) for name, values in buffers.items()}
    for e in edits:
        name = e['object']; x, y = e['target']; sx, sy = e['donor']
        assert ownership[name][y, x] == 0 and ownership[name][sy, sx] == 2
        buffers[name][y, x, :3] = buffers[name][sy, sx, :3]
        ownership[name][y, x] = 3
    OUT.mkdir(parents=True)
    for name, image in images.items():
        image.pixels.foreach_set(buffers[name].ravel()); image.update(); image.pack()
    changed_image_names = {image.name for image in images.values()}
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'worker.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(OUT / 'worker.blend'))
    assert geometry == {o.name: _geometry(o) for o in bpy.data.objects}
    assert material_layout == {o.name: _materials(o) for o in bpy.data.objects if o.type == 'MESH'}
    for name, before in image_hashes.items():
        if name not in changed_image_names:
            assert hashlib.sha256(bpy.data.images[name].packed_file.data).hexdigest() == before, name
    for name, original in originals.items():
        obj = bpy.data.objects[name]
        fid = next(e['face'] for e in edits if e['object'] == name)
        image = next(n.image for n in obj.data.materials[obj.data.polygons[fid].material_index].node_tree.nodes if n.type == 'TEX_IMAGE')
        after = rgba8(pixels(image)); allow = np.zeros(original.shape[:2], bool)
        for e in edits:
            if e['object'] == name:
                x, y = e['target']; sx, sy = e['donor']; allow[y, x] = True
                assert np.array_equal(after[y, x, :3], original[sy, sx, :3])
        assert np.array_equal(after[~allow], original[~allow])
        assert np.array_equal(after[:, :, 3], original[:, :, 3])
        proof = proofs[name]['texel_provenance']
        dest = OUT / 'provenance-isolated' / Path(proof['path']).name
        dest.parent.mkdir(exist_ok=True); np.savez_compressed(dest, ownership=ownership[name])
        proof.update(path=str(dest), sha256=sha(dest), packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(), rgba8_sha256=hashlib.sha256(after.tobytes()).hexdigest())
    for filename, report in reports.items():
        (OUT / filename).write_text(json.dumps(report, indent=2) + '\n')
    validation['layers'] = list(reports.values())
    validation['counts_before_isolated_edge_repair'] = dict(validation['counts'])
    validation['counts']['unfilled_texels_including_padding'] -= len(edits)
    validation['counts']['extrapolated_texels_including_padding'] = validation['counts'].get('extrapolated_texels_including_padding', 0) + len(edits)
    validation['isolated_edge_repair'] = edits
    validation['previous_model_sha256'] = ray['model_sha256']
    (OUT / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    report = dict(status='PASS', model_sha256=sha(OUT / 'worker.blend'), previous_model_sha256=ray['model_sha256'], geometry_all_uv_and_material_layout_exact=True, alpha_exact=True, all_untouched_rgba_exact=True, repaired_texels=6, edits=edits, evidence_sha256=bindings, script_sha256=sha(__file__))
    (OUT / 'saved-isolated-edge-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
