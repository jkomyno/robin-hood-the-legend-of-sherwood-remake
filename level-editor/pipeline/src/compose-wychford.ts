/** An editable riverside market town, assembled from shared assets and 3D paths. */
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import sharp from "sharp";
import { Document, NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRMaterialsUnlit } from "@gltf-transform/extensions";
import { parseProjectionAssetIndex, parseProjectionAssetDescriptor, parseLevel3D, parseSceneDoc,
  groundToScene, type LevelSpline, type Level3D, type ExternalAssetSource, type ProjectionAssetDescriptor } from "@rle/shared";
import { splineCurve } from "../../app/src/spline-geometry.ts";
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
let document: Level3D = { lighting: {enabled:true,sunAzimuth:305,sunElevation:48,shadowOpacity:.48}, version: 1, map: name, size, camera, glb: name + "-volumes.scene.glb", objects: [], groups: [],
  notes: "The Tollkeeper's Ledger. Editable market-town layout: northern keep, central market, western church/orchard, eastern river workshops. Patrols, navigation and mission scripting are not implemented." };
const riverPoints: [number,number,number][] = [[1950,0,0],[1910,300,0],[1770,680,0],
  [1800,1030,0],[1810,1320,0],[1870,1540,0],[1850,1750,0],[1740,1990,0],[1690,2200,0]];
const riverSamples=splineCurve({id:"river",name:"river",kind:"river",width:110,repeatLength:220,closed:false,points:riverPoints},camera)
  .getPoints(1024).map(p=>[p.x,-p.y*Math.sin(camera.elevation_deg*Math.PI/180)]);
