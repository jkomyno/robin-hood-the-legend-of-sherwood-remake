import { verifyCanonicalScene } from "./bundle-asset-states.ts";
const [model, scene, reference] = process.argv.slice(2);
if (!model || !scene || !reference)
  throw new Error("Usage: verify-canonical-scene.ts <model.gltf> <scene> <reference.gltf>");
console.log(JSON.stringify(await verifyCanonicalScene(model, scene, reference)));
