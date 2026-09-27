/** Display names do not change the identifiers used by missions and map files. */
const builtInNames: Record<string, string> = {
  croisement01: "Crossroads 1",
  croisement02: "Crossroads 2",
  croisement03: "Crossroads 3",
  derby: "Derby",
  leicester: "Leicester",
  lincoln: "Lincoln",
  nottingham: "Nottingham",
  sherwood: "Sherwood (Refined)",
  wychford: "Wychford",
  york: "York",
};

export function publishedMapLabel(name: string, modified: boolean) {
  return (builtInNames[name.toLowerCase()] ?? name) + (modified ? " (Modified)" : "");
}
