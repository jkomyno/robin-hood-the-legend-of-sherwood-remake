import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { Document, NodeIO } from '@gltf-transform/core';
import { bundleStates, verifyBundledScene } from './bundle-asset-states.ts';
import { stageAsset, isStateful } from './bundle-library-states.ts';
const temporaryDirs: string[] = [];
after(async () => { for (const dir of temporaryDirs) await rm(dir, { recursive: true, force: true }); });
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
async function model(offset = 0, extras = { source: 'same' }) {
  const d = new Document(), b = d.createBuffer();
  const a = d.createAccessor().setBuffer(b).setType('VEC3').setArray(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]));
  const t = d.createTexture().setImage(png).setMimeType('image/png');
  const m = d.createMaterial().setBaseColorTexture(t).setExtras(extras);
  const mesh = d.createMesh().addPrimitive(d.createPrimitive().setAttribute('POSITION', a).setMaterial(m));
  d.createScene('original').addChild(d.createNode('selectable-part').setMesh(mesh).setTranslation([offset, 0, 0]).setExtras({ default_hidden: false }));
  return new NodeIO().writeBinary(d);
}
test('bundles state scenes while sharing exact textures, materials, meshes, accessors', async () => {
  const a = await model(), b = await model(3);
  const result = await bundleStates([{ scene: 'initial', bytes: a }, { scene: 'applied', bytes: b }], 'initial');
  assert.deepEqual(result.after, { scenes: 2, meshes: 1, materials: 1, textures: 1, accessors: 1 });
  const d = await new NodeIO().readBinary(result.bytes);
  assert.equal(d.getRoot().getDefaultScene()!.getName(), 'initial');
  assert.deepEqual(Buffer.from(d.getRoot().listTextures()[0]!.getImage()!), png);
  await verifyBundledScene(result.bytes, 'initial', a);
  await verifyBundledScene(result.bytes, 'applied', b);
  await assert.rejects(verifyBundledScene(result.bytes, 'applied', a), /verification failed/);
});
test('material provenance extras remain distinct even with identical texture bytes', async () => {
  const r = await bundleStates([{ scene: 'a', bytes: await model() }, { scene: 'b', bytes: await model(0, { source: 'other' }) }], 'a');
  assert.equal(r.after.textures, 1); assert.equal(r.after.materials, 2);
});
test('rejects missing/duplicate scene selectors', async () => {
  const bytes = await model();
  await assert.rejects(bundleStates([{ scene: 'a', bytes }, { scene: 'a', bytes }], 'a'), /uniquely/);
  await assert.rejects(bundleStates([{ scene: 'a', bytes, sourceScene: 'wrong' }], 'a'), /Missing source/);
  const r = await bundleStates([{ scene: 'a', bytes }], 'a');
  await assert.rejects(verifyBundledScene(r.bytes, 'missing', bytes), /Missing or ambiguous/);
});
test('geometry and node metadata changes fail independent scene verification', async () => {
  const bytes = await model(), r = await bundleStates([{ scene: 'a', bytes }], 'a');
  const d = await new NodeIO().readBinary(r.bytes);
  d.getRoot().listNodes()[0]!.setExtras({ default_hidden: true });
  await assert.rejects(verifyBundledScene(await new NodeIO().writeBinary(d), 'a', bytes), /verification failed/);
  const changed = await new NodeIO().readBinary(r.bytes);
  changed.getRoot().listAccessors()[0]!.getArray()![0] = 2;
  await assert.rejects(verifyBundledScene(await new NodeIO().writeBinary(changed), 'a', bytes), /verification failed/);
});
async function fixture(standalone = false) {
  const temp = await mkdtemp(join(process.cwd(), 'work-state-bundle-test-'));
  temporaryDirs.push(temp);
  const input = join(temp, 'input'), output = join(temp, 'stage'); await mkdir(input);
  await writeFile(join(input, 'model.glb'), await model());
  await writeFile(join(input, 'model-applied.glb'), await model(2));
  const d: any = { id: 'fixture', model: 'model.glb' };
  d[standalone ? 'standalone_variants' : 'state_variants'] = { initial: { model: 'model.glb' }, applied: { model: 'model-applied.glb' } };
  await writeFile(join(input, 'asset.json'), JSON.stringify(d));
  return { temp, input, output };
}
test('state base aliases initial scene and stages incrementally with corruption recovery', async () => {
  const f = await fixture();
  const first = await stageAsset(f.input, f.output);
  assert.equal(first.after.scenes, 2);
  assert.deepEqual(first.states.map((s: any) => s.scene), ['initial', 'applied']);
  assert.equal((await stageAsset(f.input, f.output)).skipped, true);
  await writeFile(join(f.output, 'model.glb'), 'corrupt');
  assert.ok(!(await stageAsset(f.input, f.output)).skipped);
  await writeFile(join(f.input, 'model-applied.glb'), await model(5));
  assert.notEqual((await stageAsset(f.input, f.output)).source_signature, first.source_signature);
});
test('standalone states retain a distinct covered default and update only model selectors', async () => {
  const f = await fixture(true), r = await stageAsset(f.input, f.output);
  assert.equal(r.after.scenes, 3);
  const d = JSON.parse(await readFile(join(f.output, 'asset.json'), 'utf8'));
  assert.equal(d.model_scene, 'default'); assert.equal(d.standalone_variants.applied.model, 'model.glb');
  assert.equal(d.standalone_variants.applied.model_scene, 'applied');
  await assert.rejects(stageAsset(f.input, f.input), /must not overwrite/);
});
test('stateful detection includes external variants and embedded reveal/state triggers', () => {
  assert.equal(isStateful({ standalone_variants: {} }), true);
  assert.equal(isStateful({ components: [{ reveal_patch_ids: ['p1'] }] }), true);
  assert.equal(isStateful({ components: [{ sight_patch_before_ids: ['p1'] }] }), true);
  assert.equal(isStateful({ components: [{}] }), false);
});
