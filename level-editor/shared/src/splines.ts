/** Editable paths in game coordinates. Wall geometry is derived from pinned assets. */
export interface LevelSpline {
  id: string;
  name: string;
  kind: "river" | "wall";
  points: [number, number, number][];
  closed: boolean;
  width: number;
  repeatLength: number;
  /** River tile embedded in the document so save/reload needs no extra file grant. */
  texture?: string;
  /** Wall asset ID in Level3D.assetSources. */
  asset?: string;
  axis?: "x" | "y";
  sourceAngle?: number;
  /** Reflect the cross-section so the parapet can face the exterior. */
  flipCrossSection?: boolean;
  /** Retained interval along the source model, useful for trimming fixed end caps. */
  sourceStart?: number;
  sourceEnd?: number;
}
