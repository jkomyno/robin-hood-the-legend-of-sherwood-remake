/** Lossless scene bundling. Texture encoding and decoded accessor values are never changed. */
import { createHash } from 'node:crypto';
import { Document, NodeIO, PropertyType, type Scene, Root } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, mergeDocuments, unpartition } from '@gltf-transform/functions';

export const BUNDLE_VERSION = 1;
export const sha256 = (value: Uint8Array | string): string => createHash('sha256').update(value).digest('hex');
export const canonical = (value: unknown): string => JSON.stringify(sort(value));
function sort(value: any): any {
  if (Array.isArray(value)) return value.map(sort);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, sort(v)]));
  return value;
}
const io = (): NodeIO => new NodeIO().registerExtensions(ALL_EXTENSIONS);
async function readSupported(bytes: Uint8Array): Promise<Document> {
  const jsonDoc = await io().binaryToJSON(bytes);
  const known = new Set(ALL_EXTENSIONS.map(e => e.EXTENSION_NAME));
  for (const name of jsonDoc.json.extensionsUsed ?? []) if (!known.has(name)) throw new Error(`Unsupported extension: ${name}`);
  return io().readJSON(jsonDoc);
}
export interface StateInput { scene: string; bytes: Uint8Array; sourceScene?: string; }
export interface BundleResult {
  bytes: Uint8Array;
  scenes: Array<{ name: string; signature: string }>;
  before: Record<string, number>;
  after: Record<string, number>;
}

