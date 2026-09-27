// Export mission-owned state graphics independently of building reveal patches.
import fs from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import type { Patch } from "@rle/shared";
import { levelsDirPath } from "./asset-writer.ts";
import { datadirPath } from "./env.ts";
import { loadKeyedFxPng, type RhsProfile } from "./fx.ts";

export async function exportMissionPatchLayers(
  map: string,
  output: string,
  basePatchCount: number,
) {
  const records = [];
  const levels = levelsDirPath();
  for (const file of (await fs.readdir(levels)).filter((f) => /\.rhm\.json$/i.test(f)).sort()) {
    const mission = JSON.parse(await fs.readFile(path.join(levels, file), "utf8")) as {
      header: { map_filename: string; ambiance: number };
      mission_patches: Patch[];
    };
    if (mission.header.map_filename.toLowerCase() !== map.toLowerCase()) continue;
    if (mission.mission_patches.length === 0) continue;
    const ambiance =
      mission.header.ambiance === 2 ? "Fog" : mission.header.ambiance === 4 ? "Night" : "Day";
    const animationDirectories = await Promise.all(
      [...new Set([ambiance, "Day"])].map(async (name) => {
        const directory = path.join(datadirPath(), "Data", "Animations", name);
        return { name, directory, banks: await fs.readdir(directory) };
      }),
    );
    const missionId = file.replace(/\.rhm\.json$/i, "");
    for (const [index, patch] of mission.mission_patches.entries()) {
      const sprite = patch.element_fx.sprite;
      const id = `mission-${missionId}-patch-${String(index).padStart(3, "0")}`;
      const states: Record<
        string,
        {
          action_id: number;
          frames: {
            image: string;
            bbox: number[];
            delay: number;
            sound_id: number;
          }[];
        }
      > = {};
      let graphicsAmbiance = ambiance;
      if (sprite.frame_profile_name !== "pixel_vert") {
        const match = animationDirectories.flatMap(({ name, directory, banks }) =>
          banks
            .filter((b) => b.toLowerCase() === `${sprite.frame_profile_name}.rhs.d`.toLowerCase())
            .map((bank) => ({ name, directory: path.join(directory, bank) })),
        )[0];
        if (!match)
          throw new Error(
            `Missing mission patch bank ${sprite.frame_profile_name} (${ambiance}/Day)`,
          );
        const { directory } = match;
        graphicsAmbiance = match.name;
        const manifest = JSON.parse(
          await fs.readFile(path.join(directory, "manifest.json"), "utf8"),
        ) as { profiles: RhsProfile[] };
        const profile = manifest.profiles.find((p) => p.name === sprite.profile_name);
        if (!profile) throw new Error(`Missing mission patch profile ${sprite.profile_name}`);
        for (const [name, action, valid] of [
          ["initial", 148, patch.start_animation_valid],
          ["transition", 149, patch.transition_animation_valid],
          ["final", 150, patch.end_animation_valid],
        ] as const) {
          if (!valid) continue;
          const row = profile.rows.find((r) => r.action_id === action);
          if (!row?.frames.length)
            throw new Error(`Missing ${name} animation for ${sprite.profile_name}`);
          const frames = [];
          for (const [number, frame] of row.frames.entries()) {
            let source = path.join(directory, profile.name, row.path, frame.file);
            try {
              await fs.access(source);
            } catch (error) {
              if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
              source = path.join(directory, row.path, frame.file);
            }
            const image = `mission-patches/${id}/${name}-${String(number).padStart(3, "0")}.png`;
            await fs.mkdir(path.dirname(path.join(output, image)), { recursive: true });
            const png = await loadKeyedFxPng(source);
            await fs.writeFile(path.join(output, image), png);
            const info = await sharp(png).metadata();
            frames.push({
              image,
              bbox: [
                sprite.position_x + frame.offset_x,
                sprite.position_y + frame.offset_y,
                info.width,
                info.height,
              ],
              delay: frame.delay,
              sound_id: frame.sound_id,
            });
          }
          states[name] = { action_id: action, frames };
        }
      }
      const applied = patch.integrate_in_background
        ? states.transition?.frames.at(-1)
        : states.final?.frames[0];
      records.push({
        id,
        mission: missionId,
        mission_ambiance: mission.header.ambiance,
        graphics_ambiance: graphicsAmbiance,
        mission_patch_index: index,
        runtime_patch_index: basePatchCount + index,
        name: sprite.profile_name,
        state: patch,
        states,
        initial_graphic: states.initial?.frames[0] ?? null,
        applied_graphic: applied ?? null,
        applied_graphic_mode: patch.integrate_in_background
          ? "baked-last-transition-frame"
          : patch.end_animation_valid
            ? "final-animation"
            : "no-active-sprite",
        sight_before: patch.old_sight_obstacles.map(
          (n) => `building-${String(n).padStart(3, "0")}`,
        ),
        sight_after: patch.new_sight_obstacles.map((n) => `building-${String(n).padStart(3, "0")}`),
      });
    }
  }
  const projectionSources = new Map<string, { initial: string; applied: string }>();
  for (const mission of new Set(records.map((record) => record.mission))) {
    const sources = {
      initial: `mission-patches/${mission}-initial.png`,
      applied: `mission-patches/${mission}-applied.png`,
    };
    for (const state of ["initial", "applied"] as const) {
      const overlays = records
        .filter((record) => record.mission === mission)
        .flatMap((record) => {
          const graphic = state === "initial" ? record.initial_graphic : record.applied_graphic;
          return graphic
            ? [
                {
                  input: path.join(output, graphic.image),
                  left: graphic.bbox[0]!,
                  top: graphic.bbox[1]!,
                },
              ]
            : [];
        });
      await sharp(path.join(output, "covered.png"))
        .composite(overlays)
        .png()
        .toFile(path.join(output, sources[state]));
    }
    projectionSources.set(mission, sources);
  }
  return records.map((record) => ({
    ...record,
    projection_sources: projectionSources.get(record.mission)!,
  }));
}
