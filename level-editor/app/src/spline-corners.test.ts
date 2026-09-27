import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { cornerAssetIds, excludedCornerAssetIds } from "./spline-corners.ts";
import { wallPreset } from "./wall-presets.ts";
import { wallMesh, wallCorners } from "./spline-geometry.ts";
import type { LevelSpline } from "@rle/shared";

const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const path: LevelSpline = {
  id: "wall", name: "Legacy wall", kind: "wall", asset: "wall-source",
  axis: "x", sourceStraight: true, width: 10, repeatLength: 100, closed: false,
  points: [[0, 0, 0], [100, 0, 0], [100, 100, 0]],
};

test("saved presets cannot reintroduce unreviewed or interior-bearing corners", () => {
  for (const cornerAsset of [...excludedCornerAssetIds, "unreviewed-building"]) {
    assert.ok(!cornerAssetIds.has(cornerAsset));
    const preset = wallPreset({ ...path, cornerAsset, cornerScale: 3, cornerWidthScale: 2 });
    assert.equal(preset.cornerAsset, undefined);
    assert.equal(preset.cornerScale, undefined);
    assert.equal(preset.cornerWidthScale, undefined);
    assert.equal(preset.asset, path.asset);
  }
  const cornerAsset = "derby-lower-west-wall-turret";
  assert.equal(wallPreset({ ...path, cornerAsset }).cornerAsset, cornerAsset);
});

test("legacy maps render continuous walls instead of retired corner buildings", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 10, 40), new THREE.MeshBasicMaterial());
  const sources = new Map([["asset:wall-source:body", source]]);
  const continuous = wallMesh(path, camera, sources);
  try {
    for (const cornerAsset of excludedCornerAssetIds) {
      const legacy = { ...path, cornerAsset };
      assert.deepEqual(wallCorners(legacy, camera), []);
      const result = wallMesh(legacy, camera, sources);
      assert.equal(result.children.length, continuous.children.length);
      result.children.forEach((child, i) => {
        assert.deepEqual(
          Array.from((child as THREE.Mesh).geometry.getAttribute("position").array),
          Array.from((continuous.children[i] as THREE.Mesh).geometry.getAttribute("position").array),
        );
        (child as THREE.Mesh).geometry.dispose();
      });
    }
  } finally {
    continuous.children.forEach((child) => (child as THREE.Mesh).geometry.dispose());
    source.geometry.dispose();
    source.material.dispose();
  }
});
