import test from "node:test";
import assert from "node:assert/strict";
import { parseLevel3D, parseProjectionAssetDescriptor, type Level3D } from "@rle/shared";
import { assetFixture } from "./asset-commands.test.ts";
import { insertProjectionAsset } from "./asset-commands.ts";
import { deleteSelection, duplicateSelection, patchPart, setGroupState } from "./document-commands.ts";
import { MapSession } from "./session.ts";

function fixture() {
  const data = assetFixture();
  data.descriptor.states = { active: "initial", initial: ["building-000"], applied: ["building-001"] };
  return { ...data, ...insertProjectionAsset(data.document, data.descriptor, data.reference, [20, 30, 0]) };
}

test("atomic state switching persists, reloads, undoes and redoes both endpoints", () => {
  const { document, selection } = fixture();
  const before = structuredClone(document);
  const applied = setGroupState(document, selection.id, "applied");
  assert.deepEqual(document, before);
  assert.deepEqual(applied.objects.map(part => part.hidden), [true, false]);
  assert.equal(applied.groups[0]!.states!.active, "applied");
  assert.deepEqual(applied.groups[0]!.transform, document.groups[0]!.transform);
  assert.deepEqual(parseLevel3D(JSON.parse(JSON.stringify(applied))), applied);
  const session = new MapSession<Level3D, string>();
  session.publish(session.beginLoad(), "Leicester", document, "private");
  session.edit(applied);
  session.undo(); assert.equal(session.current!.document, document);
  session.redo(); assert.equal(session.current!.document, applied);
});

test("group copies remap state ownership and switch independently; deletion removes the whole group", () => {
  const { document, selection } = fixture();
  const copy = duplicateSelection(document, selection);
  parseLevel3D(copy.document);
  const switched = setGroupState(copy.document, copy.selection.id, "applied");
  assert.equal(switched.groups[0]!.states!.active, "initial");
  assert.equal(switched.groups[1]!.states!.active, "applied");
  assert.equal(switched.objects[0]!.hidden, undefined);
  assert.equal(switched.objects[2]!.hidden, true);
  assert.deepEqual(deleteSelection(switched, copy.selection), document);
  const endpoint = document.objects[0]!.id;
  assert.throws(() => duplicateSelection(document, { kind: "part", id: endpoint }), /complete state group/);
  assert.throws(() => deleteSelection(document, { kind: "part", id: endpoint }), /complete state group/);
  assert.throws(() => patchPart(document, endpoint, { hidden: true }), /State selector/);
});

test("state validation rejects dangling, overlapping, empty and nonexclusive endpoints", () => {
  const { descriptor, document } = fixture();
  for (const states of [
    { active: "initial", initial: [], applied: ["building-001"] },
    { active: "initial", initial: ["building-000"], applied: ["building-000"] },
    { active: "initial", initial: ["missing"], applied: ["building-001"] },
    { active: "applied", initial: ["building-000"], applied: ["building-001"] },
    { active: "other", initial: ["building-000"], applied: ["building-001"] },
  ]) assert.throws(() => parseProjectionAssetDescriptor({ ...descriptor, states }));
  const broken = structuredClone(document);
  broken.objects[1]!.hidden = false;
  assert.throws(() => parseLevel3D(broken), /visibility mismatch/);
  const foreign = structuredClone(document);
  foreign.objects[1]!.group = undefined;
  assert.throws(() => parseLevel3D(foreign), /outside its group/);
});
