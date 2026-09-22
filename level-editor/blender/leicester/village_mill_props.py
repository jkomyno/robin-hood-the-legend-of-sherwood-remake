"""Source-constrained furniture for the Leicester mill-south cottage.

Called from the cottage recipe; does not save scenes or generate review images.
"""
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def _replace(obj, vertices, faces, label):
    mesh = bpy.data.meshes.new(label)
    inverse = obj.matrix_world.inverted()
    mesh.from_pydata([inverse @ Vector(v) for v in vertices], [], faces)
    mesh.uv_layers.new(name='UVMap')
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bad = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
    volume = bm.calc_volume(signed=True)
    bm.to_mesh(mesh)
    bm.free()
    if bad or degenerate or volume <= 0:
        raise ValueError(f'{label}: invalid topology {bad}/{degenerate}/{volume}')
    material = bpy.data.materials.get('Leicester Detail Unknown') or bpy.data.materials.new('Leicester Detail Unknown')
    material.diffuse_color = (.5, .5, .5, 1)
    mesh.materials.append(material)
    obj.data = mesh
    return {'vertices': len(vertices), 'faces': len(faces), 'nonmanifold_edges': bad,
            'degenerate_faces': degenerate, 'signed_volume': volume}


def _furniture(obj, pixels, height, thickness, label):
    """One closed tabletop/seat with four attached legs and no internal faces."""
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    corners = [Vector((x, (-y - height*cosine)/sine, height)) for x, y in pixels]
    # The board's screen silhouette is measured; leg section and the hidden
    # fourth corner are inferred. Insets keep all legs beneath the board.
    us, vs = [0., .04, .19, .81, .96, 1.], [0., .07, .15, .85, .93, 1.]
    vertices, faces, lookup = [], [], {}

    def vertex(i, j, z):
        key = i, j, z
        if key not in lookup:
            u, v = us[i], vs[j]
            point = (1-u)*(1-v)*corners[0] + u*(1-v)*corners[1] + u*v*corners[2] + (1-u)*v*corners[3]
            point.z = z
            lookup[key] = len(vertices)
            vertices.append(tuple(point))
        return lookup[key]

    underside = {(i, j): 0. if i in (1, 3) and j in (1, 3) else height-thickness
                 for i in range(5) for j in range(5)}
    for i in range(5):
        for j in range(5):
            z = underside[i, j]
            ring = [(i, j), (i+1, j), (i+1, j+1), (i, j+1)]
            faces.append(tuple(vertex(a, b, height) for a, b in ring))
            faces.append(tuple(vertex(a, b, z) for a, b in reversed(ring)))
            for (a, b), (c, d), neighbor in [
                (ring[0], ring[1], (i, j-1)), (ring[1], ring[2], (i+1, j)),
                (ring[2], ring[3], (i, j+1)), (ring[3], ring[0], (i-1, j))]:
                upper = underside.get(neighbor, height)
                if upper > z:
                    faces.append((vertex(a, b, z), vertex(c, d, z), vertex(c, d, upper), vertex(a, b, upper)))
    report = _replace(obj, vertices, faces, label)
    report.update(source_board_corners=pixels, top_height=height, board_thickness=thickness,
                  legs=4, inference='Hidden depth follows a horizontal board solved at the inherited height. Four rectangular legs meet the underside without internal faces; leg insets/sections and occluded legs are inferred.')
    return report


def _bucket(obj):
    sine = math.sin(math.radians(35))
    center = Vector((3008., -1149.5/sine, 0.))
    # Follow the exterior up to the rim, then down the inner wall. Both end
    # caps lie below the mouth, leaving a real visible opening.
    profile = [(0., 5.8), (2., 6.3), (23.5, 7.4), (26.75, 7.5),
               (26.75, 6.), (18., 5.7)]
    segments, vertices, faces = 24, [], []
    for z, radius in profile:
        for i in range(segments):
            angle = 2*math.pi*i/segments
            vertices.append(tuple(center + Vector((radius*math.cos(angle), radius*math.sin(angle), z))))
    for row in range(len(profile)-1):
        for i in range(segments):
            a, b = row*segments+i, row*segments+(i+1)%segments
            faces.append((a, b, b+segments, a+segments))
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple(range((len(profile)-1)*segments, len(profile)*segments)))
    report = _replace(obj, vertices, faces, 'Leicester Mill Cottage Open Bucket')
    report.update(native_mask=165, radial_segments=segments, source_center_x=3008.,
                  ground_center_source_y=1149.5, rim_height=26.75, rim_radius=7.5,
                  interior_depth=8.75, inference='Native165 shows an open dark mouth and tapered stave sides. Rotational symmetry, radial depth and interior floor height are inferred; the inherited height and source width constrain the vessel. No handle is visible.')
    return report


def refine(workspace, config, bynode, update_masks=True):
    """Replace only nodes044/059/061; callers retain other cottage geometry."""
    def obj(node):
        return bynode.get(node) or bynode['building-'+node]
    table = _furniture(obj('044'), [(2852., 1171.), (2877., 1179.), (2906., 1144.), (2878., 1139.)],
                       23.25, 3., 'Leicester Mill Cottage Table')
    table.update(native_mask=161, visible_legs=3, visible_leg_source_x=[2855, 2877, 2901], hidden_legs=1)
    bench = _furniture(obj('059'), [(2962., 1135.), (2977., 1140.), (2993., 1121.), (2977., 1116.)],
                       15.75, 3., 'Leicester Mill Cottage Bench')
    bench.update(native_mask=169, visible_legs=1, visible_leg_source_x=[2966], occluded_or_inferred_legs=3,
                 foreground='Canopy post/frame crosses the center of native169; native162/166 are excluded from the bench receiver.')
    bucket = _bucket(obj('061'))
    if update_masks:
        path = Path(config['source_mask_manifest'])
        contract = json.loads(path.read_text())
        rows = contract['projections']['exterior']['assignments']
        bench_rows = [r for r in rows if r.get('source_node') == 'building-059' and not r.get('projection_component')]
        if len(bench_rows) != 1:
            raise ValueError('Expected one mill cottage bench ownership assignment')
        row = bench_rows[0]
        row['exclude_mask_indices'] = sorted(set(row.get('exclude_mask_indices', [])) | {162, 166})
        reason = 'Native169 foreground canopy support at x2974..2992/y1117..1139 belongs to native162/166, not the bench.'
        row.update(exclusions_reviewed=True, exclusion_reason=reason)
        if reason not in row.get('evidence', ''):
            row['evidence'] = row.get('evidence', '') + ' ' + reason
        path.write_text(json.dumps(contract, indent=2)+'\n')
    return {'table': table, 'bench': bench, 'bucket': bucket,
            'source_evidence': 'inspection/mill-furniture-source-close.png and mill-table-bench-grid.png',
            'limitations': 'Woodpile055 remains the inherited coarse volume. These recipes require fixed-camera projection and all eight actual-material views before approval.'}
