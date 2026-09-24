import assert from "node:assert/strict";
import test from "node:test";
import sharp from "sharp";
import {validatePadding,padTransport,cropTransport,type Padding} from "./transport-padding.ts";

const padding:Padding={version:1,kind:"bottom-padding",width:1024,height:640,
  content_box:{left:0,top:0,width:1024,height:512}};
const layout={width:1024,height:512};

test("transport padding requires the exact approved unshifted content box",()=>{
  assert.deepEqual(validatePadding(layout,padding,padding),padding);
  assert.equal(validatePadding(layout,undefined,undefined),null);
  assert.throws(()=>validatePadding(layout,padding,undefined),/authorization/);
  const shifted={...padding,content_box:{...padding.content_box,top:1}};
  assert.throws(()=>validatePadding(layout,shifted,shifted),/scaled or shifted/);
  assert.throws(()=>validatePadding({width:1024,height:513},padding,padding),/scaled or shifted/);
});

test("padding and cropping preserve every original RGBA byte without scaling",async()=>{
  const pixels=Buffer.alloc(1024*512*4);
  for(let i=0;i<pixels.length;i+=4){pixels[i]=(i/4)%251;pixels[i+1]=(i/4096)%239;pixels[i+2]=83;pixels[i+3]=(i/4)%256;}
  const png=await sharp(pixels,{raw:{width:1024,height:512,channels:4}}).png().toBuffer();
  const transport=await padTransport(png,padding);
  const metadata=await sharp(transport).metadata();assert.equal(metadata.width,1024);assert.equal(metadata.height,640);
  const restored=await sharp(await cropTransport(transport,padding)).ensureAlpha().raw().toBuffer();
  assert.deepEqual(restored,pixels);
  const raw=await sharp(transport).ensureAlpha().raw().toBuffer();
  for(let i=1024*512*4;i<raw.length;i+=4)assert.deepEqual(raw.subarray(i,i+4),Buffer.from([0,0,0,255]));
});

test("mask padding is entirely locked and wrong response dimensions fail",async()=>{
  const mask=await sharp({create:{width:1024,height:512,channels:4,background:{r:255,g:255,b:255,alpha:0}}}).png().toBuffer();
  const padded=await padTransport(mask,padding,true);const raw=await sharp(padded).ensureAlpha().raw().toBuffer();
  for(let i=1024*512*4;i<raw.length;i+=4)assert.equal(raw[i+3],255);
  await assert.rejects(cropTransport(mask,padding),/refusing to resize/);
  assert.equal(await padTransport(mask,null),mask);
});
