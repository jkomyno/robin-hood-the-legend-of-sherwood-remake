import type { Level3D } from "../../shared/src/level3d.ts";
import type { AssetMovementTransition } from "../../shared/src/asset-gameplay.ts";

interface RecoveredTransition {
  asset: string;
  patch: number;
  transition: string;
}

/** One-time migration of exported preview provenance into asset-local switch bindings. */
export function recoverAppearanceBindings(
  document: Level3D,
  patchCount: number,
  recovered: readonly RecoveredTransition[],
  transitions: ReadonlyMap<string, readonly AssetMovementTransition[]>,
) {
  const names = new Map<string, { asset: string; appearance: string; aliases: Set<string> }>();
  for (const owner of [...document.groups, ...document.objects]) {
    for (const [asset, mappings] of Object.entries(owner.patches ?? {})) {
      for (const [appearance, alias] of Object.entries(mappings)) {
        const key = JSON.stringify([asset, appearance]);
        const entry = names.get(key) ?? { asset, appearance, aliases: new Set<string>() };
        entry.aliases.add(alias);
        names.set(key, entry);
      }
    }
  }
  const bindings: (RecoveredTransition & { appearance: string })[] = [];
  const unresolved: { asset: string; appearance: string; aliases: string[]; reason: string }[] = [];
  for (const { asset, appearance, aliases } of names.values()) {
    const reject = (reason: string) =>
      unresolved.push({ asset, appearance, aliases: [...aliases], reason });
    if (aliases.size !== 1) {
      reject("Conflicting appearance provenance across asset placements");
      continue;
    }
    const alias = [...aliases][0]!;
    const match = /^patch-(\d{3,})$/.exec(alias);
    const patch = match ? Number(match[1]) : -1;
    if (
      !Number.isSafeInteger(patch) ||
      patch < 0 ||
      patch >= patchCount ||
      alias !== `patch-${String(patch).padStart(3, "0")}`
    ) {
      reject(
        "Missing canonical map-patch provenance; mission and custom preview names require separate authoring",
      );
      continue;
    }
    const candidates = [
      ...new Set(
        recovered.filter((r) => r.asset === asset && r.patch === patch).map((r) => r.transition),
      ),
    ];
    if (candidates.length !== 1) {
      reject(
        "Appearance needs one recovered switch on its own asset; cross-asset ownership requires an explicit join",
      );
      continue;
    }
    const transition = candidates[0]!;
    const local = transitions.get(asset) ?? [];
    if (
      local.filter((t) => t.id === transition).length !== 1 ||
      local.some((t) => t.id !== transition && t.appearances?.includes(appearance))
    ) {
      reject("Missing or conflicting asset-local transition definition");
      continue;
    }
    bindings.push({ asset, appearance, patch, transition });
  }
  return { bindings, unresolved };
}
