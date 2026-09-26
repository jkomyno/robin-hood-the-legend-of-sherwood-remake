/** Populate the authored town and pack only the directional sprites it uses. */
import { loadSceneModel } from "./scene-assets.ts";
import fs from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { parseLevel3D, gameToScene, validatePopulation, type Population, type PopulationSprite, type PopulationSpriteFrame, type Vec3 } from "@rle/shared";
import { decodeSpritePixels } from "../../app/src/entity-projection.ts";
import { libraryDir, datadirPath } from "./env.ts";

const scenePath=path.join(libraryDir,"scenes/Wychford.rhlos-map.json");
const document=parseLevel3D(JSON.parse(await fs.readFile(scenePath,"utf8")));
const recipe=JSON.parse(await fs.readFile(new URL("../../maps/wychford/population.json",import.meta.url),"utf8"));
const groundSource=document.sceneAssets.find(asset=>asset.role==="ground");
if(!groundSource)throw new Error("Map has no terrain asset");
const gltf=await loadSceneModel(libraryDir,groundSource);
const primitive=gltf.getRoot().listNodes().find(n=>n.getName()==="ground")!.getMesh()!.listPrimitives()[0]!;
const vertices=primitive.getAttribute("POSITION")!.getArray()!;
const indices=primitive.getIndices()!.getArray()!;
function ground(x:number,y:number):number {
  const [px,py]=gameToScene(document.camera,x,y,0);
  let height=-Infinity;
  for(let i=0;i<indices.length;i+=3){
    const a=indices[i]!*3,b=indices[i+1]!*3,c=indices[i+2]!*3;
    const ax=vertices[a]!,ay=vertices[a+1]!,bx=vertices[b]!,by=vertices[b+1]!,cx=vertices[c]!,cy=vertices[c+1]!;
    const denominator=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy);
    if(Math.abs(denominator)<1e-8)continue;
    const u=((by-cy)*(px-cx)+(cx-bx)*(py-cy))/denominator;
    const v=((cy-ay)*(px-cx)+(ax-cx)*(py-cy))/denominator;
    if(u>=-1e-5&&v>=-1e-5&&u+v<=1+1e-5)height=Math.max(height,u*vertices[a+2]!+v*vertices[b+2]!+(1-u-v)*vertices[c+2]!);
  }
  if(!Number.isFinite(height))throw new Error(`Population placement outside terrain: ${x},${y}`);
  return height*Math.cos(document.camera.elevation_deg*Math.PI/180);
}
function position(p:number[]):Vec3{return [p[0]!,p[1]!,p[2]??ground(p[0]!,p[1]!)+1];}
const population:Population={version:1,spriteCatalog:"population/wychford/sprites.json",actors:recipe.actors.map((a:any)=>({...a,position:position(a.position)})),items:recipe.items.map((i:any)=>({...i,position:position(i.position)})),routes:[]};
for(const r of recipe.routes){
  const controls=r.points.map((p:any)=>({...p,position:position(p.position)}));
  const points=[];
  for(let i=0;i<controls.length;i++){
    const a=controls[i];points.push(a);
    const b=controls[i+1]??(r.mode==="loop"?controls[0]:null);if(!b)continue;
    const count=Math.ceil(Math.hypot(b.position[0]-a.position[0],b.position[1]-a.position[1])/30);
    for(let j=1;j<count;j++){
      const t=j/count,x=a.position[0]+(b.position[0]-a.position[0])*t,y=a.position[1]+(b.position[1]-a.position[1])*t;
      const explicit=r.points[i].position.length===3 && (r.points[i+1]??r.points[0]).position.length===3;
      points.push({position:[x,y,explicit?a.position[2]+(b.position[2]-a.position[2])*t:ground(x,y)+1] as Vec3,wait:0});
    }
  }
  population.routes.push({...r,points});
}
// Wall sentries and wall patrols stand on the curtain walk, not the ground below it.
const wall=document.splines!.find(p=>p.id==="ridge-curtain")!;
for(const entry of [...population.actors,...population.routes.flatMap(r=>r.points)]){
  const elevated=(entry as any).wallSection as number|undefined;
  if(elevated===undefined)continue;
  const a=wall.points[elevated]!,b=wall.points[elevated+1]!;
  const x=entry.position[0],y=entry.position[1];
  const t=Math.max(0,Math.min(1,((x-a[0])*(b[0]-a[0])+(y-a[1])*(b[1]-a[1]))/((b[0]-a[0])**2+(b[1]-a[1])**2)));
  entry.position[2]=a[2]+(b[2]-a[2])*t+111;
}
validatePopulation(population);
const source=path.join(datadirPath(),"Data/Characters");
const output=path.join(libraryDir,"population/wychford");await fs.mkdir(output,{recursive:true});
const sprites:Record<string,PopulationSprite>={};
for(const id of [...new Set([...population.actors,...population.items].map(a=>a.sprite))]){
  const def=recipe.sprites[id];if(!def)throw new Error("Missing sprite recipe: "+id);
  const folder=path.join(source,def.filename+".rhs.d");
  const manifest=JSON.parse(await fs.readFile(path.join(folder,"manifest.json"),"utf8"));
  const profile=manifest.profiles.find((p:any)=>p.name===def.profile);if(!profile)throw new Error("Missing profile: "+def.profile);
  const kind=def.kind??"character",idle:Record<string,PopulationSpriteFrame[]>={},walk:Record<string,PopulationSpriteFrame[]>={};
  const composites:{input:Buffer;left:number;top:number}[]=[];let x=1,y=1,rowHeight=0;
  const width=1024;
  for(const [action,target] of [[def.idle??3,idle],...(def.walk===undefined?[]:[[def.walk,walk]])] as [number,Record<string,PopulationSpriteFrame[]>][]){
    const rows=profile.rows.filter((r:any)=>r.action_id===action && (kind!=="pickup"||r.direction===0));
    if(!rows.length)throw new Error(`Missing action ${action}: ${id}`);
    for(const row of rows){
      const frames:PopulationSpriteFrame[]=[];
      for(const frame of row.frames){
        let framePath=path.join(folder,row.path,frame.file);
        try{await fs.access(framePath);}catch{framePath=path.join(folder,def.profile.replace(/[\\/:*?"<>|]/g,"_"),row.path,frame.file);}
        const raw=await sharp(framePath).ensureAlpha().raw().toBuffer({resolveWithObject:true});
        const pixels=new Uint8ClampedArray(raw.data);decodeSpritePixels(pixels,manifest.pixel_format!=="rgba");
        const w=raw.info.width,h=raw.info.height;
        if(x+w+1>width){x=1;y+=rowHeight+2;rowHeight=0;}
        const png=await sharp(Buffer.from(pixels),{raw:{width:w,height:h,channels:4}}).png().toBuffer();
        composites.push({input:png,left:x,top:y});
        frames.push({rect:[x,y,w,h],offset:[frame.offset_x-profile.center_x,profile.center_y-frame.offset_y],duration:((frame.delay??2)+1)/25});
        x+=w+2;rowHeight=Math.max(rowHeight,h);
      }
      target[kind==="pickup"?"-1":String(row.direction)]=frames;
    }
  }
  const height=y+rowHeight+1,image=`population/wychford/${id}.png`;
  await sharp({create:{width,height,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).composite(composites).png().toFile(path.join(libraryDir,image));
  sprites[id]={image,width,height,kind,idle,...(def.walk!==undefined?{walk}:{})};
  console.log("Packed",id,composites.length,"frames");
}
await fs.writeFile(path.join(output,"sprites.json"),JSON.stringify({version:1,sprites}));
document.population=population;
document.notes="The Tollkeeper’s Ledger. Fortified riverside market town with authored population and patrol previews. Playable mission export, navigation and scripting remain pending.";
parseLevel3D(document);
await fs.writeFile(scenePath,JSON.stringify(document,null,2)+"\n");
console.log(JSON.stringify({actors:population.actors.length,items:population.items.length,routes:population.routes.length,sprites:Object.keys(sprites).length}));
