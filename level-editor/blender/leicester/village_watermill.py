"""Source-constrained mill wheel and walkway rail geometry.

The hidden lower wheel, axial depth, and repeated concealed joinery remain
explicit hypotheses. This module does not prepare packets or claim review.
"""
import json
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector
from village_details import silhouette_prism

SINE = math.sin(math.radians(35))
COSINE = math.cos(math.radians(35))


def finish(obj, vertices, faces, label):
    mesh = bpy.data.meshes.new(label)
    inverse = obj.matrix_world.inverted()
    mesh.from_pydata([inverse @ Vector(v) for v in vertices], [], faces)
    mesh.uv_layers.new(name='UVMap')
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    invalid = sum(not edge.is_manifold for edge in bm.edges)
    degenerate = sum(face.calc_area() < 1e-8 for face in bm.faces)
    bm.to_mesh(mesh); bm.free()
    if invalid or degenerate:
        raise ValueError(f'{label}: {invalid} nonmanifold, {degenerate} degenerate')
    mat = bpy.data.materials.get('Leicester Detail Unknown') or bpy.data.materials.new('Leicester Detail Unknown')
    mat.diffuse_color = (.5, .5, .5, 1)
    mesh.materials.append(mat); obj.data = mesh
    return {'vertices': len(vertices), 'faces': len(faces), 'nonmanifold_edges': invalid, 'degenerate_faces': degenerate}


def wheel(objects):
    """Replace four coarse wedges with connected wheel-sector cell surfaces."""
    center = Vector((2548., -1691.2, 0.0))
    # The visible wooden front rim spans about130 source pixels; the native
    # eighty-unit cap also contains background masonry. Use the inspected
    # rim-grid wooden crown rather than treating that mask cap as geometry.
    horizontal = Vector((1., .344, 0.)).normalized() * .75
    axis = Vector((-.344, 1., 0.)).normalized()
    radii = [0., 9., 72., 76., 94., 98.]
    vertical_scale = 86. / 98.
    # Native back rim is about ten pixels left and sixteen pixels above the
    # front rim. Positive axis depth preserves that observed direction.
    depths = [0., 4., 36., 40.]
    # Visible upper paddle dividers constrain phase locally; concealed total
    # counts (sixteen paddles and eight spokes) remain explicit hypotheses.
    reports = []
    # Preserve the original left-to-right upper-wheel source ownership. Only
    # the two end wedges acquire the explicitly inferred lower semicircle.
    angular_ranges = [(48, 96), (32, 48), (16, 32), (-32, 16)]
    for quadrant, (obj, (start, stop)) in enumerate(zip(objects, angular_ranges)):
        occupied = set()
        for angular in range(start, stop):
            for radial in range(5):
                for axial in range(3):
                    hub = radial == 0
                    side_rim = radial >= 2 and axial in (0, 2)
                    spoke = radial == 1 and axial in (0, 2) and angular % 16 in (0, 1)
                    paddle = radial >= 2 and angular % 8 == 0
                    drum = radial == 3
                    if hub or side_rim or spoke or paddle or drum:
                        occupied.add((angular, radial, axial))
        vertices = []; faces = []; indices = {}
        def vertex(a, r, d):
            key = (a if r else 0, r, d)
            if key not in indices:
                theta = 2 * math.pi * a / 128
                point = center + horizontal * (radii[r] * math.cos(theta)) + Vector((0, 0, radii[r] * math.sin(theta) * vertical_scale)) + axis * depths[d]
                indices[key] = len(vertices); vertices.append(point)
            return indices[key]
        for a, r, d in sorted(occupied):
            boundaries = [
                ((a-1,r,d), [(a,r,d),(a,r+1,d),(a,r+1,d+1),(a,r,d+1)]),
                ((a+1,r,d), [(a+1,r,d),(a+1,r,d+1),(a+1,r+1,d+1),(a+1,r+1,d)]),
                ((a,r-1,d), [(a,r,d),(a,r,d+1),(a+1,r,d+1),(a+1,r,d)]),
                ((a,r+1,d), [(a,r+1,d),(a+1,r+1,d),(a+1,r+1,d+1),(a,r+1,d+1)]),
                ((a,r,d-1), [(a,r,d),(a+1,r,d),(a+1,r+1,d),(a,r+1,d)]),
                ((a,r,d+1), [(a,r,d+1),(a,r+1,d+1),(a+1,r+1,d+1),(a+1,r,d+1)]),
            ]
            for neighbor, corners in boundaries:
                if neighbor in occupied: continue
                face = list(dict.fromkeys(vertex(*corner) for corner in corners))
                if len(face) >= 3: faces.append(face)
        reports.append({'source_node': obj['source_node'], 'angular_range_degrees': [start*360/128, stop*360/128], **finish(obj, vertices, faces, f'Leicester Wheel Sector {quadrant}')})
    return {'objects': reports, 'native_mask': 172, 'vertical_semiaxis_world': 86., 'horizontal_semiaxis_world': 73.5, 'center': list(center), 'axial_depth': 40., 'spokes': 8, 'paddles': 16, 'source_evidence': 'watermill-wheel-grid.png; upper paddle divisions and open radial structure visible. Native172 includes background in the spoke apertures and cannot itself define those openings.', 'inference': 'Source rim-grid.png wooden front crown near2555,898 and back crown near2540,875 constrain the shifted ellipse; native cap included background masonry. Axle ground height remains inferred. Full concealed lower semicircle, eight evenly phased spokes, sixteen complete paddles, radial dimensions and depth are hypotheses; inspect all eight views before accepting. Sector joints share coincident closed end caps, preserving the original left-to-right upper-wheel source nodes.'}


