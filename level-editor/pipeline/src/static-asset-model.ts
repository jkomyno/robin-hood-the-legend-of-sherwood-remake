import { Document, type Node, type NodeIO } from "@gltf-transform/core";
import { mat4 } from "gl-matrix";
import { canonical, modelContentSignatures } from "./bundle-asset-states.ts";

/** Preserve near-identity TRS values that the generic writer otherwise omits by tolerance. */
export async function writeStaticAssetModel(io: NodeIO, model: Document) {
  const original = Buffer.from(await io.writeBinary(model));
  const jsonLength = original.readUInt32LE(12);
  const json = JSON.parse(original.toString("utf8", 20, 20 + jsonLength)) as {
    nodes?: {
      name?: string;
      matrix?: number[];
      translation?: number[];
      rotation?: number[];
      scale?: number[];
    }[];
  };
  const nodes = model.getRoot().listNodes();
  if (!Array.isArray(json.nodes) || json.nodes.length !== nodes.length)
    throw new Error("Static model writer changed node allocation");
  for (const [i, node] of nodes.entries()) {
    const target = json.nodes[i];
    if (!target || (target.name ?? "") !== node.getName())
      throw new Error("Static model writer reordered nodes");
    delete target.matrix;
    target.translation = node.getTranslation();
    target.rotation = node.getRotation();
    target.scale = node.getScale();
  }
  const encoded = Buffer.from(JSON.stringify(json));
  const paddedLength = Math.ceil(encoded.length / 4) * 4;
  const tail = original.subarray(20 + jsonLength);
  const bytes = Buffer.alloc(20 + paddedLength + tail.length);
  original.copy(bytes, 0, 0, 20);
  bytes.writeUInt32LE(bytes.length, 8);
  bytes.writeUInt32LE(paddedLength, 12);
  bytes.fill(0x20, 20, 20 + paddedLength);
  encoded.copy(bytes, 20);
  tail.copy(bytes, 20 + paddedLength);
  return bytes;
}

/** Reparent owned subtrees into the editor's Z-up asset frame without changing their content. */
export async function normalizeStaticAssetModel(model: Document, id: string, names: string[]) {
  const root = model.getRoot();
  const scene = root.listScenes()[0];
  if (
    !scene ||
    root.listScenes().length !== 1 ||
    root.listAnimations().length ||
    root.listSkins().length
  )
    throw new Error("Static model normalization requires one scene without animation or skins");
  const reachable: Node[] = [];
  scene.traverse((node) => reachable.push(node));
  const parts = names.map((name) => {
    const matches = reachable.filter((node) => node.getName() === name);
    if (matches.length !== 1) throw new Error(`Missing or ambiguous model part: ${name}`);
    return matches[0]!;
  });
  const owned = new Set<Node>();
  for (const part of parts) part.traverse((node) => owned.add(node));
  for (const part of parts)
    if (part.getParentNode() && owned.has(part.getParentNode()!))
      throw new Error(`Nested owned part: ${part.getName()}`);
  const wrappers = reachable.filter((node) => !owned.has(node));
  const emptyHiddenList = (value: unknown) => Array.isArray(value) && value.length === 0;
  for (const node of wrappers)
    if (
      node.getMesh() ||
      node.getCamera() ||
      node.listExtensions().length ||
      Object.entries(node.getExtras()).some(
        ([key, value]) =>
          key !== "asset_group" &&
          !(key === "default_hidden_source_nodes" && emptyHiddenList(value)),
      )
    )
      throw new Error(`Unowned model content requires explicit migration: ${node.getName()}`);
  const proof = await modelContentSignatures(model);
  const expected = parts.map((part) => proof.nodeData(part));
  const worlds = parts.map((part) => part.getWorldMatrix());
  const map = model.createNode("map").setRotation([-Math.SQRT1_2, 0, 0, Math.SQRT1_2]);
  if (wrappers.some((node) => emptyHiddenList(node.getExtras().default_hidden_source_nodes)))
    map.setExtras({ default_hidden_source_nodes: [] });
  const group = model.createNode(id).setExtras({ asset_group: id });
  map.addChild(group);
  scene.addChild(map);
  // Use double precision for reparenting; the model's vertex buffers remain untouched.
  const inverse = mat4.invert(new Float64Array(16), map.getWorldMatrix());
  if (!inverse) throw new Error("Invalid map frame");
  for (const [index, part] of parts.entries()) {
    const local = mat4.multiply(new Float64Array(16), inverse, worlds[index]!);
    group.addChild(part);
    part.setMatrix(Array.from(local) as ReturnType<Node["getMatrix"]>);
  }
  for (const wrapper of wrappers) wrapper.dispose();
  for (const child of scene.listChildren()) if (child !== map) scene.removeChild(child);
  await verifyStaticParts(model, names, expected);
  return expected;
}

/** Raw geometry, materials and metadata must match exactly; matrices allow roundoff only. */
export async function verifyStaticParts(model: Document, names: string[], expected: unknown[]) {
  if (names.length !== expected.length) throw new Error("Static model proof has missing parts");
  const proof = await modelContentSignatures(model);
  interface Signature {
    world: number[];
    children: Signature[];
    [key: string]: unknown;
  }
  function comparable(value: Signature): unknown {
    const { world: _world, children, ...rest } = value;
    return { ...rest, children: children.map(comparable) };
  }
  function matrices(value: Signature): number[][] {
    return [value.world, ...value.children.flatMap(matrices)];
  }
  for (const [index, name] of names.entries()) {
    const nodes = model
      .getRoot()
      .listNodes()
      .filter((node) => node.getName() === name);
    if (nodes.length !== 1) throw new Error(`Missing or ambiguous normalized part: ${name}`);
    const actual = proof.nodeData(nodes[0]!);
    const before = expected[index] as Signature;
    const a = matrices(before),
      b = matrices(actual);
    if (
      canonical(comparable(before)) !== canonical(comparable(actual)) ||
      a.length !== b.length ||
      a.some(
        (matrix, i) =>
          matrix.length !== 16 ||
          b[i]!.length !== 16 ||
          matrix.some(
            (v, j) =>
              !Number.isFinite(v) || !Number.isFinite(b[i]![j]) || Math.abs(v - b[i]![j]!) > 1e-9,
          ),
      )
    )
      throw new Error(
        `Static model changed geometry or appearance: ${name}; content matches=${
          canonical(comparable(before)) === canonical(comparable(actual))
        }; maximum matrix delta=${Math.max(
          ...a.flatMap((matrix, i) =>
            matrix.map((value, j) => Math.abs(value - (b[i]?.[j] ?? Infinity))),
          ),
        )}`,
      );
  }
}
