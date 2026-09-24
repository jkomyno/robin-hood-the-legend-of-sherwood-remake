/** Pad only the API transport canvas; projection pixels and camera crops stay fixed. */
import sharp from "sharp";

export type Padding = {
  version: 1; kind: "bottom-padding"; width: number; height: number;
  content_box: { left: number; top: number; width: number; height: number };
};

export function validatePadding(layout: {width:number;height:number}, value: unknown, approved: unknown): Padding | null {
  if(value === undefined && approved === undefined)return null;
  if(JSON.stringify(value)!==JSON.stringify(approved))throw new Error("Transport padding differs from preparation authorization");
  const p=value as Padding | undefined;
  if(!p || p.version!==1 || p.kind!=="bottom-padding" || p.width!==1024 || p.height!==640 ||
     layout.width!==1024 || layout.height!==512 || p.content_box?.left!==0 || p.content_box?.top!==0 ||
     p.content_box.width!==1024 || p.content_box.height!==512 ||
     Object.keys(p).sort().join()!==["content_box","height","kind","version","width"].join() ||
     Object.keys(p.content_box).sort().join()!==["height","left","top","width"].join())
    throw new Error("Invalid transport padding: approved geometry must never be scaled or shifted");
  return p;
}

export async function padTransport(bytes: Buffer, padding: Padding | null, mask=false): Promise<Buffer> {
  if(!padding)return bytes;
  const info=await sharp(bytes).metadata();
  if(info.width!==padding.content_box.width || info.height!==padding.content_box.height)
    throw new Error("Transport content dimensions changed");
  // Fully opaque mask padding is locked; RGB image padding is black background.
  return sharp(bytes).ensureAlpha().extend({top:0,left:0,right:0,bottom:padding.height-padding.content_box.height,
    background:mask?{r:255,g:255,b:255,alpha:1}:{r:0,g:0,b:0,alpha:1}}).png().toBuffer();
}

export async function cropTransport(bytes: Buffer, padding: Padding | null): Promise<Buffer> {
  if(!padding)return bytes;
  const info=await sharp(bytes).metadata();
  if(info.width!==padding.width || info.height!==padding.height)
    throw new Error("Generated transport dimensions changed; refusing to resize");
  return sharp(bytes).extract(padding.content_box).png().toBuffer();
}
