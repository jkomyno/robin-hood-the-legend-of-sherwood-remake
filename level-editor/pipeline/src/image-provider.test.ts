import test from "node:test";
import assert from "node:assert/strict";
import { imageProvider, providerIdentity, openRouterBody, validateOpenRouterCapabilities } from "./refinement/image-provider.ts";

test("OpenRouter preserves reference order, explicit size and high quality without an API mask", () => {
  const body=openRouterBody({model:"gpt-image-2.5-sunburst",quality:"high",size:"2048x1024",n:"1",output_format:"png",prompt:"Fill missing texture"},Buffer.from("source"),Buffer.from("light"),true);
  assert.equal(body.model,"openai/gpt-image-2.5-sunburst");
  assert.equal(body.n,1);
  assert.equal(body.size,"2048x1024");
  assert.equal(body.quality,"high");
  assert.equal(body.output_format,"png");
  assert.deepEqual(body.input_references.map(r=>Buffer.from(r.image_url.url.split(",")[1]!,"base64").toString()),["source","light"]);
  assert.ok(!("mask" in body));
  assert.throws(()=>openRouterBody({},Buffer.from("x"),null,false),/--no-mask/);
});
test("Provider identity isolates cache and credentials while OpenAI remains default", () => {
  assert.equal(imageProvider(),"openai");
  assert.notDeepEqual(providerIdentity("openai"),providerIdentity("openrouter"));
  assert.throws(()=>imageProvider("other"),/Choose/);
});
test("Capability guard rejects unavailable model, quality and reference capacity", () => {
  const meta={id:"openai/gpt-image-2.5-sunburst",endpoints:[{supported_parameters:{quality:{type:"enum",values:["high"]},n:{type:"range",min:1,max:10},input_references:{type:"range",min:0,max:16}}}]};
  assert.doesNotThrow(()=>validateOpenRouterCapabilities(meta,2));
  assert.throws(()=>validateOpenRouterCapabilities(meta,17),/does not advertise/);
  assert.throws(()=>validateOpenRouterCapabilities({...meta,id:"other"},2),/does not advertise/);
  meta.endpoints[0]!.supported_parameters.quality.values=["low"];
  assert.throws(()=>validateOpenRouterCapabilities(meta,2),/does not advertise/);
});
