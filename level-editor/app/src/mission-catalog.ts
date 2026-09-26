import { missionLabel } from '../../../wasm-www/src/leaderboards/missions.ts';
import type { DatadirIndex } from './datadir.ts';
import { readMission } from './mission.ts';

export interface MissionEntry { id:string; map:string; label:string; }
export async function loadMissionCatalog(index: DatadirIndex): Promise<MissionEntry[]> {
  const result: MissionEntry[]=[];
  const pending=[...(index.missions??[])];
  await Promise.all(Array.from({length:Math.min(4,pending.length)},async()=>{
    while(pending.length){
      const id=pending.shift()!;
      const mission=await readMission(index,id);
      result.push({id,map:mission.map,label:missionLabel(id,id,id.startsWith('Dem_'))});
    }
  }));
  return result.sort((a,b)=>a.label.localeCompare(b.label,undefined,{numeric:true}));
}

export function missionsForMap(index: DatadirIndex | null, map: string | null | undefined) {
  return (index?.missionEntries??[]).filter(entry=>entry.map.toLowerCase()===map?.toLowerCase());
}
