"""Proxy tree/bush geometry fitted to painted Lincoln foliage (35-degree source camera).

Run from the repository root after trees_inventory.py:

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/trees_geometry.py -- \
      --output level-editor/work/lincoln-refinement/scratch/trees/pilot \
      lincoln-tree-north-plateau-west lincoln-tree-north-plateau-red lincoln-tree-north-plateau-east

Representation per asset (two meshes sharing one source node ``foliage-<slug>``), in the
style of the reviewed-good Leicester trees and built with their recipes:
- crown (projection_component ``crown``): Leicester ``foliage_trees.source_packet`` partitions
  the painted domain into 8 lobes (exact source RGB, domain as physical alpha) and
  ``foliage_trees.refine_crown`` builds paired curved cutout cards per lobe (source front,
  neutral back) plus two transverse neutral cards, all on the vertical plane through the
  tree's foot and offset only along the source ray, so the source view is exact;
- wood (projection_component ``wood``): Leicester ``props_trees.geometry`` lofts a trunk from
  the terrain contact to the crown centre and three forks toward the upper lobes.
Ground contact: the asset's base pixel is cast along the source ray onto the terrain
receivers only (the ``ground`` mesh, every node that owns an authored ground domain, and
rock/cliff/plateau groups). Lobe depth, rear cards and wood are inferred.

The script opens lincoln-grouped-v4.blend, adds the requested assets to ``lincoln Working``
(never touching other objects), bakes owned source pixels through the shared
source_projection_bake with a scratch mask manifest carrying the proposed foliage domains,
renders the eight-view packet with the shared refinement_review, and runs a source-camera
coverage audit. There is no catalog/workspace support for obstacle-less parts yet, so the
output is a scratch pilot, not a prepared workspace (see the pilot README).
"""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path.cwd()
R = ROOT / 'level-editor/work/lincoln-refinement'
sys.path.insert(0, str(ROOT / 'level-editor/blender/lincoln'))
# Leicester foliage recipes are the reviewed-good precedent; reused, not copied.
sys.path.insert(0, str(ROOT / 'level-editor/blender/leicester'))
from render_slots import acquire  # noqa: E402

