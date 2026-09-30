import { validateMission, type EditorMission, type ProtoLevel, type Vec3 } from "@rle/shared";
import type { DatadirIndex } from "./datadir.ts";
import type { MissionData } from "./mission.ts";
import { placementHeight } from "./entity-projection.ts";
import { readJson, subdir } from "./fs.ts";
import {
  loadMissionCharacterCatalog,
  parseMissionCharacterCatalog,
  type MissionCharacterProfile,
} from "./mission-character-catalog.ts";

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error(`${label}: expected object`);
  return value as Record<string, unknown>;
}
function integer(value: unknown, label: string, max = 0xffffffff): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0 || value > max)
    throw new Error(`${label}: invalid integer`);
  return value;
}
function finite(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new Error(`${label}: invalid coordinate`);
  return value;
}

/** Resolve source topology once; the editable mission stores portable world positions. */
export function importMission(
  mission: MissionData,
  level: ProtoLevel,
  configuration: unknown,
  libraryProfiles: readonly MissionCharacterProfile[],
) {
  const config = record(configuration, "character profiles");
  const sourceProfiles = parseMissionCharacterCatalog(config);
  const warnings: string[] = [];
  const result: EditorMission = {
    version: 1,
    spawnPoints: [],
    soldiers: [],
    importedFrom: mission.name,
    importWarnings: warnings,
  };
  const arrays = (key: string): unknown[] => {
    const value = mission.data[key] ?? [];
    if (!Array.isArray(value)) throw new Error(`${key}: expected array`);
    return value;
  };
  const match = (source: MissionCharacterProfile | undefined) => {
    if (!source) throw new Error("missing source character profile");
    const matches = libraryProfiles.filter(
      (profile) =>
        profile.kind === source.kind &&
        profile.filename.toLowerCase() === source.filename.toLowerCase() &&
        profile.profileName === source.profileName &&
        profile.name === source.name,
    );
    if (matches.length !== 1)
      throw new Error(`missing or ambiguous library character ${source.name}`);
    return matches[0]!;
  };
  const position = (entity: Record<string, unknown>): Vec3 => {
    const p = entity.position === undefined ? null : record(entity.position, "position");
    const x = finite(p ? p.x : entity.position_x, "x");
    const y = finite(p ? p.y : entity.position_y, "y");
    const support = integer(
      entity.obstacle_index ?? entity.projection_area ?? 65535,
      "support",
      65535,
    );
    const explicit = entity.position_z === undefined ? -1 : finite(entity.position_z, "height");
    let z = Math.max(0, explicit);
    if (explicit < 0 && support !== 65535) {
      const obstacle = level.sight_obstacles[support];
      if (!obstacle) throw new Error(`missing receiving surface ${support}`);
      z = placementHeight(x, y, obstacle);
    }
    return [x, y + z, z];
  };
  const sourceSoldiers = sourceProfiles.filter((profile) => profile.kind === "npc");
  const soldierOrder = config.soldier_order as string[];
  const soldiers = record(config.soldiers, "soldier profiles");
  for (const [index, raw] of arrays("soldiers").entries()) {
    try {
      const entity = record(raw, "soldier");
      const slot = integer(entity.profile_number, "soldier profile");
      const source =
        entity.profile_id == null
          ? sourceSoldiers[slot]
          : sourceSoldiers.find((profile) => profile.profile === entity.profile_id);
      const profile = match(source);
      if (typeof profile.profile !== "string") throw new Error("soldier has a PC profile");
      const sourceSlot = sourceSoldiers.indexOf(source!);
      const definition = record(soldiers[soldierOrder[sourceSlot]!], "soldier definition");
      if (entity.allegiance == null && typeof definition.hostile !== "boolean")
        throw new Error("missing soldier hostility");
      result.soldiers.push({
        id: `import-soldier-${index}`,
        name: profile.name,
        profile: profile.profile,
        position: position(entity),
        direction: integer(entity.direction, "direction", 15),
        allegiance: integer(entity.allegiance ?? (definition.hostile ? 1 : 0), "allegiance", 65535),
      });
    } catch (error) {
      warnings.push(`Soldier ${index + 1} omitted: ${String(error)}`);
    }
  }
  const requiredNames = [
    "",
    "Frere Tuck",
    "Lady Marianne",
    "Petit Jean",
    "Robin des bois",
    "Stutely",
    "Will Ecarlate",
  ];
  for (const [index, raw] of arrays("beam_mes").entries()) {
    try {
      const entity = record(raw, "spawn");
      const required = integer(entity.required_pc ?? 0, "required character", 6);
      let source: MissionCharacterProfile | undefined;
      if (entity.profile_override != null)
        source = sourceProfiles.find(
          (p) =>
            p.kind === "pc" && p.profile === integer(entity.profile_override, "profile override"),
        );
      else if (required)
        source = sourceProfiles.find(
          (p) =>
            p.kind === "pc" &&
            p.profileName.toLowerCase() === requiredNames[required]!.toLowerCase(),
        );
      const profile = entity.profile_override != null || required ? match(source) : undefined;
      if (profile && typeof profile.profile !== "number")
        throw new Error("spawn has a soldier profile");
      result.spawnPoints.push({
        id: `import-spawn-${index}`,
        name: profile?.name ?? `Campaign spawn ${index + 1}`,
        position: position(entity),
        direction: integer(entity.direction, "direction", 15),
        ...(profile && typeof profile.profile === "number" ? { profile: profile.profile } : {}),
      });
    } catch (error) {
      warnings.push(`Spawn ${index + 1} omitted: ${String(error)}`);
    }
  }
  const generic = result.spawnPoints.filter((spawn) => spawn.profile === undefined).length;
  if (generic)
    warnings.push(
      `${generic} spawn slots use campaign team selection; assign characters in Mission to make a fixed roster.`,
    );
  if (result.spawnPoints.some((spawn) => spawn.profile !== undefined))
    warnings.push(
      "Named starting characters become fixed PC placements rather than campaign availability requirements.",
    );
  for (const [key, label] of [
    ["civilians", "civilians"],
    ["pcs_to_rescue", "rescue characters"],
    ["targets", "targets"],
    ["bonuses", "pickups"],
    ["scrolls", "scrolls"],
    ["mission_patches", "mission patch states"],
    ["building_tenants", "building tenants"],
    ["hiking_paths", "patrol paths"],
    ["mobile_elements", "moving scenery"],
  ]) {
    const count = arrays(key!).length;
    if (count) warnings.push(`${count} ${label} are not supported by editable mission export.`);
  }
  if (
    mission.data.script_objects &&
    Object.keys(record(mission.data.script_objects, "script objects")).length
  )
    warnings.push("Mission script objects are not supported by editable mission export.");
  warnings.push(
    "Mission scripts, objectives, ambience, timed rules, tactics, starting actions, soldier AI roles, inventory and campaign/skill requirements are not imported. Only character placements, profiles, facing and allegiance are editable/exported.",
  );
  validateMission(result);
  return result;
}

export async function loadEditableMission(
  index: DatadirIndex,
  mission: MissionData,
  level: ProtoLevel,
  library: FileSystemDirectoryHandle,
) {
  if (!index.root) throw new Error("Game data root missing for mission import");
  const configuration = await subdir(index.root, ["Data", "Configuration"]);
  if (!configuration) throw new Error("Mission import requires Data/Configuration");
  const [source, catalog] = await Promise.all([
    readJson(configuration, "profile.cpf.json"),
    loadMissionCharacterCatalog(library),
  ]);
  return importMission(mission, level, source, catalog.profiles);
}

/** Noneditable entities can still be inspected without duplicating imported actors. */
export function remainingMissionPreview(mission: MissionData): MissionData {
  return { ...mission, data: { ...mission.data, soldiers: [], beam_mes: [] } };
}
