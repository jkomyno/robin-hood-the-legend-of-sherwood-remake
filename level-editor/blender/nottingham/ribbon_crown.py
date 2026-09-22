"""Closed crenellated ribbons measured along paired wall centerlines."""

import math


def arc_ribbon_geometry(points, pairs, notches, base=0, notch_depth=18):
    """Return vertices/faces for a capped ribbon with normalized notch intervals.

    ``pairs`` orders outer/inner point indices along an open wall. Each point
    supplies x, y and z_top. Distances use successive paired midpoints in the
    native x/y plane; notch endpoints are normalized to the total distance.
    C-shaped walls retain their opening: the first/last pairs are end caps,
    never connected across the opening. Hidden depth is controlled by ``base``.
    Recalculate face normals after importing the returned mesh into Blender.
    """
    if len(pairs) < 2:
        raise ValueError("A ribbon requires at least two cross-section pairs")
    if not math.isfinite(base) or not math.isfinite(notch_depth) or notch_depth <= 0:
        raise ValueError("Base must be finite and notch depth must be positive")
    for pair in pairs:
        if len(pair) != 2 or any(i < 0 or i >= len(points) for i in pair):
            raise ValueError("Invalid ribbon cross-section indices")
        for i in pair:
            if not all(math.isfinite(points[i][k]) for k in ("x", "y", "z_top")):
                raise ValueError("Ribbon points must have finite coordinates")
            if points[i]["z_top"] - notch_depth <= base:
                raise ValueError("Notch bottom must remain above the ribbon base")
    intervals = sorted(tuple(map(float, interval)) for interval in notches)
    for interval in intervals:
        if len(interval) != 2 or not 0 <= interval[0] < interval[1] <= 1:
            raise ValueError("Notches must be nonempty intervals within [0, 1]")
    midpoints = [tuple((points[a][k] + points[b][k]) / 2 for k in ("x", "y"))
                 for a, b in pairs]
    cumulative = [0.0]
    for a, b in zip(midpoints, midpoints[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length <= 1e-8:
            raise ValueError("Ribbon cross-sections must have distinct midpoints")
        cumulative.append(cumulative[-1] + length)
    cumulative = [distance / cumulative[-1] for distance in cumulative]
    vertices, indices, faces = [], {}, {}

    def vertex(coordinate):
        key = tuple(round(value, 6) for value in coordinate)
        if key not in indices:
            indices[key] = len(vertices)
            vertices.append(key)
        return indices[key]

    def face(coordinates):
        ids = [vertex(coordinate) for coordinate in coordinates]
        if len(set(ids)) != len(ids):
            raise ValueError("Ribbon contains a collapsed face")
        key = tuple(sorted(ids))
        if key in faces:
            del faces[key]
        else:
            faces[key] = ids

    def interpolate(a, b, t, level):
        top = a["z_top"] + (b["z_top"] - a["z_top"]) * t
        z = base if level == "base" else top - notch_depth if level == "low" else top
        return (a["x"] + (b["x"] - a["x"]) * t,
                a["y"] + (b["y"] - a["y"]) * t, z)

    def cell(a, b, c, d, lo, hi, bottom, top):
        al, ar = interpolate(a, c, lo, bottom), interpolate(a, c, hi, bottom)
        bl, br = interpolate(b, d, lo, bottom), interpolate(b, d, hi, bottom)
        atl, atr = interpolate(a, c, lo, top), interpolate(a, c, hi, top)
        btl, btr = interpolate(b, d, lo, top), interpolate(b, d, hi, top)
        for coordinates in ([al, ar, atr, atl], [br, bl, btl, btr],
                            [atl, atr, btr, btl], [bl, br, ar, al],
                            [bl, al, atl, btl], [ar, br, btr, atr]):
            face(coordinates)

    for i, ((ai, bi), (ci, di)) in enumerate(zip(pairs, pairs[1:])):
        start, end = cumulative[i:i + 2]
        cuts = {0.0, 1.0}
        for interval in intervals:
            for endpoint in interval:
                if start < endpoint < end:
                    cuts.add((endpoint - start) / (end - start))
        cuts = sorted(cuts)
        a, b, c, d = (points[index] for index in (ai, bi, ci, di))
        for lo, hi in zip(cuts, cuts[1:]):
            middle = start + (end - start) * (lo + hi) / 2
            cell(a, b, c, d, lo, hi, "base", "low")
            if not any(left < middle < right for left, right in intervals):
                cell(a, b, c, d, lo, hi, "low", "top")
    return vertices, list(faces.values())