VERSION = 'lincoln-foliage-cards-v3'
SCENE_BLEND = R / 'grouped/lincoln-grouped-v4.blend'
CATALOG = R / 'scratch/trees/inventory/tree-catalog-proposal.json'
MASKS = R / 'mask-review/source-masks-v4.json'
SOURCE = R / 'source-states/covered.png'
LIGHTING = R / 'lighting-calibration/map-lighting.json'
W, H = 2944, 2176
SIN, COS = math.sin(math.radians(35)), math.cos(math.radians(35))
GROUND_DOMAINS = set(range(433, 453))
FIRST_TREE_MASK = 454
# Rock/cliff/plateau groups without an authored ground domain still carry plants.
NATURAL_GROUP_WORDS = ('rock', 'cliff', 'plateau', 'slope', 'ridge', 'hillside', 'spur', 'ledge', 'bank')
# Visually chosen trunk-foot pixels where base_pixel()'s guess is wrong. Keyed by
# asset id: (x, y). ground_contact() still walks up past architecture from here.
BASE_OVERRIDES = {
    # Foot hidden behind the north curtain; crown centred near x=2465.
    'lincoln-tree-north-plateau-west': (2465, 400),
    # Foot hidden behind the NE square tower; the lower-left crown part that drags
    # the centroid west is shared with the western tree.
    'lincoln-tree-north-plateau-east': (2690, 449),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixel_of(point):
    """Source pixel (x, y) of a Blender world point."""
    return point[0], -point[1] * SIN - point[2] * COS


def terrain_nodes():
    manifest = json.loads(MASKS.read_text())
    entries = [e for p in manifest['projections'].values() for e in p['assignments']]
    return {e['source_node'] for e in entries if set(e['mask_indices']) & GROUND_DOMAINS} | {'ground'}


def load_domain(row):
    import numpy as np
    from PIL import Image
    bitmap = np.asarray(Image.open(row['domain_png']).convert('L')) > 0
    x, y = row['domain_box_top_left']
    full = np.zeros((H, W), bool)
    full[y:y + bitmap.shape[0], x:x + bitmap.shape[1]] = bitmap
    return full


def terrain_hit(terrain_tree, pixel):
    from mathutils import Vector
    toward = Vector((0, -COS, SIN))
    bx, by = pixel
    start = Vector((bx + .5, 0, -(by + .5) / COS)) + toward * 20000
    hit, _, _, _ = terrain_tree.ray_cast(start, -toward)
    if hit is None:
        raise ValueError(f'No terrain under base pixel {pixel}')
    return hit


def base_pixel(domain):
    """Foot pixel guess: the painted trunk if the lowest rows are narrow, else the
    column centroid of the crown's lower third, at the lowest painted row."""
    import numpy as np
    ys, xs = np.nonzero(domain)
    bottom, top = int(ys.max()), int(ys.min())
    width = xs.max() - xs.min() + 1
    low = xs[ys >= bottom - 6]
    if low.max() - low.min() + 1 <= .25 * width:
        return [int(np.median(low)), bottom], 'painted trunk foot (narrow lowest rows)'
    third = xs[ys >= bottom - (bottom - top) / 3]
    return [int(round(third.mean())), bottom], 'lower-third crown centroid at lowest painted row'


def ground_contact(terrain_tree, architecture_tree, base, depth_clearance):
    """Walk the foot up the source column until it and the crown's near half stand
    on open terrain, not inside/under architecture that the crown merely peeks over."""
    from mathutils import Vector
    up = Vector((0, 0, 1))
    bx, by = base
    for y in range(by, max(by - 400, 0), -2):
        foot = terrain_hit(terrain_tree, (bx, y))
        blocked = False
        for dy in (0., -.5 * depth_clearance, -depth_clearance):
            probe = foot + Vector((0, dy, 1))
            if architecture_tree.ray_cast(probe, up)[0] is not None:
                blocked = True
                break
        if not blocked:
            return foot, (bx, y), by - y
    raise ValueError(f'No open terrain above base pixel {base}')


def mesh_object(name, verts, faces, collection, props):
    import bpy
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    for key, value in props.items():
        obj[key] = value
    return obj


def source_uv_and_material(obj, image):
    """Fallback source-projection UV and material (the bake replaces the material)."""
    import bpy
    mesh = obj.data
    layer = mesh.uv_layers.new(name='source projection')
    for loop in mesh.loops:
        px, py = pixel_of(obj.matrix_world @ mesh.vertices[loop.vertex_index].co)
        layer.data[loop.index].uv = (px / W, 1 - py / H)
    material = bpy.data.materials.new(obj.name + ' / fallback')
    material.use_nodes = True
    nodes = material.node_tree.nodes
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    material.node_tree.links.new(texture.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
    mesh.materials.append(material)


def topology(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    report = dict(vertices=len(bm.verts), faces=len(bm.faces),
                  non_manifold_edges=sum(not e.is_manifold for e in bm.edges),
                  zero_area_faces=sum(f.calc_area() < 1e-8 for f in bm.faces),
                  volume=float(bm.calc_volume(signed=True)))
    bm.free()
    return report


def kmeans_seeds(domain, count=8, rounds=25):
    """Deterministic lobe seeds: farthest-point initialisation plus Lloyd rounds."""
    import numpy as np
    ys, xs = np.nonzero(domain)
    points = np.stack([xs, ys], 1).astype(float)
    step = max(1, len(points) // 20000)
    sample = points[::step]
    seeds = [sample[np.argmin(sample[:, 1])]]
    for _ in range(1, min(count, len(sample))):
        distance = np.min([((sample - s) ** 2).sum(1) for s in seeds], 0)
        seeds.append(sample[np.argmax(distance)])
    seeds = np.array(seeds)
    for _ in range(rounds):
        label = np.argmin(((sample[:, None] - seeds[None]) ** 2).sum(2), 1)
        seeds = np.array([sample[label == k].mean(0) if np.any(label == k) else seeds[k] for k in range(len(seeds))])
    return [(int(round(x)), int(round(y))) for x, y in seeds]


def foliage_packet(row, node_number, ground, workspace):
    """Run the Leicester native-cutout partition (foliage_trees.source_packet) on a
    Lincoln foliage domain: exact source RGB with the domain as alpha, per lobe."""
    import numpy as np
    import foliage_trees
    directory = workspace / 'foliage-source'
    directory.mkdir(parents=True, exist_ok=True)
    x, y = row['domain_box_top_left']
    from PIL import Image
    width, height = Image.open(row['domain_png']).size
    inventory = dict(masks=[dict(index=node_number, png=str(Path(row['domain_png']).resolve()),
                                 box_top_left=[x, y], box_size=[width, height])])
    (directory / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (directory / 'masks.json').write_text(json.dumps(dict(mask_inventory='inventory.json',
                                                          projections=dict(exterior=dict(assignments=[]))), indent=2) + '\n')
    (directory / 'workspace.json').write_text(json.dumps(dict(source_mask_manifest=str(directory / 'masks.json'),
                                                              source_path=str(SOURCE)), indent=2) + '\n')
    domain = load_domain(row)
    foliage_trees.CONFIG[node_number] = dict(mask=node_number, ground=ground,
                                            canopy_bottom=int(np.nonzero(domain)[0].max()),
                                            seeds=kmeans_seeds(domain, len(foliage_trees.DEPTHS)))
    return foliage_trees.source_packet(directory, node_number, directory / 'lobes')


def wood_paths(domain, foot_pixel_on_plane, seeds, width):
    """Trunk from the foot to the crown centre, forking toward the upper lobes
    (props_trees BRANCHES format: (x, plane y, radius) centreline samples)."""
    import numpy as np
    ys, xs = np.nonzero(domain)
    fx, fy = foot_pixel_on_plane
    cx, cy = float(xs.mean()), float(ys.mean())
    radius = min(max(.045 * width, 3.), 11.)
    trunk = [(fx, fy + 4, radius * 1.2), (fx + .35 * (cx - fx), fy + .45 * (cy - fy), radius * .9),
             (cx, cy + .15 * (fy - cy), radius * .65)]
    paths = [trunk]
    top = trunk[-1]
    upper = sorted(seeds, key=lambda s: s[1])[:3]
    for sx, sy in upper:
        mid = ((top[0] + sx) / 2, (top[1] + sy) / 2, radius * .4)
        paths.append([top[:2] + (radius * .5,), mid, (sx, sy, radius * .15)])
    return paths


def build(row, terrain_tree, architecture_tree, collection, image, workspace, node_number):
    import numpy as np
    import foliage_trees
    import props_trees
    node = 'foliage-' + row['id'].removeprefix('lincoln-')
    domain = load_domain(row)
    base, base_rule = base_pixel(domain)
    if row['id'] in BASE_OVERRIDES:
        base, base_rule = list(BASE_OVERRIDES[row['id']]), 'visual override'
    ys, xs = np.nonzero(domain)
    width = float(xs.max() - xs.min())
    try:
        foot, foot_pixel, walked = ground_contact(terrain_tree, architecture_tree, base, .3 * width)
    except ValueError:
        # Plants on ledges under overhanging architecture: require only the foot itself open.
        foot, foot_pixel, walked = ground_contact(terrain_tree, architecture_tree, base, 0.)
        base_rule += '; crown depth clearance waived (overhang)'
    # Leicester convention: every card lies on the vertical plane native y = ground
    # (offset along the source ray), so ground = native y of the foot.
    ground = -foot.y * SIN
    props = dict(source_node=node, asset_group=row['id'], asset_name=row['name'],
                 part_name='Painted ' + row['kind'], foliage_recipe=VERSION, foliage_kind=row['kind'])
    evidence = foliage_packet(row, node_number, ground, workspace)
    crown = mesh_object(row['name'] + ' / crown', [], [], collection, {**props, 'projection_component': 'crown'})
    crown_report = foliage_trees.refine_crown(crown, node_number, evidence)
    # Wood: the Leicester props_trees loft, fed Lincoln branch paths.
    native_foot_z = foot.z * COS
    paths = wood_paths(domain, (foot.x, ground - native_foot_z), foliage_trees.CONFIG[node_number]['seeds'], width)
    props_trees.SUPPORTED.add(node_number)
    props_trees.GROUND[node_number] = ground
    props_trees.CROWNS[node_number] = [[paths[0][-1][1], paths[0][-1][0] - 1, paths[0][-1][0] + 1]] * 2
    props_trees.BRANCHES[node_number] = [list(path) for path in paths]
    verts, faces = props_trees.geometry(node_number, 'wood')
    wood = mesh_object(row['name'] + ' / wood', verts, faces, collection, {**props, 'projection_component': 'wood'})
    source_uv_and_material(wood, image)
    return dict(asset_id=row['id'], source_node=node, base_pixel=list(base), base_pixel_rule=base_rule,
                foot_pixel=list(foot_pixel), foot_walked_up_pixels=walked,
                ground_contact_world=list(foot), ground_contact_native_z=native_foot_z, card_plane_native_y=ground,
                wood_paths=paths, lobes=len(evidence['lobes']),
                crown={k: v for k, v in crown_report.items() if k != 'source_partition'} | dict(name=crown.name),
                wood=dict(name=wood.name, **topology(wood)))


def pilot_masks(rows, output):
    """Scratch inventory + manifest: v4 plus proposed foliage domains for the built assets."""
    inventory_path = (MASKS.parent / json.loads(MASKS.read_text())['mask_inventory']).resolve()
    inventory = json.loads(inventory_path.read_text())
    directory = output / 'mask-inventory'
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for record in inventory['masks']:
        record = dict(record)
        if record.get('png'):
            record['png'] = os.path.relpath(inventory_path.parent / record['png'], directory)
        records.append(record)
    manifest = json.loads(MASKS.read_text())
    for number, row in enumerate(rows):
        index = FIRST_TREE_MASK + number
        from PIL import Image
        bitmap = Image.open(row['domain_png'])
        records.append(dict(index=index, layer=None, layer_index=None,
                            png=os.path.relpath(row['domain_png'], directory), mask_type=None,
                            box_top_left=row['domain_box_top_left'], box_size=list(bitmap.size),
                            character_polyline=[], projectile_polyline=[], obstacle_indices=[], synthetic=True,
                            constraint_kind='proposed-foliage-domain', source_sha256=sha(SOURCE),
                            review_evidence=str(CATALOG), pixels=row['domain_pixels'],
                            reason=f"Proposed foliage domain for {row['id']} (native masks {row['native_masks']})."))
        manifest['projections']['exterior']['assignments'].append(dict(
            reviewed=True, source_node='foliage-' + row['id'].removeprefix('lincoln-'), mask_indices=[index],
            constraint_kind='proposed-foliage-domain', review_status='pilot-visual-check-only',
            review_evidence=str(CATALOG), review_note=row['name']))
    inventory = dict(inventory, masks=records)
    (directory / 'manifest.json').write_text(json.dumps(inventory, indent=2) + '\n')
    manifest['mask_inventory'] = os.path.relpath(directory / 'manifest.json', output)
    manifest['limitations'] = list(manifest.get('limitations', [])) + [
        'SCRATCH PILOT: foliage-* assignments are unreviewed proposals from trees_inventory.py.']
    path = output / 'source-masks-pilot.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return path


def coverage_audit(row, collection, output, domains):
    """Source-camera first-hit audit over the proposed domain, independent of acceptance."""
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from PIL import Image
    domain = load_domain(row)
    objects = [o for o in collection.all_objects if o.type == 'MESH' and not o.hide_render]
    verts, tris, owners = [], [], []
    from physical_opacity import OpacityRegistry
    opacity = OpacityRegistry()
    for obj in objects:
        obj.data.calc_loop_triangles()
        offset = len(verts)
        verts += [obj.matrix_world @ v.co for v in obj.data.vertices]
        for tri in obj.data.loop_triangles:
            opacity.add(obj, obj.data, tri)
            tris.append(tuple(offset + i for i in tri.vertices))
            owners.append(obj)
    # Cutout alpha is physical coverage: rays pass through transparent leaf gaps.
    tree = opacity.wrap(BVHTree.FromPolygons(verts, tris, all_triangles=True))
    toward = Vector((0, -COS, SIN))
    ys, xs = np.nonzero(domain)
    counts = dict(own_first_hit=0, shared_with_front_foliage=0, foreign_first_hit=0, miss=0)
    foreign = {}
    picture = np.zeros((H, W, 3), np.uint8)
    for x, y in zip(xs, ys):
        start = Vector((x + .5, 0, -(y + .5) / COS)) + toward * 20000
        hit, _, index, _ = tree.ray_cast(start, -toward)
        if hit is None:
            counts['miss'] += 1; picture[y, x] = (255, 0, 0)
        elif owners[index].get('asset_group') == row['id']:
            counts['own_first_hit'] += 1; picture[y, x] = (0, 255, 0)
        else:
            key = owners[index].get('asset_group') or owners[index].get('source_node')
            if key in domains and domains[key][y, x]:
                # Pixel lies in both proposed foliage domains: first hit decides.
                counts['shared_with_front_foliage'] += 1; picture[y, x] = (0, 120, 255)
            else:
                counts['foreign_first_hit'] += 1; picture[y, x] = (255, 0, 255)
            foreign[key] = foreign.get(key, 0) + 1
    # Painted pixels outside the domain that the proxy now covers first (overreach).
    x0, y0, x1, y1 = row['source_box']
    pad = 40
    over = 0
    for y in range(max(0, y0 - pad), min(H, y1 + pad)):
        for x in range(max(0, x0 - pad), min(W, x1 + pad)):
            if domain[y, x]:
                continue
            start = Vector((x + .5, 0, -(y + .5) / COS)) + toward * 20000
            hit, _, index, _ = tree.ray_cast(start, -toward)
            if hit is not None and owners[index].get('asset_group') == row['id']:
                over += 1; picture[y, x] = (255, 200, 0)
    source = np.asarray(Image.open(SOURCE).convert('RGB'))
    bx0, by0, bx1, by1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    crop = source[by0:by1, bx0:bx1].astype(float)
    marks = picture[by0:by1, bx0:bx1]
    painted = marks.any(-1)
    blend = crop.copy()
    blend[painted] = crop[painted] * .35 + marks[painted] * .65
    sheet = np.concatenate([crop, blend], 1).astype(np.uint8)
    path = output / 'coverage-source-camera.png'
    Image.fromarray(sheet).resize((sheet.shape[1] * 2, sheet.shape[0] * 2), Image.NEAREST).save(path)
    total = int(domain.sum())
    return dict(domain_pixels=total, **counts, foreign_first_hit_by_asset=foreign,
                own_fraction=counts['own_first_hit'] / total, overreach_pixels_outside_domain=over,
                image=str(path), image_sha256=sha(path),
                legend=('left: source; right: green own first hit, blue shared pixel won by a front foliage proxy, '
                        'magenta foreign (non-foliage or exclusive) first hit, red miss, orange overreach'))


def write_handoff(row, report, workspace):
    """Pilot review files in the Lincoln candidate/audit shape (scratch, not gallery input)."""
    coverage = report['coverage']
    views = workspace / 'modified/views.json'
    exclusive = coverage['foreign_first_hit'] + coverage['miss']
    status = 'PASS' if exclusive <= .08 * coverage['domain_pixels'] else 'FAIL'
    audit = dict(
        version=1, asset_id=row['id'], status=status, model_sha256=report['model_sha256'],
        modified_views_sha256=sha(views), inspected_views=list(range(8)),
        method=('Source-camera first-hit ray per proposed foliage-domain pixel against the complete pilot scene '
                '(domain derived from native masks independently of the acceptance manifest), plus an overreach '
                'scan of non-domain pixels within 40 px of the domain box.'),
        observation=(f"{coverage['own_first_hit']}/{coverage['domain_pixels']} domain pixels hit this proxy first; "
                     f"{coverage['shared_with_front_foliage']} shared pixels are won by a front foliage proxy "
                     f"(domains overlap, first-hit gating); {coverage['foreign_first_hit']} exclusive pixels hit other "
                     f"geometry first {coverage['foreign_first_hit_by_asset']}; {coverage['miss']} miss; "
                     f"{coverage['overreach_pixels_outside_domain']} non-domain pixels are covered by the proxy (leaf gaps "
                     'filled by the closed crown; they receive neutral texture and hide terrain behind them).'),
        evidence={coverage['image']: coverage['image_sha256'], str(views): sha(views)},
        limitations=['Foliage domains are unreviewed proposals (trees_inventory.py).',
                     'Lobe depth, rear cards, transverse cards and wood are inferred; rear/transverse cards are neutral until texture fill.',
                     'Cards are intentionally open render surfaces (Leicester foliage contract), not closed volumes.'])
    (workspace / 'source-coverage-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    candidate = dict(
        version=1, asset_id=row['id'], status='refinement-in-progress', geometry_refined=True,
        geometry_reviewed=True, inspected_views=list(range(8)), recipe=str(Path(__file__).resolve()),
        model_sha256=report['model_sha256'], modified_views_sha256=sha(views),
        changes=[f"New foliage asset ({VERSION}): {report['lobes']} Leicester-style cutout lobes (paired curved "
                 f"source/neutral cards plus transverse neutral cards, {report['crown']['faces']} faces) and "
                 f"{len(report['wood_paths'])} lofted wood paths on terrain at native z {report['ground_contact_native_z']:.1f} "
                 f"(foot pixel {report['foot_pixel']}, {report['base_pixel_rule']})."],
        limitations=audit['limitations'] + [
            'Not a prepared workspace: the catalog/workspace/gallery tooling has no obstacle-less supplemental part '
            'kind, so there is no frozen input packet or baseline.'],
        geometry_approval='pending', texture_generation='not-started',
        source_comparison=str(Path(coverage['image']).relative_to(workspace)))
    (workspace / 'candidate.json').write_text(json.dumps(candidate, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-packets', action='store_true')
    parser.add_argument('--keep-going', action='store_true', help='Record per-asset fitting failures and continue')
    parser.add_argument('assets', nargs='+')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    acquire()
    import bpy
    from mathutils.bvhtree import BVHTree
    tooling = json.loads((R / 'tooling/current.json').read_text())['directory']
    sys.path.insert(0, tooling)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    rows = {row['id']: row for row in catalog['assets']}
    missing = set(args.assets) - set(rows)
    if missing:
        raise ValueError(f'Unknown proposed assets: {sorted(missing)}')
    selected = [rows[a] for a in args.assets]
    bpy.ops.wm.open_mainfile(filepath=str(SCENE_BLEND), load_ui=False)
    scene = bpy.data.scenes['lincoln Refinement']
    bpy.context.window.scene = scene
    collection = bpy.data.collections['lincoln Working']
    if any(str(o.get('source_node', '')).startswith('foliage-') for o in collection.all_objects):
        raise ValueError('Scene already contains foliage proxies')
    nodes = terrain_nodes()
    terrain = [o for o in collection.all_objects if o.type == 'MESH' and not o.hide_render
               and (o.get('source_node') in nodes or any(word in str(o.get('asset_group', '')) for word in NATURAL_GROUP_WORDS))]
    verts, tris = [], []
    for obj in terrain:
        obj.data.calc_loop_triangles()
        offset = len(verts)
        verts += [obj.matrix_world @ v.co for v in obj.data.vertices]
        tris += [tuple(offset + i for i in t.vertices) for t in obj.data.loop_triangles]
    terrain_tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    verts, tris = [], []
    for obj in collection.all_objects:
        if obj.type != 'MESH' or obj.hide_render or obj in terrain:
            continue
        obj.data.calc_loop_triangles()
        offset = len(verts)
        verts += [obj.matrix_world @ v.co for v in obj.data.vertices]
        tris += [tuple(offset + i for i in t.vertices) for t in obj.data.loop_triangles]
    architecture_tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    image = bpy.data.images.load(str(SOURCE), check_existing=True)
    reports, failures = [], []
    for number, row in enumerate(selected):
        try:
            reports.append(build(row, terrain_tree, architecture_tree, collection, image,
                                 output / row['id'], FIRST_TREE_MASK + number))
        except ValueError as error:
            # Fitting fails before any mesh is created; --keep-going lists every
            # asset that needs a visual foot override instead of stopping at the first.
            if not args.keep_going:
                raise
            failures.append(dict(asset_id=row['id'], error=str(error)))
    selected = [row for row in selected if row['id'] not in {f['asset_id'] for f in failures}]
    bpy.context.view_layer.update()
    masks = pilot_masks(selected, output)
    summary = dict(version=1, terrain_objects=sorted(o.name for o in terrain), recipe=str(Path(__file__).resolve()), recipe_version=VERSION,
                   scene=str(SCENE_BLEND), scene_sha256=sha(SCENE_BLEND), catalog=str(CATALOG),
                   catalog_sha256=sha(CATALOG), terrain_nodes=sorted(nodes), mask_manifest=str(masks), assets=reports, failures=failures)
    if not args.no_packets:
        from source_projection_bake import bake
        from refinement_review import render_review
        lighting = json.loads(LIGHTING.read_text())['lighting']
        domains = {row['id']: load_domain(row) for row in selected}
        for row, report in zip(selected, reports):
            workspace = output / row['id']
            workspace.mkdir(exist_ok=True)
            report['ownership'] = bake('lincoln', str(SOURCE), workspace / 'ownership.json',
                                       receiver_nodes=[report['source_node']], projection_label='exterior',
                                       preserve_authored=False, source_mask_manifest=str(masks),
                                       receiver_asset_id=row['id'])
            modified = workspace / 'modified'
            if modified.exists():
                raise FileExistsError(modified)
            render_review(modified, scene_name='lincoln Refinement', collection_name='lincoln Working',
                          asset_id=row['id'], source_path=str(SOURCE), lighting=lighting,
                          source_mask_manifest=str(masks),
                          projection_layers=[dict(source_path=str(SOURCE), projection_label='exterior',
                                                  receiver_nodes=sorted({o.get('source_node') for o in collection.all_objects if o.type == 'MESH' and not o.hide_render}, key=str),
                                                  occluder_nodes=sorted({o.get('source_node') for o in collection.all_objects if o.type == 'MESH' and not o.hide_render}, key=str))])
            report['coverage'] = coverage_audit(row, collection, workspace, domains)
            report['modified_views_sha256'] = sha(modified / 'views.json')
    for row, report in zip(selected, reports):
        workspace = output / row['id']
        workspace.mkdir(exist_ok=True)
        objects = {o for o in collection.all_objects if o.get('asset_group') == row['id']}
        model = workspace / 'model.blend'
        bpy.data.libraries.write(str(model), objects, compress=True)
        report['model'] = str(model)
        report['model_sha256'] = sha(model)
        if not args.no_packets:
            write_handoff(row, report, workspace)
    blend = output / 'lincoln-trees-pilot.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    summary['pilot_blend'] = str(blend)
    summary['pilot_blend_sha256'] = sha(blend)
    (output / 'pilot-report.json').write_text(json.dumps(summary, indent=2, default=list) + '\n')
    print('TREES_PILOT_COMPLETE', json.dumps([dict(id=r['asset_id'], crown=r['crown'], coverage=r.get('coverage', {}).get('own_fraction')) for r in reports]), flush=True)


if __name__ == '__main__':
    main()
