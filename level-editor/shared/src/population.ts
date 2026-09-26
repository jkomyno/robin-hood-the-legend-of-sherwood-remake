import type { Vec3 } from "./scene.ts";

export interface PopulationRoute {
  id: string;
  name: string;
  mode: "loop" | "ping-pong";
  speed: number;
  points: { position: Vec3; wait: number; direction?: number }[];
}
export interface PopulationActor {
  id: string;
  name: string;
  role: "soldier" | "civilian" | "beggar";
  sprite: string;
  position: Vec3;
  direction: number;
  duty: string;
  route?: string;
  phase?: number;
  routeOffset?: number;
  information?: string;
}
export interface PopulationItem {
  id: string;
  name: string;
  sprite: string;
  position: Vec3;
  quantity: number;
  purpose: string;
}
export interface Population {
  version: 1;
  spriteCatalog: string;
  actors: PopulationActor[];
  items: PopulationItem[];
  routes: PopulationRoute[];
}
export interface PopulationSpriteFrame {
  rect: [number, number, number, number];
  offset: [number, number];
  duration: number;
}
export interface PopulationSprite {
  image: string;
  width: number;
  height: number;
  kind: "character" | "pickup";
  idle: Record<string, PopulationSpriteFrame[]>;
  walk?: Record<string, PopulationSpriteFrame[]>;
}
export interface PopulationSpriteCatalog {
  version: 1;
  sprites: Record<string, PopulationSprite>;
}

export function validatePopulation(value: unknown): asserts value is Population {
  const fail = (message: string): never => {
    throw new Error("Population: " + message);
  };
  if (!value || typeof value !== "object") fail("expected object");
  const p = value as Population;
  if (
    p.version !== 1 ||
    typeof p.spriteCatalog !== "string" ||
    !safePopulationPath(p.spriteCatalog)
  )
    fail("invalid sprite catalog");
  if (!Array.isArray(p.actors) || !Array.isArray(p.items) || !Array.isArray(p.routes))
    fail("expected actors, items and routes");
  const ids = new Set<string>(),
    routes = new Set<string>();
  const id = (v: string) => {
    if (typeof v !== "string" || !v || ids.has(v)) fail("duplicate or missing ID");
    ids.add(v);
  };
  const position = (v: Vec3) => {
    if (!Array.isArray(v) || v.length !== 3 || !v.every(Number.isFinite)) fail("invalid position");
  };
  const direction = (v: number) => {
    if (!Number.isInteger(v) || v < 0 || v > 15) fail("invalid direction");
  };
  for (const r of p.routes) {
    id(r.id);
    routes.add(r.id);
    if (
      !r.name ||
      !["loop", "ping-pong"].includes(r.mode) ||
      !Number.isFinite(r.speed) ||
      r.speed <= 0
    )
      fail("invalid route");
    if (!Array.isArray(r.points) || r.points.length < 2) fail("route requires two points");
    for (const [i, pt] of r.points.entries()) {
      position(pt.position);
      if (!Number.isFinite(pt.wait) || pt.wait < 0) fail("invalid wait");
      if (pt.direction !== undefined) direction(pt.direction);
      if (
        i &&
        Math.hypot(
          pt.position[0] - r.points[i - 1].position[0],
          pt.position[1] - r.points[i - 1].position[1],
        ) < 0.01
      )
        fail("duplicate route point");
    }
  }
  for (const a of p.actors) {
    id(a.id);
    position(a.position);
    direction(a.direction);
    if (!["soldier", "civilian", "beggar"].includes(a.role) || !a.name || !a.sprite || !a.duty)
      fail("invalid actor");
    if (a.route !== undefined && !routes.has(a.route)) fail("missing route " + a.route);
    if (
      a.routeOffset !== undefined &&
      (!Number.isFinite(a.routeOffset) || Math.abs(a.routeOffset) > 30)
    )
      fail("invalid route offset");
    if (a.phase !== undefined && (!Number.isFinite(a.phase) || a.phase < 0))
      fail("invalid patrol phase");
  }
  for (const i of p.items) {
    id(i.id);
    position(i.position);
    if (
      !i.name ||
      !i.sprite ||
      !i.purpose ||
      !Number.isInteger(i.quantity) ||
      i.quantity < 1 ||
      i.quantity > 5
    )
      fail("invalid item");
  }
}
export function safePopulationPath(path: string) {
  return (
    path.length > 0 &&
    !/[\\\\:]/.test(path) &&
    path.split("/").every((p) => p !== "" && p !== "." && p !== "..")
  );
}
