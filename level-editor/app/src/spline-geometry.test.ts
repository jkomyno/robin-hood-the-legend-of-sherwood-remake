import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { parseLevel3D, type LevelSpline, type Level3D } from "@rle/shared";
import { riverGeometry, splineCurve, wallMesh } from "./spline-geometry.ts";
import { SplineLayer } from "./spline-layer.ts";

const camera = { kind: "oblique-orthographic" as const, elevation_deg: 35 };
const river: LevelSpline = { id: "river", name: "River", kind: "river", points: [[0,0,0],[300,0,0],[600,150,0]],
  width: 80, repeatLength: 100, closed: false };
test("river ribbons keep world width and repeat texture by arc length through curves", () => {
  const geometry = riverGeometry(river, camera), positions = geometry.getAttribute("position"), uv = geometry.getAttribute("uv");
  for (let i = 0; i < positions.count; i += 2) {
    assert.ok(Math.abs(new THREE.Vector3().fromBufferAttribute(positions, i).distanceTo(
      new THREE.Vector3().fromBufferAttribute(positions, i + 1)) - 80) < 0.001);
  }
  assert.ok(Math.abs(uv.getY(uv.count - 1) - splineCurve(river, camera).getLength() / 100) < 1e-5);
  geometry.dispose();
});
test("wall repeats bend real mesh vertices, retain UVs and leave shared geometry untouched", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 12, 40), new THREE.MeshBasicMaterial());
  const original = Array.from(source.geometry.getAttribute("position").array);
  const path: LevelSpline = { ...river, kind: "wall", asset: "wall", axis: "x", width: 12, repeatLength: 100 };
  const wall = wallMesh(path, camera, new Map([["asset:wall:building-000", source]]));
  assert.ok(wall.children.length >= 6);
  const last = wall.children.at(-1) as THREE.Mesh;
  const end = new THREE.Box3().setFromObject(last);
  assert.ok(end.max.x > 590 && end.min.y < -200, "last section must follow the curved endpoint");
  assert.ok(last.geometry.getAttribute("uv").count > 0);
  assert.deepEqual(Array.from(source.geometry.getAttribute("position").array), original);
  wall.traverse(node => { if (node instanceof THREE.Mesh) node.geometry.dispose(); });
  source.geometry.dispose(); (source.material as THREE.Material).dispose();
});
test("a skewed source wall keeps its requested thickness instead of its bounding-box ratio", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 12, 40), new THREE.MeshBasicMaterial());
  const positions = source.geometry.getAttribute("position");
  for (let i = 0; i < positions.count; i++) positions.setY(i, positions.getY(i) + positions.getX(i) * 0.6);
  const path: LevelSpline = { ...river, kind: "wall", asset: "wall", axis: "x", width: 30,
    repeatLength: 100, points: [[0,0,0],[200,0,0]] };
  const wall = wallMesh(path, camera, new Map([["asset:wall:building-000", source]]));
  for (const child of wall.children) {
    const bounds = new THREE.Box3().setFromObject(child);
    assert.ok(Math.abs(bounds.max.y - bounds.min.y - 30) < 0.001);
  }
  wall.traverse(node => { if (node instanceof THREE.Mesh) node.geometry.dispose(); });
  source.geometry.dispose(); source.material.dispose();
});
test("flipping the wall puts its parapet on the opposite side and preserves outward face winding", () => {
  const source = new THREE.Group();
  const base=new THREE.Mesh(new THREE.BoxGeometry(100,20,30),new THREE.MeshBasicMaterial());
  const parapet=new THREE.Mesh(new THREE.BoxGeometry(100,4,12),new THREE.MeshBasicMaterial());
  parapet.position.set(0,8,21);
  source.add(base,parapet);
  const path: LevelSpline = {...river,kind:"wall",asset:"wall",axis:"x",width:20,repeatLength:100,points:[[0,0,0],[100,0,0]]};
  const sources=new Map([["asset:wall:building-000",source]]);
  const normal=wallMesh(path,camera,sources),flipped=wallMesh({...path,flipCrossSection:true},camera,sources);
  const before=new THREE.Box3().setFromObject(normal.children[1]!);
  const after=new THREE.Box3().setFromObject(flipped.children[1]!);
  assert.ok(before.min.y>0 && after.max.y<0,"parapet must swap sides");
  for(const group of [normal,flipped]) group.traverse(node=>{
    if(!(node instanceof THREE.Mesh)) return;
    const p=node.geometry.getAttribute("position"),n=node.geometry.getAttribute("normal");
    let top=false;
    for(let i=0;i<p.count;i++) if(n.getZ(i)>.99) top=true;
    assert.ok(top,"top-facing triangles must retain positive normals after reflection");
    node.geometry.dispose();
  });
  base.geometry.dispose();parapet.geometry.dispose();base.material.dispose();parapet.material.dispose();
});
test("spline geometry retirement does not dispose borrowed wall materials or source meshes", () => {
  const source = new THREE.Mesh(new THREE.BoxGeometry(100, 12, 40), new THREE.MeshBasicMaterial());
  let sourceDisposals = 0;
  source.geometry.addEventListener("dispose", () => sourceDisposals++);
  source.material.addEventListener("dispose", () => sourceDisposals++);
  const layer = new SplineLayer();
  const path: LevelSpline = { ...river, kind: "wall", asset: "wall", axis: "x", width: 12, repeatLength: 100 };
  layer.sync([path], camera, new Map([["asset:wall:building-000", source]]));
  layer.clear();
  assert.equal(sourceDisposals, 0);
  source.geometry.dispose(); source.material.dispose();
});
test("documents round-trip splines and reject dangling sources and invalid control geometry", () => {
  const document: Level3D = { version: 1, map: "Test", glb: "map.glb", size: [1000,1000], camera, objects: [], groups: [], splines: [river] };
  assert.deepEqual(parseLevel3D(JSON.parse(JSON.stringify(document))).splines, [river]);
  assert.throws(() => parseLevel3D({ ...document, splines: [{ ...river, width: 0 }] }), /width/);
  assert.throws(() => parseLevel3D({ ...document, splines: [{ ...river, points: [[0,0,0]] }] }), /control points/);
  assert.throws(() => parseLevel3D({ ...document, splines: [{ ...river, kind: "wall", asset: "missing", axis: "x" }] }), /wall asset/);
});

