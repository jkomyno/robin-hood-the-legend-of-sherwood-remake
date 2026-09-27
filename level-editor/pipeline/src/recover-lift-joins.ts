import type { Vec3 } from "@rle/shared";

/** Recover shared edge sockets despite small differences between adjacent fitted planes. */
export function recoverLiftJoins(surfaces: Vec3[][]): Vec3[][] {
  const joins: Vec3[][] = surfaces.map(() => []);
  const near = (a: Vec3, b: Vec3) => Math.hypot(...a.map((n, i) => n - b[i]!)) < 0.25;
  for (let a = 0; a < surfaces.length; a++)
    for (let b = a + 1; b < surfaces.length; b++) {
      const first = surfaces[a]!,
        second = surfaces[b]!;
      const shared: Vec3[] = [];
      for (let i = 0; i < first.length; i++)
        for (let j = 0; j < second.length; j++) {
          const p = first[i]!,
            q = first[(i + 1) % first.length]!;
          const r = second[j]!,
            s = second[(j + 1) % second.length]!;
          if ((near(p, r) && near(q, s)) || (near(p, s) && near(q, r)))
            shared.push(p.map((n, k) => (n + q[k]! + r[k]! + s[k]!) / 4) as Vec3);
        }
      if (!shared.length) continue;
      if (shared.length !== 1) throw new Error("Compound lift requires an unambiguous shared edge");
      joins[a]!.push(shared[0]!);
      joins[b]!.push(shared[0]!);
    }
  if (surfaces.length > 1 && joins.some((j) => !j.length))
    throw new Error("Compound lift has a segment without a shared edge");
  return joins;
}
