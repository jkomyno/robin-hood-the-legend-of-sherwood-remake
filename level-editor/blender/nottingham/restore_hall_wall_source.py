"""Restore explicitly authorized wall source pixels without rebaking its atlas."""
import hashlib
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patch_texels(original, source, domain, candidates, prior_allowed, visible):
    """Pure guarded RGB patch planner; alpha and every non-authorized sample survive."""
    import numpy as np
    result = original.copy()
    changed, skipped = [], dict(outside_domain=0, prior_allowed=0, blocked=0)
    seen = set()
    for row in candidates:
        ax, ay = row['atlas']
        sx, sy = row['source']
        if not (0 <= ax < original.shape[1] and 0 <= ay < original.shape[0]):
            raise ValueError('Atlas candidate outside saved image')
        if (ax, ay) in seen:
            raise ValueError('Overlapping atlas candidates')
        seen.add((ax, ay))
        if not (0 <= sx < source.shape[1] and 0 <= sy < source.shape[0]) or not domain[sy, sx]:
            skipped['outside_domain'] += 1
            continue
        if prior_allowed(sx, sy):
            skipped['prior_allowed'] += 1
            continue
        if not visible(row):
            skipped['blocked'] += 1
            continue
        rgb = source[sy, sx, :3]
        if not np.array_equal(original[ay, ax, :3], rgb):
            result[ay, ax, :3] = rgb
            changed.append(row)
    assert np.array_equal(original[:, :, 3], result[:, :, 3])
    return result, changed, skipped


