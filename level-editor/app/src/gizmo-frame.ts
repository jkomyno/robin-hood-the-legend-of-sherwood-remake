import * as THREE from "three";

/** Anchor translation axes at the geometry center, retaining the object's authored origin. */
export function centerGizmoFrame(
  object: THREE.Object3D,
  frame: THREE.Object3D,
  originOffset: THREE.Vector3,
) {
  object.updateWorldMatrix(true, true);
  const bounds = new THREE.Box3().setFromObject(object, true);
  object.getWorldPosition(originOffset);
  if (bounds.isEmpty()) frame.position.copy(originOffset);
  else bounds.getCenter(frame.position);
  originOffset.sub(frame.position);
  frame.updateMatrixWorld(true);
}

export function moveFromGizmoFrame(
  object: THREE.Object3D,
  frame: THREE.Object3D,
  originOffset: THREE.Vector3,
) {
  const origin = frame.position.clone().add(originOffset);
  if (object.parent) object.parent.worldToLocal(origin);
  object.position.copy(origin);
}
