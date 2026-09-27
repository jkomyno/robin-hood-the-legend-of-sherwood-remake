import ClipperLib from "clipper-lib";
import type { MultiPolygon, Polygon } from "polygon-clipping";
import type { Point } from "@rle/shared";

type Geometry = Polygon | MultiPolygon;
type Operation = "union" | "intersection" | "difference" | "xor";
const kinds = {
  union: ClipperLib.ClipType.ctUnion,
  intersection: ClipperLib.ClipType.ctIntersection,
  difference: ClipperLib.ClipType.ctDifference,
  xor: ClipperLib.ClipType.ctXor,
};

/** Fixed-point boolean geometry for offline terrain recovery, retaining explicit hole nesting. */
export function recoveryPolygonBoolean(
  operation: Operation,
  subject: Geometry,
  clips: Geometry[] = [],
  scale = 1048576,
): MultiPolygon {
  const paths = (geometry: Geometry): ClipperLib.Paths => {
    if (!geometry.length) return [];
    const polygons = Array.isArray(geometry[0]?.[0]?.[0])
      ? (geometry as MultiPolygon)
      : [geometry as Polygon];
    return polygons.flatMap((polygon) =>
      polygon.map((ring, index) => {
        const path = ring.map(([x, y]) => {
          const X = Math.round(x * scale),
            Y = Math.round(y * scale);
          if (![X, Y].every((n) => Number.isSafeInteger(n) && Math.abs(n) <= 2 ** 52 - 1))
            throw new Error("Recovered polygon exceeds fixed-point coordinate range");
          return { X, Y };
        });
        if (ClipperLib.Clipper.Orientation(path) !== (index === 0)) path.reverse();
        return path;
      }),
    );
  };
  const subjectPaths = paths(subject),
    clipPaths = clips.flatMap(paths);
  if (
    (!subjectPaths.length && !clipPaths.length) ||
    (!subjectPaths.length && operation !== "union" && operation !== "xor")
  )
    return [];
  const clipper = new ClipperLib.Clipper();
  clipper.StrictlySimple = true;
  clipper.AddPaths(subjectPaths, ClipperLib.PolyType.ptSubject, true);
  clipper.AddPaths(clipPaths, ClipperLib.PolyType.ptClip, true);
  const result = new ClipperLib.PolyTree();
  if (
    !clipper.Execute(
      kinds[operation],
      result,
      ClipperLib.PolyFillType.pftNonZero,
      ClipperLib.PolyFillType.pftNonZero,
    )
  )
    throw new Error(`Recovered polygon ${operation} failed`);
  const ring = (node: ClipperLib.PolyNode): Point[] => {
    const points = node.Contour().map(({ X, Y }): Point => [X / scale, Y / scale]);
    return [...points, points[0]!];
  };
  const output: MultiPolygon = [];
  const visit = (parent: ClipperLib.PolyNode) => {
    for (const node of parent.Childs()) {
      if (!node.IsHole())
        output.push([
          ring(node),
          ...node
            .Childs()
            .filter((child) => child.IsHole())
            .map(ring),
        ]);
      visit(node);
    }
  };
  visit(result);
  return output;
}

export const recoveryClipping = {
  union: (subject: Geometry, ...clips: Geometry[]) =>
    recoveryPolygonBoolean("union", subject, clips),
  difference: (subject: Geometry, ...clips: Geometry[]) =>
    recoveryPolygonBoolean("difference", subject, clips),
  intersection: (subject: Geometry, ...clips: Geometry[]) =>
    clips.reduce<MultiPolygon>(
      (result, clip) => recoveryPolygonBoolean("intersection", result, [clip]),
      recoveryPolygonBoolean("union", subject),
    ),
  xor: (subject: Geometry, ...clips: Geometry[]) =>
    clips.reduce<MultiPolygon>(
      (result, clip) => recoveryPolygonBoolean("xor", result, [clip]),
      recoveryPolygonBoolean("union", subject),
    ),
};
