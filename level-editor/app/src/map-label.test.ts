import test from "node:test";
import assert from "node:assert/strict";
import { publishedMapLabel } from "./map-label.ts";

test("built-in maps use capitalized English names and distinguish saved copies", () => {
  const names = {
    croisement01: "Crossroads 1 (WIP)",
    croisement02: "Crossroads 2 (WIP)",
    croisement03: "Crossroads 3 (WIP)",
    derby: "Derby (Refined)",
    leicester: "Leicester (Refined)",
    lincoln: "Lincoln (Refined)",
    nottingham: "Nottingham (Refined)",
    sherwood: "Sherwood (Refined)",
    Wychford: "Wychford (Example)",
    york: "York (WIP)",
  };
  for (const [id, label] of Object.entries(names)) {
    assert.equal(publishedMapLabel(id, false), label);
    assert.equal(publishedMapLabel(id, true), label + " (Modified)");
  }
  assert.equal(publishedMapLabel("My custom map", false), "My custom map");
});
