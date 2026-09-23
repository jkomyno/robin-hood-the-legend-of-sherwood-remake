import crypto from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { isIdentity, type Level3D } from "@rle/shared";

type Node = { name?: string; children?: number[]; extras?: Record<string, any>;
  translation?: number[]; rotation?: number[]; scale?: number[]; matrix?: number[] };
const digest = (bytes: Uint8Array) => crypto.createHash("sha256").update(bytes).digest("hex");
const identityNode = (node: Node) =>
  (!node.translation || isDeepStrictEqual(node.translation, [0, 0, 0])) &&
  (!node.rotation || isDeepStrictEqual(node.rotation, [0, 0, 0, 1])) &&
  (!node.scale || isDeepStrictEqual(node.scale, [1, 1, 1])) &&
  (!node.matrix || isDeepStrictEqual(node.matrix, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]));

/** Native patches remain in the datadir. Only their unchanged initial editor
 * previews can be omitted from the old static-volume bake. Changed previews
 * need mission export support; this is not a refined-GLB renderer.
 */
export async function preserveNativePatchPreviews(document: Level3D, glb: Buffer,
  readMission: (mission: string) => Promise<Buffer>): Promise<Level3D> {
  if (glb.length < 20 || glb.toString("ascii", 0, 4) !== "glTF" || glb.readUInt32LE(4) !== 2 ||
      glb.readUInt32LE(8) !== glb.length || glb.readUInt32LE(16) !== 0x4e4f534a || 20 + glb.readUInt32LE(12) > glb.length)
    throw new Error("Invalid source GLB for native patch verification");
  const scene = JSON.parse(glb.toString("utf8", 20, 20 + glb.readUInt32LE(12))) as { nodes?: Node[] };
  const nodes = scene.nodes ?? [];
  const previews = nodes.filter(node => node.name?.startsWith("mission-"));
  const missionObjects = document.objects.filter(part => part.kind === "mission");
  if (!previews.length && !missionObjects.length) return document;
  if (document.assetSources?.length) throw new Error("Native patch preservation does not support imported standalone assets");
  if (!document.provenance?.glb_sha256 || document.provenance.glb_sha256 !== digest(glb))
    throw new Error("Native patch previews require the pinned, unchanged source GLB");
  if (previews.length !== missionObjects.length || new Set(previews.map(node => node.name)).size !== previews.length)
    throw new Error("Native patch preview membership changed (deleted, duplicated, or added)");
  for (const node of previews) {
    const binding = node.extras?.native_patch_preview;
    if (!binding || binding.state !== "initial" || typeof binding.mission !== "string" ||
        !/^[a-zA-Z0-9_-]+$/.test(binding.mission) || !/^[a-f0-9]{64}$/.test(binding.mission_sha256 ?? "") ||
        !Number.isInteger(binding.patch_index) || binding.patch_index < 0 || typeof binding.profile !== "string" ||
        binding.profile !== node.extras?.mission_patch_profile || node.extras?.source_obstacle !== undefined)
      throw new Error(`Missing verified native initial-patch binding: ${node.name}`);
    const part = missionObjects.find(part => part.node === node.name);
    const parents = nodes.filter(parent => parent.children?.includes(nodes.indexOf(node)));
    const parent = parents[0];
    const group = document.groups.find(group => group.id === part?.group);
    if (!part || part.id !== node.name || part.source.mission_profile !== binding.profile || part.source.map !== document.map ||
        part.source.obstacle !== undefined || part.hidden || !isIdentity(part.transform) ||
        !group || group.hidden || group.states || !isIdentity(group.transform) ||
        parents.length !== 1 || parent?.extras?.asset_group !== group.id || parent.children?.length !== 1 ||
        document.objects.filter(object => object.group === group.id).length !== 1 ||
        !identityNode(node) || !identityNode(parent) ||
        !isDeepStrictEqual(part.obstacle, node.extras?.obstacle_local_game))
      throw new Error(`Native patch preview edited or moved: ${node.name}`);
    const bytes = await readMission(binding.mission);
    if (digest(bytes) !== binding.mission_sha256) throw new Error(`Native mission source changed: ${binding.mission}`);
    const mission = JSON.parse(bytes.toString("utf8"));
    const patch = mission.mission_patches?.[binding.patch_index];
    if (mission.header?.map_filename?.toLowerCase() !== document.map.toLowerCase() ||
        patch?.element_fx?.sprite?.profile_name !== binding.profile || !patch.start_animation_valid ||
        !patch.element_fx.active)
      throw new Error(`Native patch profile/map/initial state mismatch: ${binding.mission}`);
  }
  const excluded = new Set(missionObjects.map(part => part.id));
  return { ...document, objects: document.objects.filter(part => !excluded.has(part.id)) };
}