/** Resource signatures ignore arbitrary resource names, never metadata or texture bytes. */
async function signatures(doc: Document) {
  const { json } = await io().writeJSON(doc);
  const root = doc.getRoot();
  if (root.listScenes().some(s => s.listExtensions().length)) throw new Error('Scene extensions require explicit signature support.');
  if (root.listSkins().length || root.listAnimations().length) throw new Error('State bundling does not yet support skeletal or timeline animation.');
  const images = root.listTextures().map(t => ({ mime: t.getMimeType(), bytes: sha256(t.getImage()!), extras: t.getExtras() }));
  const accessors = root.listAccessors().map(a => ({ type: a.getType(), componentType: a.getComponentType(), normalized: a.getNormalized(), extras: a.getExtras(), bytes: sha256(new Uint8Array(a.getArray()!.buffer, a.getArray()!.byteOffset, a.getArray()!.byteLength)) }));
  const stripName = (v: any): any => { const { name, ...rest } = v; return rest; };
  const textures = (json.textures ?? []).map(t => ({ ...stripName(t), source: images[t.source!], sampler: t.sampler == null ? null : json.samplers![t.sampler] }));
  function textureRefs(v: any, key = ''): any {
    if (key === 'extras' || !v || typeof v !== 'object') return v;
    if (Array.isArray(v)) return v.map(x => textureRefs(x, key));
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, k === 'index' && /texture$/i.test(key) ? textures[x as number] : textureRefs(x, k)]));
  }
  const materials = (json.materials ?? []).map(m => textureRefs(stripName(m)));
  const accessorSignature = (a: any) => a ? accessors[root.listAccessors().indexOf(a)] : null;
  const meshes = (json.meshes ?? []).map((m, mi) => ({ ...stripName(m), primitives: m.primitives.map((p, pi) => { const primitive = root.listMeshes()[mi]!.listPrimitives()[pi]!; return ({ ...p,
    attributes: Object.fromEntries(Object.entries(p.attributes).map(([k, i]) => [k, accessorSignature(primitive.getAttribute(k))])),
    indices: accessorSignature(primitive.getIndices()), material: p.material == null ? null : materials[p.material],
    targets: p.targets?.map((t, ti) => Object.fromEntries(Object.entries(t).map(([k]) => [k, accessorSignature(primitive.listTargets()[ti]!.getAttribute(k))]))),
  }); }) }));
  const nodeList = root.listNodes();
  function node(n: typeof nodeList[number]): any {
    const j = json.nodes![nodeList.indexOf(n)]!;
    const { children, mesh, camera, matrix, translation, rotation, scale, name, ...rest } = j;
    return { ...rest, world: n.getWorldMatrix(), mesh: mesh == null ? null : meshes[mesh], camera: camera == null ? null : json.cameras![camera], children: n.listChildren().map(node) };
  }
  return { resources: { images, accessors, materials, meshes }, sceneData: (s: Scene) => ({ extras: s.getExtras(), nodes: s.listChildren().map(node) }), scene: (s: Scene) => sha256(canonical({ extras: s.getExtras(), nodes: s.listChildren().map(node) })) };
}
function counts(d: Document): Record<string, number> {
  const r = d.getRoot();
  return { scenes: r.listScenes().length, meshes: r.listMeshes().length, materials: r.listMaterials().length, textures: r.listTextures().length, accessors: r.listAccessors().length };
}
export async function bundleStates(inputs: StateInput[], defaultScene: string): Promise<BundleResult> {
  if (!inputs.length || new Set(inputs.map(i => i.scene)).size !== inputs.length) throw new Error('At least one uniquely named scene is required.');
  const target = new Document();
  const expected: Array<{ name: string; signature: string }> = [];
  for (const input of inputs) {
    const source = await readSupported(input.bytes);
    const candidates = input.sourceScene ? source.getRoot().listScenes().filter(s => s.getName() === input.sourceScene) : [source.getRoot().getDefaultScene() ?? source.getRoot().listScenes()[0]];
    const selected = candidates[0];
    if (!selected || candidates.length !== 1) throw new Error(`Missing source scene for ${input.scene}`);
    expected.push({ name: input.scene, signature: (await signatures(source)).scene(selected) });
    // A state source may already contain other scenes. Retain only the selected scene.
    for (const scene of source.getRoot().listScenes()) if (scene !== selected) scene.dispose();
    const reachable = new Set<ReturnType<Document['createNode']>>();
    selected.traverse(node => reachable.add(node));
    for (const node of source.getRoot().listNodes()) if (!reachable.has(node)) node.dispose();
    const map = mergeDocuments(target, source);
    (map.get(selected) as Scene).setName(input.scene);
  }
  const before = counts(target);
  await target.transform(dedup({ propertyTypes: [PropertyType.ACCESSOR, PropertyType.TEXTURE, PropertyType.MATERIAL, PropertyType.MESH] }), unpartition());
  // The library transform separates attribute/index use categories. Collapse remaining
  // byte-identical accessors too, including imported resources without live primitives.
  const accessorProof = (await signatures(target)).resources.accessors;
  const seenAccessors = new Map<string, ReturnType<Document['createAccessor']>>();
  target.getRoot().listAccessors().forEach((a, i) => {
    if (a.listExtensions().length) throw new Error('Accessor extensions require explicit signature support.');
    const key = sha256(canonical(accessorProof[i]));
    const previous = seenAccessors.get(key);
    if (!previous) seenAccessors.set(key, a);
    else { for (const parent of a.listParents()) if (!(parent instanceof Root)) parent.swap(a, previous); a.dispose(); }
  });
  await target.transform(dedup({ propertyTypes: [PropertyType.MESH] }));
  const selectedDefault = target.getRoot().listScenes().find(s => s.getName() === defaultScene);
  if (!selectedDefault) throw new Error(`Missing default scene ${defaultScene}`);
  target.getRoot().setDefaultScene(selectedDefault);
  const bytes = await io().writeBinary(target);
  const roundtrip = await readSupported(bytes);
  const proof = await signatures(roundtrip);
  for (const { name, signature } of expected) {
    const scene = roundtrip.getRoot().listScenes().find(s => s.getName() === name);
    if (!scene || proof.scene(scene) !== signature) throw new Error(`Lossless state verification failed: ${name}`);
  }
  for (const [kind, values] of Object.entries(proof.resources)) {
    const hashes = values.map(v => sha256(canonical(v)));
    if (new Set(hashes).size !== hashes.length) throw new Error(`Duplicate ${kind} remain after bundling`);
  }
  return { bytes, scenes: expected, before, after: counts(roundtrip) };
}

export async function verifyBundledScene(bundle: Uint8Array, sceneName: string, reference: Uint8Array, referenceScene?: string) {
  const bundled = await readSupported(bundle);
  const original = await readSupported(reference);
  const selected = bundled.getRoot().listScenes().filter(s => s.getName() === sceneName);
  const source = referenceScene ? original.getRoot().listScenes().filter(s => s.getName() === referenceScene) : [original.getRoot().getDefaultScene() ?? original.getRoot().listScenes()[0]];
  if (selected.length !== 1 || source.length !== 1 || !source[0]) throw new Error('Missing or ambiguous selected scene.');
  const expected = (await signatures(original)).scene(source[0]);
  if ((await signatures(bundled)).scene(selected[0]!) !== expected) throw new Error(`Lossless state verification failed: ${sceneName}`);
  return { semantic_sha256: expected, scene: sceneName, reference_sha256: sha256(reference), bundle_sha256: sha256(bundle) };
}
