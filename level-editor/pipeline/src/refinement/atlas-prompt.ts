/** Exact-coordinate atlas inputs must not be described as eight camera views. */
export function atlasPrompt(kind: string | undefined, views: number, variant: string, lighting: boolean): string | undefined {
  if (kind !== "planar-atlas" && kind !== "uv-atlas") return undefined;
  if (views !== 1 || variant !== "short") throw new Error("Atlas generation requires exactly one view and short prompt");
  if (kind === "uv-atlas" && !lighting) throw new Error("UV atlas requires an aligned geometry lighting reference");
  const planar = kind === "planar-atlas";
  return (planar
    ? "Complete the missing neutral-gray areas of this single planar texture atlas. It is one image, not a contact sheet. Continue the surrounding ground textures at the same pixel scale and exact coordinates. Gray cutouts mark unknown ground underneath removed scenery, not object silhouettes to preserve. Preserve every existing textured pixel exactly. Do not resize, crop, reframe, rotate, or add objects. Preserve the existing planar lighting without inventing terrain relief."
    : "Complete the missing neutral-gray areas of this single terrain UV texture atlas. It is one image, not a contact sheet. Continue the surrounding ground materials at the same pixel scale and exact UV coordinates. Gray cutouts are unseen ground beneath removed scenery; do not reconstruct buildings or props. Preserve every existing textured pixel exactly. Do not resize, crop, reframe, rotate, or add objects. The existing terrain includes modeled height changes; follow their supplied lighting without inventing additional relief.")
    + (lighting ? (planar
      ? " The second image is the exact aligned planar surface in pure gray; use it as the lighting and coverage reference. Return only the completed first image."
      : " The second image maps the actual terrain triangles' directional lighting into these same UV coordinates. Use it as the exact lighting and coverage reference. Preserve holes and boundaries. Return only the completed first image.") : "");
}
