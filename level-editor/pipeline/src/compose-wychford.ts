/** An editable riverside market town, assembled from shared assets and 3D paths. */
import { importScene } from "./import-scene.ts";
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
const size: [number, number] = [3600, 2400];
const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const filename = path.join(output, name + ".rhlos-map.json");
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
let document: Level3D = { lighting: {enabled:true,sunAzimuth:305,sunElevation:48,shadowOpacity:.78}, version: 1, map: name, size, camera, sceneAssets: [], objects: [], groups: [],
  notes: "The Tollkeeper's Ledger. Editable market-town layout: eastern ridge stronghold, western village and market, central river and mill. Patrols, navigation and mission scripting are not implemented." };
const riverPoints: [number,number,number][] = [[1770,0,0],[1710,380,0],[1610,780,0],
  [1650,1080,0],[1690,1370,0],[1740,1660,0],[1680,1940,0],[1560,2400,0]];
const riverSamples=splineCurve({id:"river",name:"river",kind:"river",width:110,repeatLength:220,closed:false,points:riverPoints},camera)
  .getPoints(1024).map(p=>[p.x,-p.y*Math.sin(camera.elevation_deg*Math.PI/180)]);
const ease = (n:number) => { const t=Math.max(0,Math.min(1,n)); return t*t*(3-2*t); };
function riverX(y:number) {
  const i=Math.max(0,riverSamples.findIndex((p,j)=>j>0 && p[1]!>=y)-1);
  const a=riverSamples[i]!,b=riverSamples[i+1]!;
  return a[0]!+(b[0]!-a[0]!)*(y-a[1]!)/(b[1]!-a[1]!);
}
function groundHeight(x:number,y:number) {
  const ridge=Math.hypot((x-2720)/760,(y-820)/900);
  const hill=68*(1-ease((ridge-.60)/.4));
  const rolling=8*Math.sin(x/380)*Math.sin(y/430)+18*(1-ease(x/330));
  const shore=ease((Math.abs(x-riverX(y))-54)/68);
  return (16+hill+rolling)*shore-5*(1-shore);
}
async function place(id: string, label: string, x: number, y: number, rotation=0) {
  const source = await asset(id);
  const inserted = insertProjectionAsset(document, source.descriptor, source.reference, [x,y,groundHeight(x,y)]);
  document = inserted.document;
  const group=document.groups.find(group => group.id === inserted.selection.id)!;
  group.name=label;
  group.transform.rot_deg=rotation;
}
type Placement = [string,string,number,number,number?];
const layout = JSON.parse(await fs.readFile(new URL("../../maps/wychford/layout.json",import.meta.url),"utf8")) as {
  buildings:Placement[]; props:Placement[]; fences:Placement[]; terrain:Placement[];
  roads:[string,number,[number,number][]][];
};
for (const item of [...layout.buildings,...layout.props,...layout.fences]) await place(...item);
for (const item of layout.terrain) {
  const source=await asset(item[0]);
  const bounds=(source.descriptor as ProjectionAssetDescriptor & {bounds_local_scene?:{min:[number,number,number];max:[number,number,number]}}).bounds_local_scene;
  let x=item[2],y=item[3];
  if(bounds){x=Math.max(-bounds.min[0],Math.min(size[0]-bounds.max[0],x));
    const sin=Math.sin(camera.elevation_deg*Math.PI/180);
    y=Math.max(bounds.max[1]*sin,Math.min(size[1]+bounds.min[1]*sin,y));}
  await place(item[0],item[1],x,y,item[4]);
}
for(const label of ["Market bridge","Mill footbridge"]) document.groups.find(g=>g.name===label)!.transform.dz=9;
const treeAssets=["sherwood-leaning-tree","leicester-moat-bank-tree","sherwood-spreading-oak",
  "leicester-southeast-cottage-tree"];
