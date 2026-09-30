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

test("soldier labels use English while preserving sprite and export identities", () => {
  const names = [
    ["Hallebardier Bleu", "Blue Halberdier"],
    ["Epee Jaune", "Yellow Swordsman"],
    ["Archer Rouge", "Red Archer"],
    ["Officier Special Orange", "Orange Special Officer"],
    ["Chevalier Noir", "Black Knight"],
    ["Lancier Vert Mechant", "Green Spearman (Hostile)"],
    ["Arbaletrier Vert", "Green Crossbowman"],
    ["Cavalier Jaune", "Yellow Cavalryman"],
    ["Mmen Arc", "Merry Man (Bow)"],
    ["Mmen Baton", "Merry Man (Staff)"],
    ["Ne pas utiliser4", "Unused 4"],
    ["Sheriff of Nottingham", "Sheriff of Nottingham"],
    ["Custom Guard", "Custom Guard"],
  ];
  const catalog = parseMissionCharacterCatalog({
    characters: {},
    character_order: [],
    soldiers: Object.fromEntries(
      names.map(([name], i) => [
        String(i),
        {
          filename: `Guard${i}`,
          profile_name: "Garde A",
          display_name: name,
        },
      ]),
    ),
    soldier_order: names.map((_, i) => String(i)),
  });
  assert.deepEqual(
    catalog.map((entry) => entry.name),
    names.map(([, english]) => english),
  );
  catalog.forEach((entry, i) => {
    assert.equal(entry.profile, `guard${i}`);
    assert.equal(entry.filename, `Guard${i}`);
    assert.equal(entry.profileName, "Garde A");
  });
});
