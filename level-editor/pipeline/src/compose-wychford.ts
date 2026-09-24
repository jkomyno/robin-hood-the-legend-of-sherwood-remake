/** An editable riverside market town, assembled from shared assets and 3D paths. */
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import sharp from "sharp";
import { Document, NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRMaterialsUnlit } from "@gltf-transform/extensions";
import { parseProjectionAssetIndex, parseProjectionAssetDescriptor, parseLevel3D, parseSceneDoc,
  groundToScene, type Level3D, type ExternalAssetSource, type ProjectionAssetDescriptor } from "@rle/shared";
import { insertProjectionAsset } from "../../app/src/asset-commands.ts";
import { libraryDir } from "./env.ts";

const name = "Wychford", output = path.join(libraryDir, "scenes");
const size: [number, number] = [2600, 2200];
const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const filename = path.join(output, name + ".level3d.json");
try {
  await fs.access(filename);
  if (!process.argv.includes("--overwrite")) throw new Error("Wychford already exists; use --overwrite to replace it");
} catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const entries = parseProjectionAssetIndex(JSON.parse(await fs.readFile(path.join(libraryDir, "3d-assets/index.json"), "utf8")));
const cache = new Map<string, { descriptor: ProjectionAssetDescriptor; reference: ExternalAssetSource }>();
async function asset(id: string) {
  if (cache.has(id)) return cache.get(id)!;
  const entry = entries.find(entry => entry.id === id);
  if (!entry) throw new Error("Missing shared asset " + id);
  const descriptorPath = "3d-assets/" + entry.descriptor, model = "3d-assets/" + entry.model;
  const bytes = await fs.readFile(path.join(libraryDir, descriptorPath));
  const descriptor = parseProjectionAssetDescriptor(JSON.parse(bytes.toString()));
  if (descriptor.state_variants) throw new Error("Choose a static variant for " + id);
  const result = { descriptor, reference: { id, descriptor: descriptorPath, model,
    descriptor_sha256: hash(bytes), model_sha256: hash(await fs.readFile(path.join(libraryDir, model))) } };
  cache.set(id, result);
  return result;
}
let document: Level3D = { version: 1, map: name, size, camera, glb: name + "-volumes.scene.glb", objects: [], groups: [],
  notes: "The Tollkeeper's Ledger. Editable market-town layout: northern keep, central market, western church/orchard, eastern river workshops. Patrols, navigation and mission scripting are not implemented." };
async function place(id: string, label: string, x: number, y: number) {
  const source = await asset(id);
  const inserted = insertProjectionAsset(document, source.descriptor, source.reference, [x,y,0]);
  document = inserted.document;
  document.groups.find(group => group.id === inserted.selection.id)!.name = label;
}
const buildings: [string,string,number,number][] = [
  ["leicester-great-keep","Tollkeeper's keep",980,600],
  ["derby-south-gatehouse","Market gate",1010,1020],
  ["derby-east-courtyard-north-shelter","Quartermaster's shelter",1300,880],
  ["derby-east-bailey-well","Garrison well",790,875],
  ["leicester-south-hall","Wychford guildhall",1080,1320],
  ["leicester-north-village-cottage","Baker's house",730,1460],
  ["derby-lower-northwest-cottage","Market apothecary",730,1680],
  ["leicester-east-edge-thatched-house","Cloth merchant",1460,1430],
  ["derby-lower-southeast-cottage","Cooper's cottage",1450,1660],
  ["leicester-village-well","Market well",1080,1570],
  ["leicester-northeast-handcart","Produce cart",1250,1510],
  ["derby-lower-east-supplies","Merchant's wagon",890,1570],
  ["derby-east-wall-landing","Covered market stall",960,1750],
  ["derby-east-courtyard-south-shelter","Covered market stall — east",1190,1750],
  ["leicester-church","St. Edmund's church",420,1190],
  ["leicester-church-west-archway","Churchyard entrance",490,1450],
  ["leicester-courtyard-well","Churchyard well",275,1390],
  ["derby-lower-southwest-cottage","Sexton's cottage",350,1610],
  ["leicester-southeast-cottage","Orchard keeper's house",420,1880],
  ["leicester-mill-north-cottage","Riverside workshop",1630,1190],
  ["leicester-east-riverside-house","Ferryman's house",2080,1440],
  ["leicester-northeast-longhouse","East-bank granary",2180,1130],
  ["leicester-watermill","Wychford watermill",1940,1920],
  ["leicester-south-footbridge","Lower river crossing",1850,1750],
  ["leicester-east-village-footbridge","Open timber market bridge",1810,1320],
  ["leicester-east-riverside-hay-mound","Granary haystack",2310,1300],
  ["derby-east-bailey-stacked-timber","Workshop timber",1650,1375],
  ["derby-lower-east-supplies","Granary cart",2060,1250],
  ["leicester-mill-south-trough","Ferryman's trough",2200,1540],
  ["leicester-east-riverside-hay-mound","South approach haystack",1320,1940],
];
for (const item of buildings) await place(...item);
document.groups.find(group => group.name === "Open timber market bridge")!.transform.rot_deg = 56;

