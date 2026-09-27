// Compact exterior-only models reviewed as wall corners. Full buildings and
// interior-bearing towers belong in scene objects, never in this selector.
export const cornerAssetIds = new Set([
  "derby-lower-west-wall-turret",
  "lincoln-east-gate-north-tower",
  "lincoln-east-gate-south-tower",
  "nottingham-castle-east-round-tower",
  "nottingham-northeast-round-tower",
  "nottingham-south-gate-west-tower",
]);

// Retired choices may still occur in older maps. Render those walls with a
// continuous join instead of reinstating the rejected model on map load.
export const excludedCornerAssetIds = new Set([
  "leicester-east-moat-tower", // Large building with interior geometry.
  "leicester-west-moat-tower", // Large building with interior geometry.
  "nottingham-northwest-round-tower", // Stretched, incomplete exterior texture.
]);
