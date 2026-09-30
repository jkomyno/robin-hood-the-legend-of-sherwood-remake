import test from "node:test";
import assert from "node:assert/strict";
import { parseMissionCharacterCatalog } from "./mission-character-catalog.ts";

test("character identities follow runtime order and duplicate soldier disambiguation", () => {
  const profile = (filename: string) => ({ filename, profile_name: filename, display_name: "" });
  const data = {
    characters: { Z: profile("Zed"), A: profile("Alice") },
    character_order: ["Z", "A"],
    soldiers: { A: profile("Guard A05"), B: profile("Guard A05"), C: profile("Soldier B00") },
    soldier_order: ["C", "B", "A"],
  };
  const profiles = parseMissionCharacterCatalog(data);
  assert.deepEqual(
    profiles.map((profile) => profile.profile),
    [0, 1, "soldier_b00", "guard_a05__1", "guard_a05__2"],
  );
  assert.equal(profiles[0]!.filename, "Zed");
  assert.throws(
    () => parseMissionCharacterCatalog({ ...data, character_order: ["A", "A"] }),
    /character_order/,
  );
});
