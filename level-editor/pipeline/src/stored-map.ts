import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import {
  descriptorForSource,
  expandStoredMap,
  parseStoredMap,
  parseExternalAssetSources,
  parseProjectionAssetDescriptor,
  parseLevel3D,
  serializeStoredMap,
  type ExternalAssetSource,
  type Level3D,
  type SceneAssetSource,
  type ProjectionAssetDescriptor,
} from "@rle/shared";

export async function pinnedDescriptors(
  library: string,
  references: ExternalAssetSource[],
  sceneAssets: SceneAssetSource[] = [],
): Promise<Map<string, ProjectionAssetDescriptor>> {
  parseExternalAssetSources(references);
  return new Map(
    await Promise.all(
      [...references, ...sceneAssets.filter((source) => source.descriptor)].map(
        async (reference) => {
          const bytes = await fs.readFile(path.join(library, reference.descriptor!));
          if (createHash("sha256").update(bytes).digest("hex") !== reference.descriptor_sha256)
            throw new Error(`Asset descriptor changed: ${reference.id}`);
          return [
            reference.id,
            "role" in reference
              ? parseProjectionAssetDescriptor(JSON.parse(bytes.toString()))
              : descriptorForSource(reference, JSON.parse(bytes.toString())),
          ] as const;
        },
      ),
    ),
  );
}

export async function readStoredMap(file: string, library: string): Promise<Level3D> {
  const raw = JSON.parse(await fs.readFile(file, "utf8"));
  const expanded = expandStoredMap(raw);
  const descriptors = await pinnedDescriptors(
    library,
    (expanded.assetSources as ExternalAssetSource[] | undefined) ?? [],
    (expanded.sceneAssets as SceneAssetSource[] | undefined) ?? [],
  );
  return parseStoredMap(raw, descriptors);
}

export async function compactStoredMap(document: Level3D, library: string): Promise<unknown> {
  parseLevel3D(document);
  return serializeStoredMap(
    document,
    await pinnedDescriptors(library, document.assetSources ?? [], document.sceneAssets),
  );
}
