import type { MapCamera, PopulationRoute, Vec3 } from "@rle/shared";

/** A route pauses at each stop and either loops or reverses at its endpoints. */
export function routeSchedule(route: PopulationRoute, camera: MapCamera) {
  const sin=Math.sin(camera.elevation_deg*Math.PI/180),cos=Math.cos(camera.elevation_deg*Math.PI/180);
  const order=Array.from({length:route.points.length},(_,i)=>i);
  if(route.mode==="ping-pong")order.push(...order.slice(1,-1).reverse());
  let duration=0;
  const legs=order.map((index,i)=>{
    const from=route.points[index]!,to=route.points[order[(i+1)%order.length]!]!;
    const dx=to.position[0]-from.position[0],dy=to.position[1]-from.position[1],dz=to.position[2]-from.position[2];
    const travel=Math.hypot(dx,dy/sin,dz/cos)/route.speed;
    const start=duration;duration+=from.wait+travel;
    const direction=(Math.round(Math.atan2(dx,-dy/sin)*8/Math.PI)+16)%16;
    return {from,to,start,travel,direction};
  });
  if(!Number.isFinite(duration)||duration<=0)throw new Error("Route has no duration: "+route.id);
  return {duration,legs};
}
export function routePose(schedule: ReturnType<typeof routeSchedule>, seconds:number):{position:Vec3;direction:number;walking:boolean} {
  const time=((seconds%schedule.duration)+schedule.duration)%schedule.duration;
  const leg=schedule.legs.find(l=>time<l.start+l.from.wait+l.travel) ?? schedule.legs.at(-1)!;
  const elapsed=time-leg.start,walking=elapsed>=leg.from.wait;
  const t=walking?Math.min(1,(elapsed-leg.from.wait)/leg.travel):0;
  return {position:leg.from.position.map((p,i)=>p+(leg.to.position[i]!-p)*t) as Vec3,
    direction:walking?leg.direction:leg.from.direction??leg.direction,walking};
}