const ease = (n:number) => { const t=Math.max(0,Math.min(1,n)); return t*t*(3-2*t); };
function riverX(y:number) {
  const i=Math.max(0,riverSamples.findIndex((p,j)=>j>0 && p[1]!>=y)-1);
  const a=riverSamples[i]!,b=riverSamples[i+1]!;
  return a[0]!+(b[0]!-a[0]!)*(y-a[1]!)/(b[1]!-a[1]!);
}
function groundHeight(x:number,y:number) {
  const hill = 46 * (1-ease((Math.max(Math.abs(x-990)/610,Math.abs(y-660)/480)-.74)/.26));
  const shore=ease((Math.abs(x-riverX(y))-54)/62);
  return (14+hill)*shore-5*(1-shore);
}
async function place(id: string, label: string, x: number, y: number, rotation=0) {
  const source = await asset(id);
  const inserted = insertProjectionAsset(document, source.descriptor, source.reference, [x,y,groundHeight(x,y)]);
  document = inserted.document;
  const group=document.groups.find(group => group.id === inserted.selection.id)!;
  group.name=label;
  group.transform.rot_deg=rotation;
}
const buildings: [string,string,number,number][] = [
  ["leicester-great-keep","Tollkeeper's keep",980,600],
  ["derby-south-gatehouse","Market gate",1010,1020],
  ["derby-east-courtyard-north-shelter","Quartermaster's shelter",1300,880],
  ["derby-east-bailey-well","Garrison well",790,875],
  ["leicester-south-hall","Wychford guildhall",1280,1220],
  ["leicester-north-village-cottage","Baker's house",730,1460],
  ["leicester-northeast-gabled-house","Market apothecary",730,1680],
  ["leicester-east-edge-thatched-house","Cloth merchant",1460,1430],
  ["leicester-mill-south-cottage","Cooper's cottage",1450,1660],
  ["leicester-village-well","Market well",1080,1570],
  ["leicester-northeast-handcart","Produce cart",1250,1510],
  ["derby-lower-east-supplies","Merchant's wagon",890,1570],
  ["leicester-northeast-handcart","Cloth market cart",1190,1590],
  ["leicester-south-stilt-shed","Market storehouse",1280,1770],
  ["leicester-church","St. Edmund's church",420,1190],
  ["leicester-church-west-archway","Churchyard entrance",490,1450],
  ["leicester-courtyard-well","Churchyard well",275,1390],
  ["leicester-mill-north-cottage","Sexton's cottage",350,1610],
  ["leicester-southeast-cottage","Orchard keeper's house",420,1880],
  ["leicester-mill-north-cottage","Riverside workshop",1630,1190],
  ["leicester-east-riverside-house","Ferryman's house",2080,1440],
  ["leicester-northeast-longhouse","East-bank granary",2180,1130],
  ["leicester-watermill","Wychford watermill",1900,1900],
  ["leicester-south-footbridge","Lower river crossing",1850,1750],
  ["leicester-east-village-footbridge","Open timber market bridge",1810,1320],
  ["leicester-east-riverside-hay-mound","Granary haystack",2310,1300],
  ["derby-east-bailey-stacked-timber","Workshop timber",1650,1375],
  ["derby-lower-east-supplies","Granary cart",2060,1250],
  ["leicester-mill-south-trough","Ferryman's trough",2200,1540],
  ["leicester-east-riverside-hay-mound","South approach haystack",1320,1940],
];
buildings.push(
  ["leicester-southeast-wall-turret","Northwest bailey bastion",540,420],
  ["derby-lower-west-wall-turret","Northeast bailey bastion",1460,440],
  ["leicester-southeast-wall-turret","Southeast bailey bastion",1450,990],
  ["derby-lower-west-wall-turret","Southwest bailey bastion",540,960],
  ["leicester-northeast-gabled-house","West market shop",600,1450],
  ["leicester-mill-south-cottage","Brewery",650,1260],
  ["leicester-southeast-cottage","South street merchant",770,1910],
  ["leicester-north-village-cottage","Cobbler",1080,1850],
  ["leicester-east-edge-thatched-house","Dyer",1460,1860],
  ["leicester-mill-south-cottage","Carter",1220,2070],
  ["leicester-mill-north-cottage","Weaver",1480,2070],
  ["leicester-northeast-gabled-house","East-bank smith",2180,1650],
  ["leicester-southeast-manor","East-bank manor",2300,1990],
  ["leicester-south-stilt-shed","Timber wharf",2050,950],
  ["leicester-northeast-longhouse","North-bank warehouse",2170,740],
  ["leicester-mill-south-cottage","Church lane cottage",430,1740],
);
for (const item of buildings) await place(...item);
const crossing=document.groups.find(group => group.name === "Open timber market bridge")!;
crossing.transform.rot_deg=56;
crossing.transform.dz=8;

for (const [x,y] of [[1580,1310],[1605,1320],[2160,1200],[2190,1210],[890,1620],[1240,1730],[1270,930]])
  await place("derby-east-bailey-crate","Working-yard barrel",x!,y!);
const treeAssets = ["leicester-northwest-forest-tree", "leicester-north-church-tree",
  "leicester-moat-bank-tree", "leicester-northwest-tower-tree", "leicester-southeast-cottage-tree"];
const trees = [[120,400],[200,520],[160,740],[170,890],[200,1030],[140,1240],[180,1480],
  [150,1710],[220,1990],[350,2110],[560,2110],[130,2150],
  [1650,490],[1650,770],[1630,1040],[1680,1550],[1610,1910],
  [2130,360],[2310,400],[2400,590],[2380,880],[2390,1200],[2400,1460],
  [2300,1780],[2100,2120],[1940,2150]];
for (const [i,p] of trees.entries()) await place(treeAssets[i % treeAssets.length]!,
  "Woodland / riverside tree " + (i+1),p[0]!,p[1]!);
