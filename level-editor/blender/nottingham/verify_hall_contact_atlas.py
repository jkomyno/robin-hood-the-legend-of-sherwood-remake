"""Bind source-ray witnesses to the saved roof cap atlas through exact replay."""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]
CAP = 'building-505__castle-hall-northwest-contact'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(obj):
    materials = {p.material_index for p in obj.data.polygons}
    if len(materials) != 1:
        raise ValueError('Expected one cap atlas material')
    material = obj.data.materials[next(iter(materials))]
    image = next(n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE')
    layer = obj.data.uv_layers[next(n.uv_map for n in material.node_tree.nodes if n.type == 'UVMAP')]
    return image, layer, dict(packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),
                            uv_sha256=hashlib.sha256(json.dumps([list(v.uv) for v in layer.data]).encode()).hexdigest())


def main():
    import bpy
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from source_projection_bake import bake
    from render_slots import acquire
    acquire(slots=2)
    args = sys.argv[sys.argv.index('--') + 1:]
    workspace, witnesses, output = [Path(p).resolve() for p in args[:3]]
    output.mkdir(parents=True, exist_ok=False)
    model = workspace / 'model.blend'
    model_hash = sha(model)
    config = json.loads((workspace / 'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(model))
    bpy.context.view_layer.update()
    obj = bpy.data.objects[CAP]
    _, _, before = binding(obj)
    report = bake(config['map_name'], config['source_path'], output / 'replay.json',
                  texels_per_unit=float(obj.get('source_contact_texels_per_unit', 1)),
                  receiver_nodes=['building-505'], projection_label='exterior',
                  receiver_object_names=[CAP], receiver_asset_id=config['asset_id'],
                  preserve_authored=False, source_mask_manifest=config['source_mask_manifest'],
                  collection_name=config['collection_name'], provenance_directory=output / 'provenance')
    _, _, after = binding(obj)
    if before != after:
        (output / 'report.json').write_text(json.dumps(dict(status='FAIL-REPLAY-MISMATCH',
            model_sha256=model_hash, saved=before, replayed=after), indent=2) + '\n')
        raise ValueError('Cap source replay differs from saved packed image or UVs')
    entry = report['objects'][0]['texel_provenance']
    provenance = np.load(entry['path'])['ownership']
    # Sampling uses the unchanged saved scene, never the replay's in-memory material.
    bpy.ops.wm.open_mainfile(filepath=str(model))
    bpy.context.view_layer.update()
    obj = bpy.data.objects[CAP]
    image, uv, saved = binding(obj)
    assert saved == before
    points, triangles, records = [], [], []
    for other in bpy.data.collections[config['collection_name']].all_objects:
        if other.type != 'MESH' or other.hide_render:
            continue
        start = len(points)
        points.extend(other.matrix_world @ v.co for v in other.data.vertices)
        other.data.calc_loop_triangles()
        for triangle in other.data.loop_triangles:
            triangles.append(tuple(start + i for i in triangle.vertices))
            records.append((other, tuple(triangle.loops), triangle.polygon_index))
    tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    toward, down = Vector((0, -cosine, sine)), Vector((0, -sine, -cosine))
    far = max(p.dot(toward) for p in points) + 10
    data = np.array(image.pixels[:]).reshape(image.size[1], image.size[0], 4)
    rows = []
    source_pixels = json.loads(witnesses.read_text())['removed_source_pixels']
    for x, y in source_pixels:
        base = Vector((x + .5, 0, 0)) + down * (y + .5)
        origin = base + toward * (far - base.dot(toward))
        hit, _, index, _ = tree.ray_cast(origin, -toward)
        row = dict(source=[x, y], first_object=records[index][0].name if index is not None else None)
        if index is None or records[index][0] != obj:
            row['status'] = 'FAIL-NONCAP-FIRST-HIT'
            rows.append(row)
            continue
        _, loops, face = records[index]
        a, b, c = [points[i] for i in triangles[index]]
        u, v, q = b-a, c-a, hit-a
        denominator = u.dot(u)*v.dot(v)-u.dot(v)**2
        bu = (q.dot(u)*v.dot(v)-q.dot(v)*u.dot(v))/denominator
        bv = (q.dot(v)*u.dot(u)-q.dot(u)*u.dot(v))/denominator
        st = sum((uv.data[i].uv*w for i, w in zip(loops, [1-bu-bv, bu, bv])), Vector((0, 0)))
        xx, yy = st.x*image.size[0]-.5, st.y*image.size[1]-.5
        ix, iy = math.floor(xx), math.floor(yy)
        tx, ty = xx-ix, yy-iy
        taps = []
        rgb = np.zeros(3)
        for dx, dy, weight in [(0, 0, (1-tx)*(1-ty)), (1, 0, tx*(1-ty)),
                               (0, 1, (1-tx)*ty), (1, 1, tx*ty)]:
            px, py = max(0, min(image.size[0]-1, ix+dx)), max(0, min(image.size[1]-1, iy+dy))
            taps.append(dict(atlas=[px, py], weight=weight, provenance=int(provenance[py, px])))
            rgb += data[py, px, :3]*weight
        source_weight = sum(t['weight'] for t in taps if t['provenance'] == 1)
        row.update(face=face, uv=list(st), rgb=list(rgb), taps=taps, source_weight=source_weight,
                   status='ALL-SOURCE' if source_weight >= 1-1e-6 else
                          'NO-SOURCE' if source_weight <= 1e-6 else 'MIXED-SOURCE-BOUNDARY')
        rows.append(row)
    counts = {status: sum(r['status'] == status for r in rows) for status in sorted({r['status'] for r in rows})}
    status = ('FAIL' if counts.get('NO-SOURCE', 0) or counts.get('FAIL-NONCAP-FIRST-HIT', 0) else
              'REQUIRES-BOUNDARY-REVIEW' if counts.get('MIXED-SOURCE-BOUNDARY', 0) else 'PASS')
    proof = dict(status=status,
                 model_sha256=model_hash, atlas_binding=before, witnesses_sha256=sha(witnesses),
                 provenance=entry, count=len(rows), counts=counts, pixels=rows,
                 transferred_pixels=len(rows), all_source_pixels=counts.get('ALL-SOURCE', 0),
                 mixed_source_pixels=counts.get('MIXED-SOURCE-BOUNDARY', 0),
                 noncap_pixels=counts.get('FAIL-NONCAP-FIRST-HIT', 0), no_source_pixels=counts.get('NO-SOURCE', 0),
                 method='Exact packed-image and UV replay equality; saved-scene first hit and actual bilinear UV taps classified by source provenance.',
                 limitation='Mixed samples are reported individually without an automatic tolerance waiver.')
    assert sha(model) == model_hash, 'Read-only audit changed saved model'
    (output / 'report.json').write_text(json.dumps(proof, indent=2) + '\n')
    (workspace / 'inspection/contact-material-provenance.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({k: proof[k] for k in ['status', 'count', 'counts']}))


if __name__ == '__main__':
    main()