const trees=[[190,230],[360,340],[210,620],[180,840],[170,1240],[170,1780],[140,2120],
  [380,2320],[970,2300],[1480,2290],[1520,610],[1490,1160],[1510,1530],
  [1900,260],[2070,400],[2060,720],[1980,1040],[2200,1880],[2360,2100],
  [2530,2240],[2750,2280],[3300,2260],[3430,1900],[3390,1580],[3430,1170],
  [3410,860],[3320,480],[3110,210],[2910,130],[2620,190],[2340,240],[300,175],[170,470],[270,540],[170,720],
  [180,970],[180,1520],[190,1940],[220,2280],[1220,2300],[1490,2100],
  [1900,550],[2020,880],[1910,1390],[2290,2250],[2730,2110],[3370,2060],
  [3330,1740],[3370,1340],[3350,1030],[3290,290]];
for(const [i,[x,y]] of trees.entries()) await place(treeAssets[i%treeAssets.length]!,"Woodland tree "+(i+1),x!,y!);
for(const [i,[x,y]] of [[1550,220],[1590,900],[1800,1220],[1770,2110],[2100,1650],[2280,340],
  [3290,930],[3260,1460],[330,580],[210,2010],[2560,2180],[2980,210]].entries())
  await place(["sherwood-rock-057","sherwood-rock-059","sherwood-rock-062","sherwood-rock-067","sherwood-rock-074","sherwood-rock-080"][i%6]!,"Rock outcrop "+i,x!,y!);
