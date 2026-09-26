import test from "node:test";
import assert from "node:assert/strict";
import { publishedMapLabel } from "./map-label.ts";

test("built-in maps use capitalized English names and distinguish saved copies", () => {
  const names = { croisement01: "Crossroads 1", croisement02: "Crossroads 2", croisement03: "Crossroads 3",
    derby: "Derby", leicester: "Leicester", lincoln: "Lincoln", nottingham: "Nottingham",
    sherwood: "Sherwood", Wychford: "Wychford", york: "York" };
  for (const [id, label] of Object.entries(names)) {
    assert.equal(publishedMapLabel(id, false), label);
    assert.equal(publishedMapLabel(id, true), label + " (Modified)");
  }
  assert.equal(publishedMapLabel("My custom map", false), "My custom map");
});
