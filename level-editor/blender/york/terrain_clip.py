"""Subtract terrain prisms from textured triangles without moving retained surfaces.

Vertices contain XYZ followed by any interpolated corner attributes (UV channels).
Every cutter is bounded by its footprint, its top, and the global ground base.
"""
import math

EPS = 1e-7
# The reconstruction quantizes planes; near-zero bases can straddle Z=0.
GROUND_BASE = -.1


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def area(poly):
    a = poly[0]
    return sum(math.hypot(*cross([b[k]-a[k] for k in range(3)],
                                [c[k]-a[k] for k in range(3)]))/2
               for b, c in zip(poly[1:], poly[2:]))


def split(poly, plane):
    """Return positive and negative half-polygons, interpolating corner attributes."""
    n, offset = plane
    distances = [dot(n, p[:3])-offset for p in poly]
    if min(distances) >= -EPS:
        return poly, []
    if max(distances) <= EPS:
        return [], poly
    positive, negative = [], []
    for i, a in enumerate(poly):
        b = poly[(i+1) % len(poly)]
        da, db = distances[i], distances[(i+1) % len(poly)]
        (positive if da >= 0 else negative).append(a)
        if (da > 0 and db < 0) or (da < 0 and db > 0):
            t = da/(da-db)
            point = tuple(x+(y-x)*t for x, y in zip(a, b))
            positive.append(point); negative.append(point)
        elif da == 0:
            negative.append(a)
    return positive, negative


def prism(triangle, source):
    a, b, c = triangle
    n = cross([b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)])
    length = math.hypot(*n)
    if length < EPS or abs(n[2]) < length*.001:
        return None
    # All planes face outward. Negative is inside the terrain.
    if n[2] < 0:
        triangle = [a, c, b]
        n = tuple(-x for x in n)
    n = tuple(x/length for x in n)
    planes = [(n, dot(n, a)), ((0, 0, -1), -GROUND_BASE)]
    for a, b in zip(triangle, triangle[1:]+triangle[:1]):
        n = (b[1]-a[1], a[0]-b[0], 0)
        length = math.hypot(*n)
        n = tuple(x/length for x in n)
        planes.append((n, dot(n, a)))
    return {'source': source, 'planes': planes,
            'lo': [min(p[k] for p in triangle) if k < 2 else GROUND_BASE for k in range(3)],
            'hi': [max(p[k] for p in triangle) for k in range(3)]}


def subtract(poly, cutter):
    # Keep coplanar top faces: only strictly buried surfaces are removed.
    planes = cutter['planes']
    if min(dot(planes[0][0], p[:3])-planes[0][1] for p in poly) >= -EPS:
        return [poly], []
    inside, outside = poly, []
    for plane in planes:
        if not inside:
            break
        positive, inside = split(inside, plane)
        if len(positive) >= 3 and area(positive) > EPS:
            outside.append(positive)
    if len(inside) < 3 or area(inside) <= EPS:
        return [poly], []
    return outside, [inside]


def clip(triangle, cutters):
    lo = [min(p[k] for p in triangle) for k in range(3)]
    hi = [max(p[k] for p in triangle) for k in range(3)]
    pieces, removed = [triangle], []
    for cutter in cutters:
        if any(hi[k] < cutter['lo'][k]-EPS or lo[k] > cutter['hi'][k]+EPS for k in range(3)):
            continue
        remaining = []
        for poly in pieces:
            kept, buried = subtract(poly, cutter)
            remaining.extend(kept)
            removed.extend((p, cutter['source']) for p in buried)
        pieces = remaining
        if not pieces:
            break
    return pieces, removed
