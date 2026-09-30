import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { IDENTITY_TRANSFORM } from "@rle/shared";
import { joinedNavigationCompilerFixture } from "../../shared/test-fixtures/asset-gameplay.ts";
import { compileMap } from "./map-compile.ts";

test("independently placed walkway copies match the native pathfinding fixture", async () => {
  const { document, assets } = joinedNavigationCompilerFixture();
  const groups = [...document.groups];
  for (const group of groups)
    document.groups.push({
      id: `${group.id}-copy`,
      transform: { ...IDENTITY_TRANSFORM, dx: 1000, dy: 100, rot_deg: 90 },
    });
  for (const part of [...document.objects].filter((part) => part.group))
    document.objects.push({
      ...structuredClone(part),
      id: `${part.id}-copy`,
      group: `${part.group}-copy`,
    });
  const descriptor = compileMap(document, [0, 0, 2000, 2000], assets).descriptor;
  const expected = JSON.parse(
    await readFile(
      new URL(
        "../../../crates/robin_engine/tests/fixtures/asset-navigation-copies.level.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  assert.deepEqual(descriptor, expected);
});
