/** Display names do not change the identifiers used by missions and map files. */
const builtInNames: Record<string, string> = {
  croisement01: "Crossroads 1 (WIP)",
  croisement02: "Crossroads 2 (WIP)",
  croisement03: "Crossroads 3 (WIP)",
  derby: "Derby (Refined)",
  leicester: "Leicester (Refined)",
  lincoln: "Lincoln (Refined)",
  nottingham: "Nottingham (Refined)",
  sherwood: "Sherwood (Refined)",
  wychford: "Wychford (Example)",
  york: "York (WIP)",
};

export function publishedMapLabel(name: string, modified: boolean) {
  return (builtInNames[name.toLowerCase()] ?? name) + (modified ? " (Modified)" : "");
}
