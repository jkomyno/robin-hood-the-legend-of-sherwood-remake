import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import sharp from "sharp";
import { exportMissionPatchLayers } from "./mission-patch-layers.ts";

test("mission patches resolve Fog and Night banks, with Day fallback", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "mission-patch-ambiance-"));
  const previous = process.env.HACKABLE_DATADIR;
  process.env.HACKABLE_DATADIR = root;
  try {
    const levels = path.join(root, "Data", "Levels");
    await fs.mkdir(levels, { recursive: true });
    const png = await sharp({ create: { width: 4, height: 4, channels: 4, background: "#887766" } })
      .png()
      .toBuffer();
    for (const ambiance of ["Day", "Fog", "Night"]) {
      const bank = path.join(root, "Data", "Animations", ambiance, `${ambiance}-door.rhs.d`);
      await fs.mkdir(bank, { recursive: true });
      await fs.writeFile(path.join(bank, "door.png"), png);
      await fs.writeFile(
        path.join(bank, "manifest.json"),
        JSON.stringify({
          profiles: [
            {
              name: "door",
              rows: [
                {
                  action_id: 148,
                  path: ".",
                  frames: [{ file: "door.png", offset_x: 0, offset_y: 0, delay: 1, sound_id: 0 }],
                },
              ],
            },
          ],
        }),
      );
    }
    for (const [name, ambiance, bank, expected] of [
      ["fog", 2, "Fog-door", "Fog"],
      ["night", 4, "Night-door", "Night"],
      ["fallback", 2, "Day-door", "Day"],
    ] as const) {
      await fs.writeFile(
        path.join(levels, `${name}.rhm.json`),
        JSON.stringify({
          header: { map_filename: name, ambiance },
          mission_patches: [
            {
              element_fx: {
                sprite: {
                  frame_profile_name: bank,
                  profile_name: "door",
                  position_x: 0,
                  position_y: 0,
                },
              },
              start_animation_valid: true,
              transition_animation_valid: false,
              end_animation_valid: false,
              integrate_in_background: false,
              old_sight_obstacles: [],
              new_sight_obstacles: [],
            },
          ],
        }),
      );
      const output = path.join(root, name);
      await fs.mkdir(output);
      await fs.writeFile(path.join(output, "covered.png"), png);
      const records = await exportMissionPatchLayers(name, output, 10);
      assert.equal(records.length, 1);
      assert.equal(records[0]!.graphics_ambiance, expected);
      assert.equal(records[0]!.runtime_patch_index, 10);
      assert.deepEqual(
        await fs.readFile(path.join(output, records[0]!.initial_graphic!.image)),
        png,
      );
    }
  } finally {
    if (previous === undefined) delete process.env.HACKABLE_DATADIR;
    else process.env.HACKABLE_DATADIR = previous;
    await fs.rm(root, { recursive: true, force: true });
  }
});