for (const [x,y] of [[1580,1310],[1605,1320],[2160,1200],[2190,1210],[890,1620],[1240,1730],[1270,930]])
  await place("derby-east-bailey-crate","Working-yard barrel",x!,y!);
const treeAssets = ["leicester-northwest-forest-tree", "leicester-north-church-tree",
  "leicester-moat-bank-tree", "leicester-northwest-tower-tree", "leicester-southeast-cottage-tree"];
const trees = [[170,1760],[310,1910],[580,1830],[190,1390],[200,1000],[250,670],
  [1690,640],[1680,900],[1660,1590],[1650,1980],[2040,650],[2280,770],
  [2370,1090],[2320,1680],[2390,2000],[760,2070],[1450,2110]];
for (const [i,p] of trees.entries()) await place(treeAssets[i % treeAssets.length]!,
  "Orchard / riverside tree " + (i+1),p[0]!,p[1]!);
const battlement = await asset("derby-upper-east-curtain");
document.assetSources!.push(battlement.reference);
document.splines = [
  { id: "wych-river", name: "River Wych", kind: "river", width: 110, repeatLength: 175, closed: false,
    points: [[1845,0,0],[1810,300,0],[1795,700,0],[1835,1030,0],[1810,1320,0],[1850,1750,0],[1800,2200,0]] },
  { id: "bailey-wall", name: "Bailey battlements — west, north, east", kind: "wall",
    asset: battlement.reference.id, axis: "x", sourceAngle: 82.4, sourceStart: 0.18, sourceEnd: 0.72,
    width: 95, repeatLength: 340, closed: false,
    points: [[840,1010,0],[570,990,0],[450,830,0],[420,490,0],[560,310,0],[1000,280,0],
      [1430,350,0],[1540,560,0],[1510,900,0],[1390,1030,0],[1180,1030,0]] },
];
// Art is painted in ground-plane proportions (roughly 2600 : 2200/sin(35°)).
// Bake it to map-pixel proportions so its detail shares the meshes' foreshortening.
const art = new URL("../../maps/wychford/", import.meta.url);
const terrain = await sharp(await fs.readFile(new URL("terrain.png", art))).resize(size[0],size[1],{fit:"fill"}).png().toBuffer();
const riverTile = await sharp(await fs.readFile(new URL("river.png", art))).resize(256,512,{fit:"fill"}).png().toBuffer();
document.splines![0]!.texture = "data:image/png;base64," + riverTile.toString("base64");
await fs.mkdir(output,{recursive:true});
await fs.writeFile(path.join(output,name+"-ground.png"),terrain);
const gltf=new Document(),buffer=gltf.createBuffer(),unlit=gltf.createExtension(KHRMaterialsUnlit);
const root=gltf.createNode("map").setRotation([-Math.SQRT1_2,0,0,Math.SQRT1_2]);
gltf.createScene("scene").addChild(root);
const material=gltf.createMaterial("Wychford ground").setDoubleSided(true)
  .setBaseColorTexture(gltf.createTexture().setImage(terrain).setMimeType("image/png"))
  .setExtension("KHR_materials_unlit",unlit.createUnlit());
const corners=[[0,0],[size[0],0],size,[0,size[1]]].map(p=>groundToScene(camera,p[0]!,p[1]!));
const pos=gltf.createAccessor().setType("VEC3").setArray(new Float32Array(corners.flat())).setBuffer(buffer);
const uv=gltf.createAccessor().setType("VEC2").setArray(new Float32Array([0,0,1,0,1,1,0,1])).setBuffer(buffer);
const idx=gltf.createAccessor().setType("SCALAR").setArray(new Uint16Array([0,2,1,0,3,2])).setBuffer(buffer);
root.addChild(gltf.createNode("ground").setMesh(gltf.createMesh().addPrimitive(gltf.createPrimitive()
  .setAttribute("POSITION",pos).setAttribute("TEXCOORD_0",uv).setIndices(idx).setMaterial(material))));
await new NodeIO().registerExtensions(ALL_EXTENSIONS).write(path.join(output,document.glb),gltf);
document.provenance={glb_sha256:hash(await fs.readFile(path.join(output,document.glb)))};
const scene=parseSceneDoc({version:1,standalone:true,map:name,size,camera,placements:[],ground:{texture:name+"-ground.png",rect:[0,0,...size]}});
parseLevel3D(document,{scene});
await fs.writeFile(filename,JSON.stringify(document,null,2)+"\n");
await fs.writeFile(path.join(output,name+"-volumes.scene.json"),JSON.stringify(scene,null,2)+"\n");
console.log(JSON.stringify({map:name,instances:document.groups.length,paths:document.splines.length,assets:cache.size,output}));
