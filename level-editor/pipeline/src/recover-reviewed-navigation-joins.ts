import type { Level3D } from "../../shared/src/level3d.ts";
import { partMatrix } from "../../shared/src/level3d.ts";
import { gameToScene, type Vec3 } from "../../shared/src/scene.ts";
import { applyAffineMatrix, sceneToGame } from "../../shared/src/geometry.ts";
import type { ProtoLevel } from "../../shared/src/level.ts";
import {
  assembleNavigationJoins,
  orientNavigationJoin,
  type NavigationJoin,
  type PlacedNavigationJoin,
} from "../../shared/src/assemble-navigation-joins.ts";
import type { RecoveredGameplayPacket, RecoveredSurface } from "./recovered-gameplay-definition.ts";
import { heightPlane, planeHeight } from "../../shared/src/gameplay-plane.ts";

export interface ReviewedNavigationJoins {
  source_sha256: string;
  regions: {
    id: string;
    entries: {
      asset: string;
      model_sha256: string;
      surface: string;
      node: string;
      source_obstacle: number;
      edges: NavigationJoin[];
      heightTolerance?: number;
      /** Reviewed asset-local movement boundary, independent of its receiving footprint. */
      vertices?: Vec3[];
      holes?: Vec3[][];
    }[];
  }[];
}

/** One-time authoring of reviewed seams. Source identities validate provenance only;
 * returned surface definitions contain local geometry and local region labels. */
export function recoverReviewedNavigationJoins(
  document: Level3D,
  source: Pick<ProtoLevel, "sight_obstacles" | "lifts">,
  sourceSha256: string,
  definitions: ReviewedNavigationJoins,
  packets: ReadonlyMap<string, RecoveredGameplayPacket>,
) {
  if (definitions.source_sha256 !== sourceSha256)
    throw new Error("Reviewed navigation source changed");
  if (!Array.isArray(definitions.regions) || !definitions.regions.length)
    throw new Error("Reviewed navigation joins need regions");
  const seenRegions = new Set<string>(),
    seenSurfaces = new Set<string>();
  const updates: {
    asset: string;
    surface: RecoveredSurface;
    region: string;
    edges: NavigationJoin[];
    heightTolerance?: number;
    vertices?: Vec3[];
    holes?: Vec3[][];
  }[] = [];
  for (const region of definitions.regions) {
    if (
      typeof region.id !== "string" ||
      !region.id.trim() ||
      seenRegions.has(region.id) ||
      !Array.isArray(region.entries) ||
      region.entries.length < 2
    )
      throw new Error("Reviewed navigation region needs a unique label and multiple surfaces");
    seenRegions.add(region.id);
    let receiving: string | undefined;
    const joins: PlacedNavigationJoin[] = [];
    for (const entry of region.entries) {
      const reference = document.assetSources?.find((a) => a.id === entry.asset);
      if (!reference || reference.model_sha256 !== entry.model_sha256)
        throw new Error(`Reviewed navigation model changed: ${entry.asset}`);
      const parts = document.objects.filter((p) => p.node === `asset:${entry.asset}:${entry.node}`);
      const surfaces =
        packets.get(entry.asset)?.surfaces.filter((s) => s.id === entry.surface) ?? [];
      const part = parts[0],
        surface = surfaces[0];
      const key = `${entry.asset}/${entry.surface}`;
      if (
        parts.length !== 1 ||
        surfaces.length !== 1 ||
        !part ||
        !surface ||
        surface.node !== entry.node ||
        surface.kind === "lift" ||
        seenSurfaces.has(key)
      )
        throw new Error(`Reviewed navigation needs one ordinary surface and placement: ${key}`);
      seenSurfaces.add(key);
      if (
        (surface.navigationRegion !== undefined && surface.navigationRegion !== region.id) ||
        surface.navigationJoins !== undefined
      )
        throw new Error(`Reviewed navigation conflicts with existing authoring: ${key}`);
      const obstacle = source.sight_obstacles[entry.source_obstacle];
      const projection = obstacle?.projection_area;
      if (
        !Number.isInteger(entry.source_obstacle) ||
        part.source.obstacle !== entry.source_obstacle ||
        !obstacle ||
        !Array.isArray(projection) ||
        source.lifts.some((l) => l.motion_area_index === projection[0])
      )
        throw new Error(`Reviewed navigation source owner is not an ordinary projection: ${key}`);
      const binding = JSON.stringify(projection);
      if (receiving !== undefined && receiving !== binding)
        throw new Error(
          `Reviewed navigation would join distinct source movement regions: ${region.id}`,
        );
      receiving = binding;
      if (
        entry.heightTolerance !== undefined &&
        (!Number.isFinite(entry.heightTolerance) || entry.heightTolerance < 0)
      )
        throw new Error(`Invalid reviewed navigation height tolerance: ${key}`);
      if (entry.vertices !== undefined || entry.holes !== undefined) {
        const rings = [entry.vertices, ...(entry.holes ?? [])];
        const plane = heightPlane(surface.vertices);
        if (
          rings.some(
            (ring) =>
              !Array.isArray(ring) ||
              ring.length < 3 ||
              ring.some(
                (p) =>
                  !Array.isArray(p) ||
                  p.length !== 3 ||
                  !p.every(Number.isFinite) ||
                  Math.abs(planeHeight(plane, [p[0], p[1]]) - p[2]) > 1e-4,
              ),
          )
        )
          throw new Error(
            `Reviewed navigation contour must retain its receiving height plane: ${key}`,
          );
      }
      if (
        !Array.isArray(entry.edges) ||
        entry.edges.some(
          (edge) =>
            !Array.isArray(edge) ||
            edge.length !== 2 ||
            edge.some((p) => !Array.isArray(p) || p.length !== 3 || !p.every(Number.isFinite)),
        )
      )
        throw new Error(`Invalid reviewed navigation edge: ${key}`);
      const matrix = partMatrix(document.camera, document, part);
      const place = (point: Vec3) =>
        sceneToGame(
          document.camera,
          applyAffineMatrix(matrix, gameToScene(document.camera, ...point)),
        );
      for (const edge of entry.edges)
        joins.push({
          region: `${entry.asset}/${region.id}`,
          owner: entry.asset,
          heightTolerance: entry.heightTolerance,
          edge: orientNavigationJoin((entry.vertices ?? surface.vertices).map(place), [
            place(edge[0]),
            place(edge[1]),
          ]),
        });
      updates.push({
        asset: entry.asset,
        surface,
        region: region.id,
        edges: structuredClone(entry.edges),
        heightTolerance: entry.heightTolerance,
        vertices: entry.vertices === undefined ? undefined : structuredClone(entry.vertices),
        holes: entry.vertices === undefined ? undefined : structuredClone(entry.holes ?? []),
      });
    }
    const assembled = assembleNavigationJoins(joins);
    if (
      assembled.unmatched.length ||
      new Set(assembled.identities.values()).size !== 1 ||
      region.entries.some((entry) => !assembled.identities.has(`${entry.asset}/${region.id}`))
    )
      throw new Error(`Reviewed navigation region has detached edges or components: ${region.id}`);
  }
  // Validate the whole catalog before the caller mutates any authoring packets.
  return updates;
}
