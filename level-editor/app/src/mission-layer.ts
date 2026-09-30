import * as THREE from "three";
import { gameToScene, type Level3D } from "@rle/shared";
import { disposeObjectResources } from "./resources.ts";

/** Editor markers have their own root so they never enter the baked map artwork. */
export class MissionLayer {
  readonly root = new THREE.Group();
  private key = "";

  clear() {
    disposeObjectResources([this.root]);
    this.root.clear();
    this.key = "";
  }

  sync(document: Level3D, selected = "") {
    const key = JSON.stringify([document.mission, document.camera, selected]);
    if (key === this.key) return;
    this.clear();
    this.key = key;
    for (const [kind, entries] of [
      ["PC", document.mission?.spawnPoints ?? []],
      ["NPC", document.mission?.soldiers ?? []],
    ] as const) {
      for (const entry of entries) {
        const marker = new THREE.Group();
        marker.userData.missionId = entry.id;
        marker.position.set(...gameToScene(document.camera, ...entry.position));
        const material = new THREE.MeshBasicMaterial({
          color: entry.id === selected ? 0xffdd55 : kind === "PC" ? 0x55bbff : 0xff6655,
          depthTest: false,
        });
        const body = new THREE.Mesh(new THREE.ConeGeometry(9, 30, 8), material);
        body.rotation.x = Math.PI / 2;
        body.position.z = 20;
        body.renderOrder = 1100;
        const base = new THREE.Mesh(new THREE.RingGeometry(11, 15, 24), material);
        base.position.z = 1;
        base.renderOrder = 1100;
        marker.add(body, base);
        this.root.add(marker);
      }
    }
  }

  hit(raycaster: THREE.Raycaster): string | undefined {
    const hit = raycaster.intersectObject(this.root, true)[0];
    return hit?.object.parent?.userData.missionId;
  }
}
