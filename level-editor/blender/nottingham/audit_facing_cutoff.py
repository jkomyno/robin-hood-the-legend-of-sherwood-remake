"""Read-only shortlist of pending town faces rejected by an elevated facing cutoff.

Geometric face shortlists and native-owned, scene-visible pixel witnesses are
reported separately. Policy changes still require visual review of the results.
Run Blender without an input file so the render lease precedes scene loading.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire
sys.path.insert(0, str(WORK / 'tooling-common-v1/2fbc2cbceea1fd2d'))
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints


def main():
    acquire()
    catalog = json.loads((WORK / 'grouping/catalog-v7.json').read_text())
    decisions = json.loads((WORK / 'approvals.json').read_text())
    approved = {row['asset_id'] for row in decisions['approvals']
                if row['decision'] == 'approved'}
    overrides = json.loads((WORK / 'workspace-overrides.json').read_text())['assets']
    angle = math.radians(35)
    toward = Vector((0, -math.cos(angle), math.sin(angle)))
    results = []
    for asset in catalog['groups']:
        nodes = {f"building-{part['obstacle']:03}" for part in asset['parts']}
        if (asset['id'] in approved or not nodes or
                max(part['obstacle'] for part in asset['parts']) >= 168):
            continue
        workspace = Path(overrides.get(asset['id'], WORK / 'round-1/assets' / asset['id']))
        path = workspace / 'model.blend'
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.view_layer.update()
        packet = json.loads((workspace / 'input/views.json').read_text())
        assert packet['elevation_degrees'] == 35, 'Unexpected source projection'
        faces = []
        for obj in bpy.data.collections['nottingham Working'].all_objects:
            cutoff = float(obj.get('projection_min_cosine', .05))
            if obj.type != 'MESH' or obj.get('source_node') not in nodes or cutoff <= .05:
                continue
            normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
            for face in obj.data.polygons:
                cosine = (normal_matrix @ face.normal).normalized().dot(toward)
                if not .05 < cosine < cutoff:
                    continue
                vertices = [obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
                pixels = [(v.x, -v.y * math.sin(angle) - v.z * math.cos(angle)) for v in vertices]
                area = abs(sum(a[0] * b[1] - b[0] * a[1]
                               for a, b in zip(pixels, pixels[1:] + pixels[:1]))) / 2
                if area < 1:
                    continue
                faces.append({'node': obj['source_node'], 'object': obj.name,
                              'face': face.index, 'cosine': cosine, 'cutoff': cutoff,
                              'projected_area_pixels': area, 'source_corners': pixels})
        visible = []
        if faces:
            source = bpy.data.images.load(packet['source_image'], check_existing=True)
            width, height = source.size
            constraints = SourceMaskConstraints(workspace / 'source-masks.json', 'exterior',
                                                packet['source_sha256'], (width, height))
            objects = [obj for obj in bpy.data.collections['nottingham Working'].all_objects
                       if obj.type == 'MESH' and not obj.hide_render]
            tree, owners, points = _tree(objects)
            depth = max(point.dot(toward) for point in points) + 10
            tested = set()
            for face in faces:
                pixels = face['source_corners']
                left = max(0, math.floor(min(p[0] for p in pixels)))
                right = min(width, math.ceil(max(p[0] for p in pixels)))
                top = max(0, math.floor(min(p[1] for p in pixels)))
                bottom = min(height, math.ceil(max(p[1] for p in pixels)))
                for y in range(top, bottom):
                    for x in range(left, right):
                        if (x, y) in tested:
                            continue
                        tested.add((x, y))
                        point = Vector((x + .5, -(y + .5) / math.sin(angle), 0))
                        origin = point + toward * (depth - point.dot(toward))
                        hit, normal, index, _ = tree.ray_cast(origin, -toward)
                        if index is None:
                            continue
                        obj = owners[index]
                        cosine = normal.dot(toward)
                        if (obj.get('source_node') in nodes and
                                .05 < cosine < float(obj.get('projection_min_cosine', .05)) and
                                constraints.allowed_pixel(obj, x, y)):
                            visible.append({'pixel': [x, y], 'node': obj['source_node'],
                                            'cosine': cosine})
        results.append({'asset_id': asset['id'], 'model': str(path),
                        'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'suspect_faces': faces, 'source_visible_rejected_pixels': visible})
        print(asset['id'], len(faces), 'candidate faces,', len(visible),
              'source-visible rejected pixels', flush=True)
    output = WORK / 'coordinator-audit/pending-town-facing-cutoff.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'version': 1,
        'limitation': 'Face area is geometric. Pixel witnesses separately require source-native ownership and full-scene first hit. No policy changes are made by this audit.',
        'assets': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()