test("corner towers join turns, skip straight controls and retain shared resources", () => {
  const curtain=new THREE.Mesh(new THREE.BoxGeometry(100,12,40),new THREE.MeshBasicMaterial());
  const tower=new THREE.Mesh(new THREE.CylinderGeometry(24,24,50,16).rotateX(Math.PI/2),new THREE.MeshBasicMaterial());
  const sources=new Map([["asset:wall:building-000",curtain],["asset:tower:building-001",tower]]);
  const path:LevelSpline={...river,kind:"wall",asset:"wall",axis:"x",cornerAsset:"tower",cornerMinAngle:40,cornerWidthScale:2,
    width:12,repeatLength:100,points:[[0,0,0],[100,0,0],[200,0,0],[200,150,20]]};
  const layer=new SplineLayer();let disposed=0;
  tower.geometry.addEventListener("dispose",()=>disposed++);tower.material.addEventListener("dispose",()=>disposed++);
  layer.sync([path],camera,sources);
  const joined=layer.root.children[1]!;
  const corners=joined.children.filter(c=>c.userData.cornerPoint!==undefined);
  assert.equal(corners.length,1);assert.equal(corners[0]!.userData.cornerPoint,2);
  assert.ok(corners[0]!.position.distanceTo(new THREE.Vector3(200,0,0))<.001);
  const fitted=new THREE.Box3().setFromObject(corners[0]!,true).getSize(new THREE.Vector3());
  assert.ok(fitted.x>94 && fitted.x<98 && Math.abs(fitted.z-50)<.001,"tower width must change independently of height");
  layer.sync([{...path,cornerDisabled:[2]}],camera,sources);
  assert.ok(!layer.root.children[1]!.children.some(c=>c.userData.cornerPoint!==undefined));
  layer.clear();assert.equal(disposed,0);
  curtain.geometry.dispose();curtain.material.dispose();tower.geometry.dispose();tower.material.dispose();
});
test("closed walls place seam towers once, including a single remaining corner", () => {
  const source=new THREE.Mesh(new THREE.BoxGeometry(100,12,40),new THREE.MeshBasicMaterial());
  const sources=new Map([["asset:wall:building-000",source],["asset:tower:building-001",source]]);
  const path:LevelSpline={...river,kind:"wall",asset:"wall",axis:"x",cornerAsset:"tower",closed:true,
    points:[[0,0,0],[200,0,0],[200,200,0],[0,200,0]]};
  for(const disabled of [[],[1,2,3]]) {
    const result=wallMesh({...path,cornerDisabled:disabled},camera,sources);
    assert.equal(result.children.filter(c=>c.userData.cornerPoint!==undefined).length,4-disabled.length);
    result.traverse(n=>{if(n instanceof THREE.Mesh)n.geometry.dispose();});
  }
  source.geometry.dispose();source.material.dispose();
});
test("footpaths save independently of water and follow authored height", () => {
  const road:LevelSpline={...river,kind:"road",width:24,points:[[0,0,5],[80,20,30],[160,40,40]]};
  const doc:Level3D={version:1,map:"Roads",glb:"map.glb",size:[300,300],camera,objects:[],groups:[],splines:[road]};
  assert.deepEqual(parseLevel3D(JSON.parse(JSON.stringify(doc))).splines,[road]);
  const geometry=riverGeometry(road,camera);assert.ok(geometry.getAttribute("position").getZ(0)>5);
  const layer=new SplineLayer();layer.sync([road],camera,new Map());
  assert.equal(layer.root.children[1]!.userData.noSunShadow,true);
  layer.clear();geometry.dispose();
});
