/** Transport adapters for the same approved image model and image references. */
export type ImageProvider = "openai" | "openrouter";
export function imageProvider(value = "openai"): ImageProvider {
  if (value !== "openai" && value !== "openrouter") throw new Error("Choose --provider openai or openrouter");
  return value;
}
export function providerIdentity(provider: ImageProvider) {
  return provider === "openrouter"
    ? { provider, model: "openai/gpt-image-2.5-sunburst", endpoint: "https://openrouter.ai/api/v1/images", credential: "OPENROUTER_API_KEY" }
    : { provider, model: "gpt-image-2.5-sunburst", endpoint: "https://api.openai.com/v1/images/edits", credential: "OPENAI_API_KEY" };
}
export function openRouterBody<T extends Record<string,string>>(parameters: T, input: Buffer, lighting: Buffer | null, omitMask: boolean, auxiliary: Buffer[] = []) {
  if (!omitMask) throw new Error("OpenRouter transport requires --no-mask; local source protection remains required");
  return { ...parameters, model: providerIdentity("openrouter").model, n: Number(parameters.n),
    input_references: [input, ...(lighting ? [lighting] : []), ...auxiliary].map(bytes => ({ type: "image_url", image_url: { url: `data:image/png;base64,${bytes.toString("base64")}` } })) };
}
type Capability = { type: string; values?: string[]; min?: number; max?: number };
export function validateOpenRouterCapabilities(value: unknown, references: number): void {
  const record = value as { id?: string; endpoints?: { supported_parameters?: Record<string,Capability> }[] };
  const supports = (p: Record<string,Capability>, key: string, v: string | number) => {
    const c = p[key];
    return c?.type === "enum" ? c.values?.includes(String(v)) : c?.type === "range" && typeof v === "number" && v >= c.min! && v <= c.max!;
  };
  if (record.id !== providerIdentity("openrouter").model || !record.endpoints?.some(e => {
    const p=e.supported_parameters ?? {};
    return supports(p,"quality","high") && supports(p,"n",1) && supports(p,"input_references",references);
  })) throw new Error("OpenRouter does not advertise high quality, one output and the required image references for the approved model");
  // size/output_format are common API fields, not endpoint capability keys.
  // Exact returned dimensions and PNG format are checked before any composition.
}
