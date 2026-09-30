import { readJson, subdir } from "./fs.ts";

export const DEFAULT_CHARACTER_DIRECTION = 8;

function englishSoldierName(name: string): string {
  const roles: Record<string, string> = {
    Hallebardier: "Halberdier",
    Epee: "Swordsman",
    Archer: "Archer",
    Officier: "Officer",
    Chevalier: "Knight",
    Lancier: "Spearman",
    Arbaletrier: "Crossbowman",
    Cavalier: "Cavalryman",
  };
  const colors: Record<string, string> = {
    Bleu: "Blue",
    Jaune: "Yellow",
    Orange: "Orange",
    Rouge: "Red",
    Noir: "Black",
    Vert: "Green",
  };
  const match =
    /^(Hallebardier|Epee|Archer|Officier|Chevalier|Lancier|Arbaletrier|Cavalier)( Special)? (Bleu|Jaune|Orange|Rouge|Noir|Vert)( Mechant)?$/.exec(
      name,
    );
  if (match)
    return `${colors[match[3]!]} ${match[2] ? "Special " : ""}${roles[match[1]!]}${match[4] ? " (Hostile)" : ""}`;
  if (name === "Mmen Arc") return "Merry Man (Bow)";
  if (name === "Mmen Baton") return "Merry Man (Staff)";
  return name.replace(/^Ne pas utiliser(\d+)$/, "Unused $1");
}

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
      const name =
        typeof profile.display_name === "string" && profile.display_name.trim()
          ? profile.display_name.trim()
          : profile.filename.replace(/([a-z])([A-Z])/g, "$1 $2");
      return {
        filename: profile.filename,
        profileName: profile.profile_name,
        name: kind === "npc" ? englishSoldierName(name) : name,
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
