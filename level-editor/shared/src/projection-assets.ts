import type { SightObstacle } from "./level.ts";

export type AssetState = "initial" | "applied";

/** Explicit endpoint membership: canonical nodes in descriptors, object IDs in documents. */
export interface AssetStates {
  active: AssetState;
  initial: string[];
  applied: string[];
}

/** A standalone model exported from a reviewed map, with local obstacles. */
export interface ProjectionAssetDescriptor {
  editor_usage?: "map-background";
  version: 1;
  kind: "projection-mapped-asset";
  id: string;
  name: string;
  source_map: string;
  model: string;
  source_origin_scene: [number, number, number];
  source_origin_game: [number, number, number];
  states?: AssetStates;
  /** Independent static models sharing an origin; these do not imply animation. */
  state_variants?: Partial<Record<AssetState, { name: string; model: string; parts?: ProjectionAssetDescriptor["parts"] }>>;
  /** Additional complete appearances; the primary model remains separately insertable. */
  standalone_variants?: ProjectionAssetDescriptor["state_variants"];
  parts: ({ node: string; name: string; default_hidden?: boolean; obstacle_local_game: SightObstacle } & (
    { source_obstacle: number; source_components?: string[]; mission_profile?: never } |
    { source_obstacle?: never; source_components?: never; mission_profile: string }
  ))[];
}

export interface ProjectionAssetEntry {
  asset_type?: string;
  tags?: string[];
  state_variant?: AssetState;
  editor_usage?: "map-background";
  id: string;
  name: string;
  source_map: string;
  descriptor: string;
  model: string;
}

/** Paths are relative to the granted library root; hashes pin saved instances. */
export interface ExternalAssetSource {
  state_variant?: AssetState;
  id: string;
  descriptor: string;
  model: string;
  descriptor_sha256: string;
  model_sha256: string;
}

export function assetVariantId(id: string, variant: AssetState): string {
  return `${id}--state-${variant}`;
}

export function assetNodeKey(id: string, node: string): string {
  return `asset:${id}:${node}`;
}

export function safeLibraryPath(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 &&
    !/[\\\0:#?%]/.test(value) &&
    value.split("/").every(part => part !== "" && part !== "." && part !== "..");
}