def main():
    import bpy
    import numpy as np
    from PIL import Image
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from occlusion_constraints import SourceMaskConstraints
    from preserve_hall_contact_states import signature
    from workspace_components import appearance_state
    args = sys.argv[sys.argv.index('--') + 1:]
    contract_path, destination = [Path(x).resolve() for x in args[:2]]
    contract = json.loads(contract_path.read_text())
    for path_key, hash_key in [('model', 'model_sha256'), ('source_image', 'source_sha256'),
                               ('domain_image', 'domain_sha256')]:
        if sha(contract[path_key]) != contract[hash_key]:
            raise ValueError('Input hash mismatch: ' + path_key)
    if contract['state'] not in ('covered', 'revealed') or contract['face_index'] != 17:
        raise ValueError('Only explicit covered/revealed wall face17 restoration is supported')
    destination.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=contract['model'])
    bpy.context.view_layer.update()
    obj = bpy.data.objects[contract['object']]
    if obj.get('source_node') != 'building-504':
        raise ValueError('Restoration must target hall wall504')
    face = obj.data.polygons[17]
    material = obj.data.materials[face.material_index]
    textures = [n for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
    uv_nodes = [n for n in material.node_tree.nodes if n.type == 'UVMAP']
    if len(textures) != 1 or len(uv_nodes) != 1:
        raise ValueError('Expected one explicit active atlas and UV binding')
    image = textures[0].image
    image_hash = hashlib.sha256(image.packed_file.data).hexdigest()
    if image_hash != contract['packed_image_sha256']:
        raise ValueError('Active wall image changed')
    # Shared active images need a separately reviewed binding change, not implicit detachment.
    for other in bpy.data.objects:
        if other.type != 'MESH' or other == obj:
            continue
        for slot in {p.material_index for p in other.data.polygons}:
            mat = other.data.materials[slot] if slot < len(other.data.materials) else None
            if mat and mat.use_nodes and any(n.type == 'TEX_IMAGE' and n.image == image for n in mat.node_tree.nodes):
                raise ValueError('Wall atlas shared with another active receiver: ' + other.name)
    uv = obj.data.uv_layers[uv_nodes[0].uv_map]
    original = np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1].copy()
    live = np.rint(np.clip(np.array(image.pixels[:]).reshape(original.shape), 0, 1)*255).astype(np.uint8)
    if not np.array_equal(original, live):
        raise ValueError('Packed atlas/live sample encoding differs')
    source = np.array(Image.open(contract['source_image']).convert('RGBA'))
    cropped = np.array(Image.open(contract['domain_image']).convert('L')) > 0
    domain = np.zeros(source.shape[:2], dtype=bool)
    x, y, width, height = contract['domain_box']
    if cropped.shape != (height, width) or x < 0 or y < 0 or x+width > domain.shape[1] or y+height > domain.shape[0]:
        raise ValueError('Invalid source authority domain extent')
    domain[y:y+height, x:x+width] = cropped
    constraints = []
    for prior in contract['prior_projections']:
        if sha(prior['manifest']) != prior['manifest_sha256']:
            raise ValueError('Prior state mask authority changed')
        constraints.append(SourceMaskConstraints(prior['manifest'], prior['label'],
                                                prior['source_sha256'], (source.shape[1], source.shape[0])))
    if not constraints:
        raise ValueError('At least one prior state source authority is required')
    def prior_allowed(sx, sy):
        return any(c.allowed_pixel(obj, sx, sy) for c in constraints)
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    toward = Vector((0, -cosine, sine))
    points, triangles, owners = [], [], []
    for other in bpy.data.collections[contract['collection_name']].all_objects:
        if other.type != 'MESH' or other.hide_render:
            continue
        start = len(points)
        points.extend(other.matrix_world @ v.co for v in other.data.vertices)
        other.data.calc_loop_triangles()
        for triangle in other.data.loop_triangles:
            triangles.append(tuple(start+i for i in triangle.vertices))
            owners.append((other, triangle.polygon_index))
    tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    far = max(p.dot(toward) for p in points)+10
    def visible(row):
        point = Vector(row['world'])
        hit, normal, index, _ = tree.ray_cast(point+toward*(far-point.dot(toward)), -toward)
        return (index is not None and owners[index] == (obj, 17) and normal.dot(toward) > .05
                and (hit-point).length <= .01)
    candidates = {}
    overlap = set()
    obj.data.calc_loop_triangles()
    for triangle in obj.data.loop_triangles:
        mat = obj.data.materials[triangle.material_index]
        if not mat or not mat.use_nodes or not any(n.type == 'TEX_IMAGE' and n.image == image for n in mat.node_tree.nodes):
            continue
        mapping = next(n.uv_map for n in mat.node_tree.nodes if n.type == 'UVMAP')
        coords = [obj.data.uv_layers[mapping].data[i].uv for i in triangle.loops]
        a, b, c = [Vector((st.x*image.size[0], st.y*image.size[1])) for st in coords]
        det = (b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y)
        if abs(det) < 1e-12:
            continue
        vertices = [obj.matrix_world @ obj.data.vertices[i].co for i in triangle.vertices]
        for ay in range(max(0, math.floor(min(v.y for v in [a,b,c]))), min(image.size[1], math.ceil(max(v.y for v in [a,b,c])))):
            for ax in range(max(0, math.floor(min(v.x for v in [a,b,c]))), min(image.size[0], math.ceil(max(v.x for v in [a,b,c])))):
                qx, qy = ax+.5, ay+.5
                wa = ((b.y-c.y)*(qx-c.x)+(c.x-b.x)*(qy-c.y))/det
                wb = ((c.y-a.y)*(qx-c.x)+(a.x-c.x)*(qy-c.y))/det
                weights = [wa, wb, 1-wa-wb]
                if min(weights) < -1e-7:
                    continue
                if triangle.polygon_index != 17:
                    overlap.add((ax, ay))
                    continue
                point = sum((v*w for v,w in zip(vertices,weights)), Vector((0,0,0)))
                candidates[ax, ay] = dict(atlas=[ax, ay], source=[math.floor(point.x),
                    math.floor(-point.y*sine-point.z*cosine)], world=list(point))
    if set(candidates) & overlap:
        raise ValueError('Target face UV island overlaps another active face')
    patched, changed, skipped = patch_texels(original, source, domain, candidates.values(), prior_allowed, visible)
    if not changed:
        raise ValueError('No newly authorized visible source texels to restore')
    padding = []
    if 'edge_padding_proposal' in contract:
        proposal_path = Path(contract['edge_padding_proposal'])
        if sha(proposal_path) != contract['edge_padding_sha256']:
            raise ValueError('Source-edge padding proposal changed')
        proposal = json.loads(proposal_path.read_text())
        direct = {tuple(row['atlas']): row for row in changed}
        if len(proposal['samples']) != 24 or len({tuple(r['target']) for r in proposal['samples']}) != 24:
            raise ValueError('Only the exact reviewed 24 edge support samples are permitted')
        for sample in proposal['samples']:
            target, donor = tuple(sample['target']), tuple(sample['donor'])
            distance = math.dist(target, donor)
            if target in direct or donor not in direct or target not in candidates or distance > 1.000001:
                raise ValueError('Padding must use an original direct-source donor exactly one texel away on face17')
            row, donor_row = candidates[target], direct[donor]
            sx, sy = row['source']
            if prior_allowed(sx, sy):
                raise ValueError('Padding attempted to overwrite previously authorized source')
            authorized = 0 <= sx < source.shape[1] and 0 <= sy < source.shape[0] and domain[sy, sx]
            direct_visible = bool(authorized and visible(row))
            ax, ay = target
            dx, dy = donor
            # Prefer the exact camera source if the target is independently eligible.
            patched[ay, ax, :3] = source[sy, sx, :3] if direct_visible else patched[dy, dx, :3]
            padding.append(dict(target=list(target), donor=list(donor), atlas_distance=distance,
                world_distance=math.dist(row['world'], donor_row['world']), target_physical=True,
                target_source=row['source'], donor_source=donor_row['source'],
                target_in_authorized_domain=bool(authorized), exact_target_source=direct_visible,
                reason='exact-target-source' if direct_visible else
                       'source-occluded-filter-support' if authorized else 'outside-authority-filter-support'))
    other_before = {o.name: signature(o) for o in bpy.data.objects
                    if o.type == 'MESH' and o.get('asset_group') == obj.get('asset_group') and o != obj}
    def schema():
        appearance = appearance_state(obj)
        for mat in appearance['materials']:
            for node in mat.get('nodes', []) if mat else []:
                if node.get('image', {}).get('name') == image.name:
                    node['image'].pop('packed_sha256', None)
                    node['image'].pop('dirty', None)
        return dict(appearance=appearance, vertices=[list(v.co) for v in obj.data.vertices],
                    faces=[list(p.vertices) for p in obj.data.polygons], matrix=[list(r) for r in obj.matrix_world])
    before_schema = schema()
    image.pixels.foreach_set((patched.astype(np.float32)/255).ravel())
    image.update()
    image.pack()
    packed = np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1]
    if not np.array_equal(packed, patched) or schema() != before_schema:
        raise ValueError('Packed atlas bytes or protected receiver schema changed unexpectedly')
    assert other_before == {n: signature(bpy.data.objects[n]) for n in other_before}
    target_name, image_name = obj.name, image.name
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(destination / 'model.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(destination / 'model.blend'))
    obj, image = bpy.data.objects[target_name], bpy.data.images[image_name]
    if schema() != before_schema or other_before != {n: signature(bpy.data.objects[n]) for n in other_before}:
        raise ValueError('Protected objects or target schema changed after saving')
    reopened = np.array(Image.open(io.BytesIO(bytes(image.packed_file.data))).convert('RGBA'))[::-1]
    if not np.array_equal(reopened, patched):
        raise ValueError('Saved packed atlas differs from authorized patch')
    proof = dict(status='PASS', state=contract['state'], contract_sha256=sha(contract_path),
                 original_model_sha256=contract['model_sha256'], model_sha256=sha(destination/'model.blend'),
                 original_packed_image_sha256=image_hash, packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),
                 changed_texels=len(changed)+len(padding), direct_source_texels=len(changed),
                 edge_padding_texels=len(padding), edge_padding=padding,
                 skipped=skipped, changes=changed,
                 protected_other_objects=other_before, geometry_uv_material_schema_preserved=True,
                 prior_allowed_source_texels_preserved=True, alpha_preserved=True,
                 all_outside_patch_rgba_preserved=True)
    (destination / 'source-restoration.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps({k:proof[k] for k in ['status','state','changed_texels','skipped']}))


if __name__ == '__main__':
    main()