for(const item of [
  ["sherwood-camp-table-011","Bread stall",930,1530],
  ["sherwood-camp-table-012","Cloth stall",1160,1520],
  ["sherwood-camp-table-014","Pottery stall",1220,1450],
  ["sherwood-round-stool","Potter's stool",540,2160],
  ["sherwood-cooking-cauldron","Market cookpot",1190,1570],
  ["sherwood-cooper-barrel","Cooper's finished cask",740,2280],
  ["sherwood-supply-barrel","Mill grain cask",1960,2000],
  ["sherwood-logs-116","Carpenter's logs",410,1770],
  ["sherwood-logs-117","Garrison firewood",2940,1180],
  ["sherwood-logs-118","Brewer's fuel",680,1880],
] as Placement[]) await place(...item);
const battlement=await asset("derby-upper-east-curtain");
document.assetSources!.push(battlement.reference);
const corner=await asset("derby-lower-west-wall-turret");
document.assetSources!.push(corner.reference);
const contour:[number,number][]=[[2405,1370],[2170,1160],[2200,580],[2460,380],[3090,480],[3190,970],[2940,1300],[2670,1380]];
document.splines=[
  {id:"wych-river",name:"River Wych",kind:"river",width:110,repeatLength:220,closed:false,points:riverPoints},
  {id:"ridge-curtain",name:"Ridge curtain",kind:"wall",asset:battlement.reference.id,axis:"x",sourceAngle:82.4,
   cornerAsset:corner.reference.id,cornerMinAngle:25,cornerScale:1.65,cornerWidthScale:1,sourceStart:.18,sourceEnd:.72,flipCrossSection:true,width:44,repeatLength:340,closed:false,
   points:contour.map(([x,y])=>[x,y,groundHeight(x,y)])},
];
function road(label:string,width:number,points:[number,number][]) {
  const path:LevelSpline={id:"path-"+document.splines!.length,name:label,kind:"road",width,repeatLength:160,closed:false,
    points:points.map(([x,y])=>[x,y,0])};
  // Densely sample the centerline so every footpath follows the relief.
  const samples=splineCurve(path,camera).getPoints(Math.max(2,Math.ceil(splineCurve(path,camera).getLength()/35)));
  path.points=samples.map(p=>{const x=p.x,y=-p.y*Math.sin(camera.elevation_deg*Math.PI/180);return [x,y,groundHeight(x,y)+1.5];});
  document.splines!.push(path);
}
for(const [label,width,points] of layout.roads) road(label,width,points);
// Door approaches meet streets at deliberate junctions and leave the yards open.
for(const [label,points] of [
  ["Baker doorstep",[[490,835],[510,900],[530,950]]],
  ["Apothecary doorstep",[[960,860],[975,920],[960,970]]],
  ["Weaver doorstep",[[1400,950],[1430,1000],[1450,1050]]],
  ["Church porch",[[570,1340],[600,1410],[600,1460]]],
  ["Guildhall steps",[[1230,1340],[1190,1390],[1180,1460]]],
  ["Carpenter yard",[[355,1700],[350,1780],[300,1810]]],
  ["Brewer front yard",[[735,1860],[710,1960],[720,2040]]],
  ["Granary yard",[[1080,1985],[1150,2010],[1220,2020]]],
  ["Ferry steps",[[1460,1840],[1510,1870],[1560,1850]]],
  ["Potter approach",[[490,2160],[570,2200],[850,2160]]],
  ["Cooper approach",[[700,2270],[830,2240],[860,2260]]],
  ["Dyer approach",[[1365,2205],[1480,2170],[1540,1990],[1560,1850]]],
  ["Reeve gate",[[1150,585],[1160,625],[1200,635]]],
  ["Mill door",[[1840,1840],[1850,1890],[1900,1920]]],
  ["Keep approach",[[2640,1020],[2680,1110],[2630,1160]]],
  ["Stores approach",[[3040,1190],[2800,1200],[2630,1160]]],
  ["Gatekeeper yard",[[2920,1690],[2860,1760],[2790,1790]]],
  ["Stable entrance",[[3080,1970],[3070,2050],[3010,2050]]],
] as [string,[number,number][]][]) road(label,21,points);
// Ground art is authored from an overhead guide and projected by the ground mesh.
const art = new URL("../../maps/wychford/", import.meta.url);
// Ground UVs cover the full texture independently of map dimensions.
const terrain = await fs.readFile(new URL("terrain.jpg", art));
const riverTile = await sharp(await fs.readFile(new URL("river.png", art))).resize(256,512,{fit:"fill"}).png().toBuffer();
const roadPixels = await sharp(await fs.readFile(new URL("path.png",art))).resize(128,256).ensureAlpha().raw().toBuffer();
for(let y=0;y<256;y++) for(let x=0;x<128;x++) {
  const edge=Math.min(x,127-x)/127;
  const irregular=.035*Math.sin(y*Math.PI/32)+.018*Math.sin(y*Math.PI/8);
  roadPixels[(y*128+x)*4+3]=Math.round(230*ease((edge-irregular)/.18));
}
const roadTile=await sharp(roadPixels,{raw:{width:128,height:256,channels:4}}).png().toBuffer();
for(const spline of document.splines!) if(spline.kind==="road") spline.texture="data:image/png;base64,"+roadTile.toString("base64");
document.splines![0]!.texture = "data:image/png;base64," + riverTile.toString("base64");
await fs.mkdir(output,{recursive:true});
await fs.writeFile(path.join(output,name+"-ground.jpg"),terrain);
const gltf=new Document(),buffer=gltf.createBuffer(),unlit=gltf.createExtension(KHRMaterialsUnlit);
const root=gltf.createNode("map").setRotation([-Math.SQRT1_2,0,0,Math.SQRT1_2]);
gltf.createScene("scene").addChild(root);
const material=gltf.createMaterial("Wychford ground").setDoubleSided(true)
  .setBaseColorTexture(gltf.createTexture().setImage(terrain).setMimeType("image/jpeg"))
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
const intermediate = path.join(libraryDir,"../work",name+"-ground.scene.glb");
await new NodeIO().registerExtensions(ALL_EXTENSIONS).write(intermediate,gltf);
document = (await importScene(intermediate,libraryDir,document as unknown as Record<string,unknown>)).document;
const scene=parseSceneDoc({version:1,standalone:true,map:name,size,camera,placements:[],ground:{texture:name+"-ground.jpg",rect:[0,0,...size]}});
parseLevel3D(document,{scene});
await fs.writeFile(filename,JSON.stringify(document,null,2)+"\n");

console.log(JSON.stringify({map:name,instances:document.groups.length,paths:document.splines?.length ?? 0,assets:cache.size,output}));
