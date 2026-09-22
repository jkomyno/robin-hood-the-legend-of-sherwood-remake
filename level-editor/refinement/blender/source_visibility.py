"""Source rays with explicitly reviewed, receiver-scoped foreground silhouettes."""


def first_source_hit(tree, owners, origin, direction, *, constraints=None,
                     receiver=None, source_pixel=None):
    """Continue past unsupported foreign hits, retaining every other depth blocker.

    The bitmap is queried at the requested source pixel, including for continuous
    subpixel rays. Geometry owned by the receiver's canonical part never skips.
    """
    if not constraints or not constraints.occluder_by_node:
        return tree.ray_cast(origin, direction)
    if receiver is None or source_pixel is None:
        raise ValueError('Scoped source visibility requires receiver and source pixel')
    start = origin.copy()
    # Advancing past a rejected triangle must terminate even for malformed meshes.
    for _ in range(len(owners) + 1):
        hit, normal, index, distance = tree.ray_cast(start, direction)
        if hit is None:
            return hit, normal, index, distance
        if constraints.occluder_supported(owners[index], receiver, *source_pixel):
            return hit, normal, index, (hit-origin).length
        start = hit + direction * .001
    raise ValueError('Reviewed source visibility ray did not progress')