for (const item of [
  ["leicester-southwest-woodland-bank","Western wooded ridge",170,530],
  ["leicester-southwest-edge-bank","Northwest rock bank",280,230],
  ["leicester-southwest-field-bank","Northern field terrace",1090,170],
  ["leicester-south-field-corner-bank","Riverside bank",1670,1100],
  ["leicester-south-edge-field-bank","Mill approach bank",1650,1860],
  ["leicester-north-village-field-fence","Church garden enclosure",520,1930],
  ["leicester-south-cottage-garden-fence","South street gardens",820,2040],
  ["leicester-roadside-rail-fence","East-bank pasture",2280,1480],
  ["leicester-northeast-field-boundary","Northern pasture",2320,580],
  ["leicester-mill-south-yard-wall","Mill yard",2070,1910],
  ["leicester-mill-south-trough","Workshop trough",1460,1750],
  ["leicester-village-well-bucket","Market bucket",1100,1590],
  ["leicester-mill-south-barrel","Wharf cargo",2080,1040],
  ["leicester-south-field-corner-rock","River crossing rock",1750,1400],
  ["leicester-south-fence-end-rock","Woodland outcrop",290,920],
] as [string,string,number,number][]) await place(...item);
const battlement = await asset("derby-upper-east-curtain");
document.assetSources!.push(battlement.reference);
const wall = (id:string,name:string,a:[number,number],b:[number,number]):LevelSpline => ({
  id,name,kind:"wall",asset:battlement.reference.id,axis:"x",sourceAngle:82.4,
  sourceStart:.18,sourceEnd:.72,flipCrossSection:true,width:72,repeatLength:340,closed:false,
  points:[a,b].map(([x,y])=>[x,y,groundHeight(x,y)]),
});
document.splines = [
  {id:"wych-river",name:"River Wych",kind:"river",width:110,repeatLength:220,closed:false,points:riverPoints},
  wall("bailey-sw","Gate to southwest bastion",[890,1010],[540,960]),
  wall("bailey-west","West curtain",[540,960],[540,420]),
  wall("bailey-north","North curtain",[540,420],[1460,440]),
  wall("bailey-east","East curtain",[1460,440],[1450,990]),
  wall("bailey-se","Southeast bastion to gate",[1450,990],[1140,1040]),
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
// A banked river channel and raised bailey are actual ground geometry.
const nx=130,ny=110,positions:number[]=[],texcoords:number[]=[],indices:number[]=[];
for(let j=0;j<=ny;j++) for(let i=0;i<=nx;i++) {
  const x=size[0]*i/nx,y=size[1]*j/ny;
  const p=groundToScene(camera,x,y);
  positions.push(p[0],p[1],groundHeight(x,y)/Math.cos(camera.elevation_deg*Math.PI/180));
  texcoords.push(i/nx,j/ny);
}
for(let j=0;j<ny;j++) for(let i=0;i<nx;i++) {
  const a=j*(nx+1)+i,b=a+nx+1;
  indices.push(a,b+1,a+1,a,b,b+1);
}
const pos=gltf.createAccessor().setType("VEC3").setArray(new Float32Array(positions)).setBuffer(buffer);
const uv=gltf.createAccessor().setType("VEC2").setArray(new Float32Array(texcoords)).setBuffer(buffer);
const idx=gltf.createAccessor().setType("SCALAR").setArray(new Uint16Array(indices)).setBuffer(buffer);
root.addChild(gltf.createNode("ground").setMesh(gltf.createMesh().addPrimitive(gltf.createPrimitive()
  .setAttribute("POSITION",pos).setAttribute("TEXCOORD_0",uv).setIndices(idx).setMaterial(material))));
await new NodeIO().registerExtensions(ALL_EXTENSIONS).write(path.join(output,document.glb),gltf);
document.provenance={glb_sha256:hash(await fs.readFile(path.join(output,document.glb)))};
const scene=parseSceneDoc({version:1,standalone:true,map:name,size,camera,placements:[],ground:{texture:name+"-ground.png",rect:[0,0,...size]}});
parseLevel3D(document,{scene});
await fs.writeFile(filename,JSON.stringify(document,null,2)+"\n");
await fs.writeFile(path.join(output,name+"-volumes.scene.json"),JSON.stringify(scene,null,2)+"\n");
console.log(JSON.stringify({map:name,instances:document.groups.length,paths:document.splines.length,assets:cache.size,output}));
