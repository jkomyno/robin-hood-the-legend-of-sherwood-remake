import { MissionEntities } from "../src/mission";
import type { ProtoLevel } from "@rle/shared";
import * as THREE from "three";

/** Real lossless WebP decoding and canvas cropping, including directional frame textures. */
export async function checkSpriteAtlas() {
  // Pillow lossless WebP: 8×4 transparent image with red/green 2×2 frames at (1,1)/(5,1).
  const webp = new Blob(
    [
      Uint8Array.from(
        atob("UklGRioAAABXRUJQVlA4TB0AAAAvB8AAEBcgEEjaH3qN+Y/5D2xBIJDiIIY4ov/BHQA="),
        (c) => c.charCodeAt(0),
      ),
    ],
    { type: "image/webp" },
  );
  let atlasReads = 0;
  const files = new Map<string, Blob>([
    [
      "Data/Configuration/profile.cpf.json",
      new Blob([
        JSON.stringify({
          soldier_order: ["guard"],
          soldiers: { guard: { filename: "Guard", profile_name: "Guard" } },
        }),
      ]),
    ],
    ["Data/Characters/Guard.rhs.d/atlas.webp", webp],
    [
      "Data/Characters/Guard.rhs.d/manifest.json",
      new Blob([
        JSON.stringify({
          pixel_format: "rgba",
          atlas: "atlas.webp",
          profiles: [
            {
              name: "Guard",
              center_x: 0,
              center_y: 0,
              rows: [0, 3].flatMap((action) =>
                Array.from({ length: 16 }, (_, direction) => ({
                  action_id: action,
                  direction,
                  path: ".",
                  frames: [
                    {
                      file: "atlas.webp",
                      rect: [direction % 2 ? 5 : 1, 1, 2, 2],
                      offset_x: 0,
                      offset_y: 0,
                    },
                  ],
                })),
              ),
            },
          ],
        }),
      ]),
    ],
  ]);
  function directory(prefix = ""): FileSystemDirectoryHandle {
    return {
      async getDirectoryHandle(name: string) {
        const next = prefix + name + "/";
        if (![...files.keys()].some((key) => key.startsWith(next)))
          throw new DOMException(next, "NotFoundError");
        return directory(next);
      },
      async getFileHandle(name: string) {
        const blob = files.get(prefix + name);
        if (!blob) throw new DOMException(name, "NotFoundError");
        return {
          async getFile() {
            if (name === "atlas.webp") atlasReads++;
            return new File([blob], name, { type: blob.type });
          },
        };
      },
    } as unknown as FileSystemDirectoryHandle;
  }
  const root = directory();
  const preview = await MissionEntities.load(
    { root, levelsDir: root, maps: new Set() },
    {
      name: "Atlas",
      map: "Fixture",
      data: {
        header: { ambiance: 1 },
        soldiers: [0, 3].map((action, direction) => ({
          profile_number: 0,
          action,
          direction,
          position_x: 0,
          position_y: 0,
        })),
      },
    },
    { sight_obstacles: [] } as unknown as ProtoLevel,
    { kind: "oblique-orthographic", elevation_deg: 35 },
  );
  try {
    if (atlasReads !== 1) throw new Error(`Atlas fetched ${atlasReads} times across two poses`);
    for (const [i, actor] of preview.root.children.entries()) {
      const texture = (actor as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>).material
        .map!;
      const image = texture.image as OffscreenCanvas;
      if (image.width !== 2 || image.height !== 2)
        throw new Error("Atlas frame dimensions changed");
      const pixels = image.getContext("2d")!.getImageData(0, 0, 2, 2).data;
      const expected = i === 0 ? [255, 0, 0, 255] : [0, 255, 0, 255];
      if ([...pixels].some((value, channel) => value !== expected[channel % 4]))
        throw new Error("Atlas frame sampled neighboring pixels");
    }
  } finally {
    preview.dispose();
  }
}
