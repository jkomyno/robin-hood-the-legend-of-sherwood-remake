import { readJson, subdir } from "./fs.ts";

export interface MissionCharacterProfile {
  kind: "pc" | "npc";
  profile: number | string;
  name: string;
  filename: string;
  profileName: string;
}

export function parseMissionCharacterCatalog(value: unknown): MissionCharacterProfile[] {
  const record = (value: unknown): Record<string, unknown> => {
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error("Invalid character profile catalog");
    return value as Record<string, unknown>;
  };
  const data = record(value);
  const result: MissionCharacterProfile[] = [];
  for (const [kind, field, orderField] of [
    ["pc", "characters", "character_order"],
    ["npc", "soldiers", "soldier_order"],
  ] as const) {
    const profiles = record(data[field]);
    const order = data[orderField];
    if (
      !Array.isArray(order) ||
      !order.every((key) => typeof key === "string" && Object.hasOwn(profiles, key)) ||
      new Set(order).size !== order.length ||
      order.length !== Object.keys(profiles).length
    )
      throw new Error(`Invalid ${orderField} in character catalog`);
    const entries = order.map((key) => {
      const profile = record(profiles[key]);
      if (
        typeof profile.filename !== "string" ||
        !profile.filename ||
        typeof profile.profile_name !== "string" ||
        !profile.profile_name
      )
        throw new Error(`Invalid character sprite profile ${key}`);
      const identifier = profile.filename
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "");
      if (!identifier) throw new Error(`Invalid character filename ${key}`);
      return {
        filename: profile.filename,
        profileName: profile.profile_name,
        name:
          typeof profile.display_name === "string" && profile.display_name.trim()
            ? profile.display_name
            : profile.filename.replace(/([a-z])([A-Z])/g, "$1 $2"),
        identifier,
      };
    });
    entries.forEach(({ identifier, ...entry }, index) =>
      result.push({
        ...entry,
        kind,
        profile:
          kind === "pc"
            ? index
            : entries.filter((other) => other.identifier === identifier).length > 1
              ? `${identifier}__${index}`
              : identifier,
      }),
    );
  }
  return result;
}

export async function loadMissionCharacterCatalog(library: FileSystemDirectoryHandle) {
  const root = await subdir(library, ["game-data"]);
  if (!root) throw new Error("The library has no game-data character sprites");
  const configuration = await subdir(root, ["Data", "Configuration"]);
  if (!configuration) throw new Error("The library has no character profile catalog");
  return {
    root,
    profiles: parseMissionCharacterCatalog(await readJson(configuration, "profile.cpf.json")),
  };
}
