import test from "node:test";
import assert from "node:assert/strict";
import { type ProtoLevel, validateMission } from "@rle/shared";
import { importMission, remainingMissionPreview } from "./import-mission.ts";
import { parseMissionCharacterCatalog } from "./mission-character-catalog.ts";
import type { MissionData } from "./mission.ts";

const config = {
  character_order: ["Robin", "Tuck"],
  characters: {
    Robin: { filename: "RobinHood", profile_name: "Robin des bois", display_name: "Robin Hood" },
    Tuck: { filename: "Friar Tuck", profile_name: "Frere Tuck", display_name: "Friar Tuck" },
  },
  soldier_order: ["enemy", "friend"],
  soldiers: {
    enemy: {
      filename: "Guard A05",
      profile_name: "Garde A",
      display_name: "Hallebardier Vert Mechant",
      hostile: true,
    },
    friend: {
      filename: "Guard A05",
      profile_name: "Garde A",
      display_name: "Hallebardier Vert",
      hostile: false,
    },
  },
};
const target = {
  ...config,
  soldier_order: ["friend", "enemy"],
  character_order: ["Tuck", "Robin"],
};
const level = {
  sight_obstacles: [
    {
      points: [
        { x: 0, y: 20, z_top: 20 },
        { x: 100, y: 20, z_top: 20 },
        { x: 0, y: 120, z_top: 20 },
      ],
    },
  ],
} as ProtoLevel;
const beam = { position: { x: 30, y: 40 }, direction: 7, projection_area: 0, required_pc: 0 };
const soldier = {
  position_x: 40,
  position_y: 50,
  direction: 3,
  obstacle_index: 0,
  profile_number: 0,
};

test("mission import remaps profiles, resolves heights and retains generic campaign slots", () => {
  const source: MissionData = {
    name: "Sample",
    map: "Derby",
    data: {
      beam_mes: [beam, { ...beam, required_pc: 1 }, { ...beam, profile_override: 0 }],
      soldiers: [
        soldier,
        { ...soldier, profile_number: 1 },
        { ...soldier, allegiance: 12, position_z: 35 },
      ],
      civilians: [{ example: true }],
      hiking_paths: [[]],
      script_objects: { globals: [] },
    },
  };
  const result = importMission(source, level, config, parseMissionCharacterCatalog(target));
  assert.deepEqual(
    result.spawnPoints.map((spawn) => spawn.profile),
    [undefined, 0, 1],
  );
  assert.deepEqual(result.spawnPoints[0]!.position, [30, 60, 20]);
  assert.equal(result.spawnPoints[0]!.direction, 7);
  assert.deepEqual(
    result.soldiers.map((entry) => entry.profile),
    ["guard_a05__1", "guard_a05__0", "guard_a05__1"],
  );
  assert.deepEqual(
    result.soldiers.map((entry) => entry.allegiance),
    [1, 0, 12],
  );
  assert.deepEqual(result.soldiers[2]!.position, [40, 85, 35]);
  assert.equal(result.soldiers[0]!.name, "Green Halberdier (Hostile)");
  assert.equal(result.importedFrom, "Sample");
  assert.ok(result.importWarnings?.some((warning) => warning.includes("civilians")));
  validateMission(JSON.parse(JSON.stringify(result)));
  const remaining = remainingMissionPreview(source);
  assert.deepEqual(remaining.data.soldiers, []);
  assert.deepEqual(remaining.data.beam_mes, []);
  assert.deepEqual(remaining.data.civilians, source.data.civilians);
  assert.equal((source.data.soldiers as unknown[]).length, 3);
});

test("invalid rows are reported without discarding other mission characters", () => {
  const result = importMission(
    {
      name: "Partial",
      map: "Derby",
      data: {
        soldiers: [
          soldier,
          { ...soldier, obstacle_index: 999 },
          { ...soldier, profile_number: 99 },
        ],
        beam_mes: [beam, { ...beam, direction: 16 }],
      },
    },
    level,
    config,
    parseMissionCharacterCatalog(config),
  );
  assert.equal(result.soldiers.length, 1);
  assert.equal(result.spawnPoints.length, 1);
  assert.equal(result.importWarnings?.filter((warning) => warning.includes("omitted:")).length, 3);
});

test("campaign spawns validate without a profile but reject invalid supplied profiles", () => {
  const mission = {
    version: 1,
    spawnPoints: [{ id: "slot", name: "Campaign spawn", position: [0, 0, 0], direction: 0 }],
    soldiers: [],
  };
  assert.doesNotThrow(() => validateMission(mission));
  assert.throws(() =>
    validateMission({ ...mission, spawnPoints: [{ ...mission.spawnPoints[0], profile: -1 }] }),
  );
});
