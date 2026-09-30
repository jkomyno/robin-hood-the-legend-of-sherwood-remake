import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { createTerrainGrid, gameToScene, type Level3D } from "@rle/shared";
import { EditorViewport } from "./editor-viewport.ts";
import { resizeWorkspace } from "./workspace.ts";

function fixture() {
  let document: Level3D = {
    version: 1,
    map: "Clipping",
    size: [800, 700],
    sceneAssets: [],
    objects: [],
    groups: [],
    camera: { kind: "oblique-orthographic", elevation_deg: 35 },
    terrain: createTerrainGrid([0, 0, 800, 700], 200, 0),
  };
  const viewport = new EditorViewport({
    document: () => document,
    selection: () => null,
    level: () => null,
    showElevation: () => false,
    showObstacles: () => false,
    onSelection: () => {},
    commitTransform: () => {},
  });
  const camera = new THREE.OrthographicCamera(-1000, 1000, 1000, -1000, -100000, 100000);
  const target = new THREE.Vector3(400, 0, 600);
  Object.assign(viewport, {
    camera,
    orbit: { target },
    frustum: 3000,
    container: { clientWidth: 800, clientHeight: 800 },
  });
  viewport.syncViews(document);
  return {
    viewport,
    camera,
    target,
    document: () => document,
    edit(next: Level3D) {
      document = next;
      viewport.syncViews(next, false);
    },
  };
}
function worldPoints(document: Level3D) {
  return document.terrain!.vertices.map(({ position }) => {
    const [x, y, z] = gameToScene(document.camera, ...position);
    return new THREE.Vector3(x, z, -y);
  });
}
function assertDepth(viewport: EditorViewport, points: THREE.Vector3[], label: string) {
  const lens = (viewport as unknown as { activeCamera(): THREE.Camera }).activeCamera();
  for (const point of points) {
    const depth = point.clone().project(lens).z;
    assert.ok(depth >= -1 && depth <= 1, `${label}: ${point.toArray()} clipped at ${depth}`);
  }
}
test("initial terrain bounds include the Z-up to Y-up scene transform at every orbit angle", () => {
  const { viewport, camera, target, document } = fixture();
  for (const yaw of [0, Math.PI / 2, Math.PI, -Math.PI / 2]) {
    camera.position.copy(target).add(new THREE.Vector3().setFromSphericalCoords(10000, 0.75, yaw));
    camera.lookAt(target);
    assertDepth(viewport, worldPoints(document()), `yaw ${yaw}`);
  }
  viewport.dispose();
});

test("live terrain edits and cancellation update clipping independently of lens framing", () => {
  const { viewport, camera, target, document, edit } = fixture();
  const before = document();
  const raised = {
    ...before,
    terrain: {
      ...before.terrain!,
      vertices: before.terrain!.vertices.map((v) => ({
        ...v,
        position: [v.position[0], v.position[1], 1800 + v.position[0] / 2] as [
          number,
          number,
          number,
        ],
      })),
    },
  };
  for (const lens of [0, 1, 30, 65]) {
    viewport.setPerspective(lens);
    for (const zoom of [0.1, 0.5, 1]) {
      camera.zoom = zoom;
      for (const yaw of [0, Math.PI / 2, Math.PI]) {
        camera.position
          .copy(target)
          .add(new THREE.Vector3().setFromSphericalCoords(10000, 0.95, yaw));
        camera.lookAt(target);
        edit(raised);
        assertDepth(viewport, worldPoints(raised), `raised lens ${lens} zoom ${zoom} yaw ${yaw}`);
        edit(before);
        assertDepth(viewport, worldPoints(before), `restored lens ${lens} zoom ${zoom} yaw ${yaw}`);
      }
    }
  }
  viewport.dispose();
});

test("repeated workspace growth and shrink retain terrain and asset depth across opposing views", () => {
  const { viewport, camera, target, document, edit } = fixture();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(60, 60, 400), new THREE.MeshBasicMaterial());
  mesh.position.z = 200;
  const source = new THREE.Group();
  source.add(mesh);
  viewport.replaceMap(source, null, new Map([["tower", mesh]]));
  const assetDocument: Level3D = {
    ...document(),
    objects: [
      {
        id: "tower",
        node: "tower",
        kind: "scenery",
        source: { map: "Clipping" },
        transform: { dx: 700, dy: 650, dz: 0, rot_deg: 0 },
      },
    ],
  };
  edit(assetDocument);
  for (const size of [
    [1800, 1400],
    [200, 150],
    [2600, 1900],
    [400, 350],
  ] as [number, number][]) {
    const resized = resizeWorkspace(document(), size);
    // An incremental asset move must also refresh depth without a lens refit.
    edit({
      ...resized,
      objects: resized.objects.map((object) => ({
        ...object,
        transform: { ...object.transform, dz: size[0] / 2 },
      })),
    });
    const roots = (viewport as unknown as { objectsRoot: THREE.Group }).objectsRoot;
    roots.updateWorldMatrix(true, true);
    const points = worldPoints(document());
    roots.traverse((node) => {
      if (!(node instanceof THREE.Mesh)) return;
      const vertices = node.geometry.getAttribute("position");
      for (let index = 0; index < vertices.count; index++)
        points.push(
          new THREE.Vector3().fromBufferAttribute(vertices, index).applyMatrix4(node.matrixWorld),
        );
    });
    for (const lens of [0, 30]) {
      viewport.setPerspective(lens);
      for (const yaw of [0, Math.PI, Math.PI / 2, -Math.PI / 2]) {
        for (const zoom of lens === 0 ? [0.25, 1, 4] : [0.1, 0.25, 0.5]) {
          camera.zoom = zoom;
          camera.position
            .copy(target)
            .add(new THREE.Vector3().setFromSphericalCoords(500, 1.45, yaw));
          camera.lookAt(target);
          assertDepth(viewport, points, `workspace ${size} lens ${lens} yaw ${yaw} zoom ${zoom}`);
        }
      }
    }
  }
  viewport.dispose();
});