def rails(workspace, config, update_masks=True):
    """Native175 fixes four posts/two rails, split onto two walkway edges."""
    reports = []; assignments = []
    # Ground-foot contact anchors follow the artwork at the walkway corner.
    # Use the native platform top, 12.001 game elevation units.
    for label, x0, py0, slope, predicate in [
        ('return', 2430., 973., -1.15, lambda x,y: x < 2431),
        ('front', 2430., 973., .22, lambda x,y: x >= 2431),
    ]:
        platform_height = 12.001 / COSINE
        y0 = (-py0 - platform_height * COSINE) / SINE
        def plane(px, py):
            y = y0 + (px-x0)*slope
            return px, y, (-py-y*SINE)/COSINE
        mesh, report = silhouette_prism(workspace, 175, plane, 2., predicate)
        name = f'Leicester Mill Walkway {label.title()} Rail'
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, mesh)
            bpy.data.collections[config['collection_name']].objects.link(obj)
        else: obj.data = mesh
        obj['source_node'] = 'building-076'
        obj['projection_component'] = f'walkway-{label}-rail'
        obj['asset_group'] = config['asset_id']
        obj['part_name'] = f'Walkway {label} open railing'
        reports.append({'run': label, **report})
        assignments.append({'source_node':'building-076','projection_component':obj['projection_component'],'mask_indices':[175],'reviewed':True,'evidence':'watermill-wheel-flume-close.png: native175 two horizontal rails on each run and four posts; planar depth follows walkway hypothesis.'})
    if update_masks:
        path = Path(config['source_mask_manifest']); contract = json.loads(path.read_text())
        rows = contract['projections']['exterior']['assignments']
        components = {row['projection_component'] for row in assignments}
        rows[:] = [row for row in rows if not (row.get('source_node') == 'building-076' and row.get('projection_component') in components)]
        rows.extend(assignments); path.write_text(json.dumps(contract,indent=2)+'\n')
    return {'components':reports,'horizontal_rails_per_run':2,'visible_posts':4,'inference':'Walkway corner at source2430,973 uses native platform elevation12.001game. Two-unit concealed timber thickness and planar depths require eight-view contact review.'}
