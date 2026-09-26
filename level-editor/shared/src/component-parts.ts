/** Stable editor part identity retains the canonical obstacle and an explicit scoped component. */
export function obstaclePartIdentity(
  node: string,
): { kind: "building" | "terrace"; obstacle: number; component?: string } | null {
  const match = /^(building|terrace)-(\d+)(?:--component-([a-zA-Z0-9_-]+))?$/.exec(node);
  return match
    ? {
        kind: match[1] as "building" | "terrace",
        obstacle: Number(match[2]),
        ...(match[3] ? { component: match[3] } : {}),
      }
    : null;
}

export function componentIdentityMatches(
  node: string,
  obstacle: unknown,
  components: unknown,
): boolean {
  const identity = obstaclePartIdentity(node);
  if (!identity || identity.obstacle !== obstacle) return false;
  return identity.component === undefined
    ? components === undefined
    : Array.isArray(components) && components.length === 1 && components[0] === identity.component;
}
