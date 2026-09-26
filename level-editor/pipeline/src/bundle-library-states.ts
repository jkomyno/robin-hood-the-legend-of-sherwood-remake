/** Stage verified shared-resource GLBs. Live library promotion is a separate transaction. */
import { readFile, writeFile, mkdir, readdir, stat } from 'node:fs/promises';
import { resolve, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { bundleStates, verifyBundledScene, BUNDLE_VERSION, canonical, sha256, type StateInput } from './bundle-asset-states.ts';

export async function stageAsset(assetDir: string, outputDir: string) {
  if (resolve(assetDir) === resolve(outputDir)) throw new Error('Staging must not overwrite the live asset directory.');
  const descriptorBytes = await readFile(join(assetDir, 'asset.json'));
  const descriptor = JSON.parse(descriptorBytes.toString());
  const states: Array<StateInput & { source_file: string; source_sha256: string }> = [];
  const files = new Map<string, Buffer>();
  const add = async (scene: string, model: string, sourceScene?: string) => {
    if (basename(model) !== model || !model.endsWith('.glb')) throw new Error(`Only local GLB files are supported: ${model}`);
    let bytes = files.get(model);
    if (!bytes) { bytes = await readFile(join(assetDir, model)); files.set(model, bytes); }
    states.push({ scene, sourceScene, bytes, source_file: model, source_sha256: sha256(bytes) });
  };
  const variantsKey = descriptor.standalone_variants ? 'standalone_variants' : descriptor.state_variants ? 'state_variants' : null;
  const defaultScene = variantsKey === 'state_variants' ? 'initial' : 'default';
  await add(defaultScene, descriptor.model, descriptor.model_scene);
  if (variantsKey) {
    for (const [key, variant] of Object.entries(descriptor[variantsKey]) as Array<[string, any]>) {
      if (key === defaultScene && variant.model === descriptor.model && variant.model_scene === descriptor.model_scene) continue;
      if (key === defaultScene) throw new Error('The initial state must match the base model.');
      await add(key, variant.model, variant.model_scene);
    }
  }
  const sourceFiles = [...files].map(([path, bytes]) => ({ path, sha256: sha256(bytes), bytes: bytes.byteLength }));
  const code = await Promise.all(['bundle-library-states.ts', 'bundle-asset-states.ts'].map(p => readFile(join(fileURLToPath(new URL('.', import.meta.url)), p))));
  const sourceSignature = sha256(canonical({ version: BUNDLE_VERSION, code: code.map(sha256), descriptor: sha256(descriptorBytes), files: sourceFiles, scenes: states.map(s => [s.scene, s.source_file, s.sourceScene]) }));
  try {
    const receipt = JSON.parse(await readFile(join(outputDir, 'bundle.receipt.json'), 'utf8'));
    if (receipt.source_signature === sourceSignature && sha256(await readFile(join(outputDir, 'model.glb'))) === receipt.output.sha256 && sha256(await readFile(join(outputDir, 'asset.json'))) === receipt.output_descriptor_sha256) return { ...receipt, skipped: true };
  } catch { /* Missing or corrupt staging products are regenerated. */ }
  const packed = await bundleStates(states, defaultScene);
  descriptor.model = 'model.glb'; descriptor.model_scene = defaultScene;
  if (variantsKey) for (const [key, variant] of Object.entries(descriptor[variantsKey]) as Array<[string, any]>) { variant.model = 'model.glb'; variant.model_scene = key; }
  // Previews are derived from the source bytes. Rebuilding updates their incremental receipt.
  const outputDescriptor = JSON.stringify(descriptor, null, 2) + '\n';
  const receipt = {
    version: BUNDLE_VERSION, kind: 'lossless-state-bundle', asset_id: descriptor.id,
    source_signature: sourceSignature, source_descriptor_sha256: sha256(descriptorBytes), source_files: sourceFiles,
    output: { path: 'model.glb', sha256: sha256(packed.bytes), bytes: packed.bytes.byteLength },
    output_descriptor_sha256: sha256(outputDescriptor),
    states: states.map(s => ({ scene: s.scene, source_file: s.source_file, source_sha256: s.source_sha256, source_scene: s.sourceScene ?? null, semantic_sha256: packed.scenes.find(p => p.name === s.scene)!.signature })),
    before: packed.before, after: packed.after,
    verification: 'Exact scene structure/world transforms, extras, decoded accessor bytes, material graphs and encoded image bytes match after GLB round trip. No lossy compression.',
  };
  await mkdir(outputDir, { recursive: true });
  await writeFile(join(outputDir, 'model.glb'), packed.bytes);
  await writeFile(join(outputDir, 'asset.json'), outputDescriptor);
  await writeFile(join(outputDir, 'bundle.receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
  return receipt;
}
export function isStateful(d: any): boolean {
  return !!(d.state_variants || d.standalone_variants || d.components?.some((p: any) => p.reveal_patch_ids?.length || p.sight_patch_before_ids?.length || p.sight_patch_after_ids?.length));
}
async function main() {
  const args = process.argv.slice(2);
  const option = (key: string) => { const i = args.indexOf(key); return i < 0 ? undefined : args[i + 1]; };
  if (option('--verify-scene')) {
    if (!option('--scene') || !option('--reference')) throw new Error('--verify-scene requires --scene and --reference');
    console.log(JSON.stringify(await verifyBundledScene(await readFile(option('--verify-scene')!), option('--scene')!, await readFile(option('--reference')!), option('--reference-scene'))));
    return;
  }
  const stage = option('--stage'), asset = option('--asset-dir'), library = option('--library');
  if (!stage || (!asset && !library) || (asset && library)) throw new Error('Usage: bundle-library-states.ts (--asset-dir DIR | --library DIR) --stage DIR');
  if (asset) console.log(JSON.stringify(await stageAsset(resolve(asset), resolve(stage))));
  else {
    const reports = [];
    for (const id of (await readdir(library!)).sort()) {
      const dir = join(library!, id);
      if (!(await stat(dir)).isDirectory()) continue;
      let d: any;
      try { d = JSON.parse(await readFile(join(dir, 'asset.json'), 'utf8')); } catch { continue; }
      if (!isStateful(d)) continue;
      const receipt = await stageAsset(dir, join(stage, id));
      reports.push(receipt); console.log(JSON.stringify({ asset: id, before_bytes: receipt.source_files.reduce((n: number, f: any) => n + f.bytes, 0), after_bytes: receipt.output.bytes, skipped: 'skipped' in receipt }));
    }
    await mkdir(stage, { recursive: true });
    await writeFile(join(stage, 'bundles.json'), JSON.stringify(reports, null, 2) + '\n');
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(e => { console.error(e); process.exitCode = 1; });
