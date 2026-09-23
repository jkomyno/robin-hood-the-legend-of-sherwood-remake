"""Draw actual saved-mesh crease edges on unchanged source artwork."""
import sys
import json
import math
import hashlib
from pathlib import Path
sys.path[:0] = ['/usr/lib/python3.14', '/usr/lib/python3.14/lib-dynload',
    '/usr/lib/python3.14/site-packages', str(Path(__file__).parent)]
import bpy
from mathutils import Vector
from PIL import Image, ImageDraw
from refinement_review import _tree


def main():
    packet = Path(sys.argv[sys.argv.index('--')+1]).resolve()
    model = Path(bpy.data.filepath)
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    frame = json.loads((packet/'modified/views.json').read_text())
    all_objects = [o for o in bpy.data.collections['Derby Working'].all_objects
                   if o.type == 'MESH' and not o.hide_render]
    tree, _, _ = _tree(all_objects)
    elevation = math.radians(frame['elevation_degrees'])
    toward = Vector((0, -math.cos(elevation), math.sin(elevation)))
    bounds = frame['context_crop']
    box = tuple(bounds[k] for k in ('left','top','right','bottom'))
    art = Image.open(frame['source_image']).convert('RGB').crop(box)
    scale = 3
    overlay = art.resize((art.width*scale, art.height*scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(overlay)
    records = []
    def project(v):
        return (v.x-box[0], -v.y*math.sin(elevation)-v.z*math.cos(elevation)-box[1])
    for obj in all_objects:
        if obj.get('asset_group') != frame['asset_id']:
            continue
        mesh = obj.data
        face_normals = {}
        for polygon in mesh.polygons:
            for key in polygon.edge_keys:
                face_normals.setdefault(tuple(sorted(key)), []).append(polygon.normal)
        for edge in mesh.edges:
            normals = face_normals.get(tuple(sorted(edge.vertices)), [])
            if len(normals) == 2 and normals[0].dot(normals[1]) > .9999:
                continue
            a, b = [obj.matrix_world @ mesh.vertices[i].co for i in edge.vertices]
            pa, pb = project(a), project(b)
            length = math.dist(pa, pb)
            steps = max(1, math.ceil(length*4))
            previous = None
            count = 0
            for i in range(steps+1):
                p = a.lerp(b, i/steps)
                q = project(p)
                if not (0 <= q[0] < art.width and 0 <= q[1] < art.height):
                    previous = None
                    continue
                hit, normal, face, distance = tree.ray_cast(p+toward*10000, -toward, 10001)
                visible = hit is not None and (hit-p).length < .12
                if visible:
                    point = (q[0]*scale, q[1]*scale)
                    if previous is not None:
                        draw.line((previous,point), fill=(255,45,45), width=1)
                        count += 1
                    previous = point
                else:
                    previous = None
            if count:
                records.append(dict(object=obj.name, edge=edge.index,
                    vertex_indices=list(edge.vertices), world_endpoints=[list(a),list(b)],
                    visible_segments=count))
    output = packet/'modified'
    overlay.save(output/'mesh-on-artwork.png')
    original = art.resize(overlay.size, Image.Resampling.NEAREST)
    original.save(output/'original-artwork.png')
    comparison = Image.new('RGB', (overlay.width*2,overlay.height+30), '#202020')
    comparison.paste(original,(0,30)); comparison.paste(overlay,(overlay.width,30))
    labels=ImageDraw.Draw(comparison)
    labels.text((8,8),'Original artwork (nearest enlarged)',fill='white')
    labels.text((overlay.width+8,8),'Saved mesh visible crease edges (thin red)',fill='white')
    comparison.save(output/'original-mesh-comparison.png')
    assert hashlib.sha256(model.read_bytes()).hexdigest() == model_hash
    (packet/'edge-overlay-proof.json').write_text(json.dumps(dict(
        model=str(model), model_sha256=model_hash, model_unchanged=True,
        source_path=frame['source_image'], source_sha256=frame['source_sha256'],
        crop=box, scale=scale, source_elevation=frame['elevation_degrees'],
        sample_spacing_source_pixels=.25, visibility_world_tolerance=.12,
        visibility='Nearest ray hit against all visible Working meshes',
        limitation='Subpixel visibility tolerance; crease geometry is not an artwork annotation.',
        visible_edges=records),indent=2))
    print(f'Visible edges: {len(records)}; unchanged model {model_hash}',flush=True)


if __name__ == '__main__':
    main()
