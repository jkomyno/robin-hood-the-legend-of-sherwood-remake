import type { ProjectionAssetDescriptor, Vec3 } from "@rle/shared";

const coordinates = "Z-up mesh children; Y-up glTF map wrapper; units are map pixels";
export const staticMetadataKeys = ["coordinates", "anchor", "bounds_local_scene", "components"];
interface Metadata {
  coordinates?: string;
  anchor?: string;
  bounds_local_scene?: { min: Vec3; max: Vec3 };
  components?: Record<string, string | number | boolean>[];
}

/** Migrate only known descriptive fields; behavioral or spatial component metadata needs its own migration. */
export function readStaticAssetMetadata(descriptor: ProjectionAssetDescriptor): Metadata {
  const raw = descriptor as ProjectionAssetDescriptor & Record<string, unknown>;
  const result: Metadata = {};
  if (raw.coordinates !== undefined) {
    if (raw.coordinates !== coordinates) throw new Error("Unknown static asset coordinate frame");
    result.coordinates = coordinates;
  }
  if (raw.anchor !== undefined) {
    if (typeof raw.anchor !== "string" || !raw.anchor.trim())
      throw new Error("Invalid static asset anchor description");
    result.anchor = raw.anchor;
  }
  if (raw.bounds_local_scene !== undefined) {
    const bounds = raw.bounds_local_scene as { min?: unknown; max?: unknown };
    const vector = (v: unknown): v is Vec3 =>
      Array.isArray(v) && v.length === 3 && v.every(Number.isFinite);
    if (
      !result.coordinates ||
      !bounds ||
      typeof bounds !== "object" ||
      Object.keys(bounds).some((key) => key !== "min" && key !== "max") ||
      !vector(bounds.min) ||
      !vector(bounds.max)
    )
      throw new Error("Invalid static asset bounds");
    const maximum = bounds.max;
    if (bounds.min.some((v, i) => v > maximum[i]!)) throw new Error("Invalid static asset bounds");
    result.bounds_local_scene = { min: [...bounds.min], max: [...bounds.max] };
  }
  if (raw.components !== undefined) {
    if (!Array.isArray(raw.components)) throw new Error("Invalid static asset components");
    const strings = new Set([
      "name",
      "source_node",
      "editor_part_node",
      "projection_layer",
      "projection_component",
      "reprojection_geometry_sha256",
      "reprojection_source_sha256",
      "reprojection_ownership_label",
      "reprojection_ownership_source_sha256",
      "reprojection_receiver_layer",
      "reprojection_manifest_sha256",
      "reprojection_recipe_sha256",
      "reprojection_source_path",
    ]);
    const numbers = new Set([
      "step_count",
      "projection_min_cosine",
      "reprojection_known_texels",
      "reprojection_unknown_texels",
      "reprojection_projected_faces",
      "reprojection_fallback_faces",
    ]);
    const booleans = new Set(["default_hidden", "reprojection_ground_preserved"]);
    result.components = raw.components.map((value: unknown) => {
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error("Invalid static component");
      const component: Record<string, string | number | boolean> = {};
      for (const [key, v] of Object.entries(value)) {
        if (
          (strings.has(key) && typeof v === "string") ||
          (numbers.has(key) && typeof v === "number" && Number.isFinite(v)) ||
          (booleans.has(key) && typeof v === "boolean")
        )
          component[key] = v;
        else throw new Error(`Component metadata requires explicit migration: ${key}`);
      }
      if (
        typeof component.name !== "string" ||
        !descriptor.parts.some((part) => part.node === component.source_node) ||
        (component.editor_part_node !== undefined &&
          !descriptor.parts.some((part) => part.node === component.editor_part_node))
      )
        throw new Error("Static component must reference an owned part");
      return component;
    });
  }
  return result;
}

/** Bounds translate into the merged frame; component annotations remain attached to unchanged part nodes. */
export function mergeStaticAssetMetadata(inputs: { metadata: Metadata; offset: Vec3 }[]): Metadata {
  const result: Metadata = {};
  if (inputs.some(({ metadata }) => metadata.coordinates)) result.coordinates = coordinates;
  if (inputs.some(({ metadata }) => metadata.anchor))
    result.anchor = "Origin of the first constituent asset";
  if (inputs.some(({ metadata }) => metadata.components))
    result.components = inputs.flatMap(({ metadata }) =>
      structuredClone(metadata.components ?? []),
    );
  if (inputs.some(({ metadata }) => metadata.bounds_local_scene)) {
    if (inputs.some(({ metadata }) => !metadata.bounds_local_scene))
      throw new Error("Cannot merge incomplete asset bounds");
    const bound = (key: "min" | "max", select: (...v: number[]) => number): Vec3 =>
      [0, 1, 2].map((i) =>
        select(
          ...inputs.map(
            ({ metadata, offset }) => metadata.bounds_local_scene![key][i]! + offset[i]!,
          ),
        ),
      ) as Vec3;
    result.bounds_local_scene = { min: bound("min", Math.min), max: bound("max", Math.max) };
  }
  return result;
}
