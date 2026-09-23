"""Physical foliage cutout visibility, independent of source-ownership metadata."""
import math
from array import array


class OpacityRegistry:
    def __init__(self):
        self.records = []
        self.images = {}

    def add(self, obj, mesh, triangle):
        material = mesh.materials[triangle.material_index] if mesh.materials else None
        if not material or not material.get('foliage_physical_opacity'):
            self.records.append(None)
            return
        if material.get('opacity_semantics') != 'physical-coverage':
            raise ValueError('Foliage visibility requires physical-coverage semantics')
        shaders = [node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'] if material.use_nodes else []
        if len(shaders) != 1 or len(shaders[0].inputs['Alpha'].links) != 1:
            raise ValueError('Physical foliage requires one directly textured Principled alpha')
        link = shaders[0].inputs['Alpha'].links[0]
        texture = link.from_node
        if texture.type != 'TEX_IMAGE' or link.from_socket.name != 'Alpha' or not texture.image:
            raise ValueError('Physical coverage must come from an explicit image alpha socket')
        vector_links = texture.inputs['Vector'].links
        if vector_links:
            if len(vector_links) != 1 or vector_links[0].from_node.type != 'UVMAP':
                raise ValueError('Physical foliage ray tracing requires explicit untransformed UVs')
            layer = mesh.uv_layers.get(vector_links[0].from_node.uv_map)
        else:
            layer = next((uv for uv in mesh.uv_layers if uv.active_render), mesh.uv_layers.active)
        if layer is None:
            raise ValueError('Physical foliage has no UV map')
        image = texture.image
        if image not in self.images:
            pixels = array('f', [0]) * len(image.pixels)
            image.pixels.foreach_get(pixels)
            self.images[image] = (int(image.size[0]), int(image.size[1]), pixels[3::4])
        if texture.interpolation not in ('Closest', 'Linear') or texture.extension not in ('REPEAT', 'EXTEND', 'CLIP'):
            raise ValueError('Unsupported physical alpha sampling mode')
        points = tuple(obj.matrix_world @ mesh.vertices[i].co for i in triangle.vertices)
        uvs = tuple(tuple(layer.data[i].uv) for i in triangle.loops)
        cull = material.get('foliage_card_sides') == 'paired-one-sided' or material.use_backface_culling
        self.records.append((points, uvs, self.images[image], texture.interpolation, texture.extension, cull))

    def wrap(self, tree):
        return PhysicalOpacityTree(tree, self.records) if any(self.records) else tree


def _alpha(record, hit):
    points, uvs, (width, height, pixels), interpolation, extension, _ = record
    a, b, c = points
    ab, ac, ap = b-a, c-a, hit-a
    aa, bb, cc = ab.dot(ab), ab.dot(ac), ac.dot(ac)
    determinant = aa*cc-bb*bb
    if abs(determinant) < 1e-20:
        return 0
    u = (cc*ap.dot(ab)-bb*ap.dot(ac))/determinant
    v = (aa*ap.dot(ac)-bb*ap.dot(ab))/determinant
    uv = [uvs[0][i]*(1-u-v)+uvs[1][i]*u+uvs[2][i]*v for i in range(2)]
    if not all(math.isfinite(value) for value in uv) or width <= 0 or height <= 0:
        raise ValueError('Invalid physical opacity UV/image')
    def sample(x, y):
        if extension == 'REPEAT':
            x, y = x % width, y % height
        elif extension == 'CLIP' and not (0 <= x < width and 0 <= y < height):
            return 0
        else:
            x, y = min(width-1,max(0,x)), min(height-1,max(0,y))
        return pixels[y*width+x]
    if interpolation == 'Closest':
        return sample(math.floor(uv[0]*width), math.floor(uv[1]*height))
    x, y = uv[0]*width-.5, uv[1]*height-.5
    ix, iy = math.floor(x), math.floor(y)
    dx, dy = x-ix, y-iy
    return ((1-dx)*(1-dy)*sample(ix,iy)+dx*(1-dy)*sample(ix+1,iy)
            +(1-dx)*dy*sample(ix,iy+1)+dx*dy*sample(ix+1,iy+1))


class PhysicalOpacityTree:
    def __init__(self, tree, records):
        self.tree, self.records = tree, records

    def ray_cast(self, origin, direction, distance=float('inf')):
        direction = direction.normalized()
        start = origin.copy()
        for _ in range(len(self.records)+1):
            remaining = distance-(start-origin).length
            if remaining <= 0:
                return None, None, None, None
            hit, normal, index, _ = self.tree.ray_cast(start, direction, remaining)
            if hit is None:
                return None, None, None, None
            record = self.records[index]
            if record is None or ((not record[-1] or normal.dot(direction) < 0) and _alpha(record, hit) >= .5):
                return hit, normal, index, (hit-origin).length
            start = hit + direction*.001
        raise ValueError('Physical alpha visibility ray did not progress')
